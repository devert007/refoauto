#!/usr/bin/env python3
"""
OAuth 2.0 authentication for DialogGauge API via Google.

First run: opens browser for Google login, saves refresh_token.
Subsequent runs: automatically refreshes tokens without browser.

Usage:
    python auth_oauth.py          # Get/refresh session and test API
    python auth_oauth.py --login  # Force new login (re-authorize)
"""

import json
import sys
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

BASE_DIR = Path(__file__).parent
TOKEN_FILE = BASE_DIR / ".oauth_tokens.json"

# DialogGauge OAuth endpoints (need to verify these)
DG_BASE_URL = "https://dialoggauge.yma.health"
DG_AUTH_URL = f"{DG_BASE_URL}/auth/google"  # или /oauth/google, /login/google
DG_CALLBACK_URL = f"{DG_BASE_URL}/auth/google/callback"

# Google OAuth configuration
# Эти значения нужно получить из Google Cloud Console
# или из существующего credentials.json если он для этого проекта
GOOGLE_CLIENT_ID = ""  # Заполнить!
GOOGLE_CLIENT_SECRET = ""  # Заполнить!
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Scopes для Google OAuth (email + profile обычно достаточно)
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

# Local callback server
LOCAL_PORT = 8765
LOCAL_REDIRECT_URI = f"http://localhost:{LOCAL_PORT}/callback"


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback from Google."""
    
    authorization_code = None
    
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/callback":
            params = parse_qs(parsed.query)
            if "code" in params:
                OAuthCallbackHandler.authorization_code = params["code"][0]
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<html><body><h1>Success!</h1>")
                self.wfile.write(b"<p>Authorization complete. You can close this window.</p>")
                self.wfile.write(b"</body></html>")
            else:
                error = params.get("error", ["Unknown error"])[0]
                self.send_response(400)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"<html><body><h1>Error: {error}</h1></body></html>".encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress logging


def load_tokens() -> dict | None:
    """Load saved tokens from file."""
    if not TOKEN_FILE.exists():
        return None
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tokens(tokens: dict) -> None:
    """Save tokens to file."""
    tokens["saved_at"] = int(time.time())
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=2)
    print(f"Tokens saved to {TOKEN_FILE}")


def get_authorization_code() -> str:
    """Open browser for Google OAuth and get authorization code."""
    
    if not GOOGLE_CLIENT_ID:
        raise ValueError(
            "GOOGLE_CLIENT_ID not set. Get it from Google Cloud Console:\n"
            "1. Go to https://console.cloud.google.com/apis/credentials\n"
            "2. Create OAuth 2.0 Client ID (Desktop app)\n"
            "3. Add http://localhost:8765/callback to redirect URIs\n"
            "4. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in this script"
        )
    
    # Build authorization URL
    auth_params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": LOCAL_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",  # This requests refresh_token!
        "prompt": "consent",  # Force consent to get refresh_token
    }
    auth_url = GOOGLE_AUTH_URL + "?" + "&".join(f"{k}={v}" for k, v in auth_params.items())
    
    print(f"\nOpening browser for Google authorization...")
    print(f"If browser doesn't open, go to:\n{auth_url}\n")
    webbrowser.open(auth_url)
    
    # Start local server to receive callback
    server = HTTPServer(("localhost", LOCAL_PORT), OAuthCallbackHandler)
    server.timeout = 120  # 2 minutes timeout
    
    print(f"Waiting for authorization (listening on port {LOCAL_PORT})...")
    while OAuthCallbackHandler.authorization_code is None:
        server.handle_request()
    
    code = OAuthCallbackHandler.authorization_code
    OAuthCallbackHandler.authorization_code = None  # Reset for next use
    
    return code


def exchange_code_for_tokens(code: str) -> dict:
    """Exchange authorization code for access and refresh tokens."""
    
    data = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": LOCAL_REDIRECT_URI,
    }
    
    response = requests.post(GOOGLE_TOKEN_URL, data=data)
    
    if response.status_code != 200:
        raise Exception(f"Token exchange failed: {response.text}")
    
    tokens = response.json()
    
    if "refresh_token" not in tokens:
        print("WARNING: No refresh_token received. You may need to revoke access and re-authorize.")
    
    return tokens


def refresh_access_token(refresh_token: str) -> dict:
    """Use refresh token to get new access token."""
    
    data = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    
    response = requests.post(GOOGLE_TOKEN_URL, data=data)
    
    if response.status_code != 200:
        raise Exception(f"Token refresh failed: {response.text}")
    
    new_tokens = response.json()
    # Refresh token is not always returned, keep the old one
    if "refresh_token" not in new_tokens:
        new_tokens["refresh_token"] = refresh_token
    
    return new_tokens


def get_dg_session_with_google_token(access_token: str) -> str:
    """
    Exchange Google access_token for DialogGauge session.
    
    This depends on how DialogGauge handles the OAuth flow.
    Common patterns:
    1. POST /auth/google with {access_token: "..."}
    2. POST /auth/google with {id_token: "..."}
    3. GET /auth/google/callback?access_token=...
    """
    
    # Try pattern 1: POST with access_token
    print("\nTrying to get DialogGauge session...")
    
    # Option A: POST to auth endpoint
    try:
        response = requests.post(
            f"{DG_BASE_URL}/auth/google",
            json={"access_token": access_token},
            allow_redirects=False
        )
        if "dg_session" in response.cookies:
            return response.cookies["dg_session"]
    except Exception as e:
        print(f"  POST /auth/google failed: {e}")
    
    # Option B: Try with Authorization header
    try:
        response = requests.get(
            f"{DG_BASE_URL}/api/me",  # or /api/user, /api/profile
            headers={"Authorization": f"Bearer {access_token}"},
            allow_redirects=False
        )
        if response.status_code == 200:
            if "dg_session" in response.cookies:
                return response.cookies["dg_session"]
            # Maybe API accepts Bearer token directly
            print("  API accepts Bearer token directly!")
            return f"Bearer:{access_token}"
    except Exception as e:
        print(f"  GET /api/me failed: {e}")
    
    return None


def get_valid_tokens(force_login: bool = False) -> dict:
    """Get valid tokens, refreshing or re-authorizing as needed."""
    
    tokens = load_tokens()
    
    if tokens and not force_login:
        # Check if we have refresh_token
        if "refresh_token" in tokens:
            print("Found saved refresh_token, refreshing access_token...")
            try:
                tokens = refresh_access_token(tokens["refresh_token"])
                save_tokens(tokens)
                return tokens
            except Exception as e:
                print(f"Refresh failed: {e}")
                print("Will re-authorize...")
    
    # Need to do full OAuth flow
    print("Starting OAuth authorization flow...")
    code = get_authorization_code()
    print(f"Got authorization code: {code[:20]}...")
    
    tokens = exchange_code_for_tokens(code)
    save_tokens(tokens)
    
    return tokens


def test_api_with_session(session_cookie: str) -> bool:
    """Test if session cookie works."""
    
    if session_cookie.startswith("Bearer:"):
        # Direct Bearer token
        token = session_cookie.replace("Bearer:", "")
        response = requests.get(
            f"{DG_BASE_URL}/api/locations/10/categories",
            headers={"Authorization": f"Bearer {token}"},
            params={"flat": "true", "include_archived": "true"}
        )
    else:
        response = requests.get(
            f"{DG_BASE_URL}/api/locations/10/categories",
            cookies={"dg_session": session_cookie},
            params={"flat": "true", "include_archived": "true"}
        )
    
    if response.status_code == 200:
        data = response.json()
        print(f"API test successful! Got {len(data)} categories.")
        return True
    else:
        print(f"API test failed: {response.status_code} - {response.text[:200]}")
        return False


def main():
    force_login = "--login" in sys.argv
    
    print("=" * 50)
    print("DialogGauge OAuth Authentication")
    print("=" * 50)
    
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        print("\n" + "=" * 50)
        print("SETUP REQUIRED")
        print("=" * 50)
        print("""
To use OAuth 2.0, you need Google OAuth credentials:

1. Go to https://console.cloud.google.com/apis/credentials
2. Create a project (or select existing)
3. Create OAuth 2.0 Client ID:
   - Application type: Desktop app
   - Name: DialogGauge CLI
4. Download or copy:
   - Client ID
   - Client Secret
5. Edit this file and set:
   - GOOGLE_CLIENT_ID = "your-client-id"
   - GOOGLE_CLIENT_SECRET = "your-secret"
6. In OAuth consent screen, add your email as test user

Note: The credentials in credentials.json/cred.json in this folder
may work if they're for the same Google Cloud project that
DialogGauge uses.
""")
        
        # Try to load from existing credentials.json
        creds_file = BASE_DIR / "credentials.json"
        if creds_file.exists():
            print(f"\nFound {creds_file}, attempting to use...")
            with open(creds_file) as f:
                creds = json.load(f)
            if "installed" in creds:
                print(f"Client ID: {creds['installed']['client_id'][:30]}...")
                print("\nTo use these credentials, copy them to this script.")
        
        return
    
    tokens = get_valid_tokens(force_login)
    
    print(f"\nAccess token: {tokens.get('access_token', 'N/A')[:50]}...")
    print(f"Refresh token: {'Yes' if tokens.get('refresh_token') else 'No'}")
    print(f"Expires in: {tokens.get('expires_in', 'N/A')} seconds")
    
    # Try to get DialogGauge session
    session = get_dg_session_with_google_token(tokens["access_token"])
    
    if session:
        print(f"\nGot DialogGauge session!")
        test_api_with_session(session)
    else:
        print("\nCouldn't automatically get DialogGauge session.")
        print("The API might require a different authentication method.")
        print("\nTry these options:")
        print("1. Check if API accepts Bearer token directly")
        print("2. Look at browser Network tab during login to see exact flow")
        print("3. Ask DialogGauge team for API documentation")


if __name__ == "__main__":
    main()
