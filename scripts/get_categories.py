#!/usr/bin/env python3
"""
Script to fetch categories from DialogGauge API.

Authentication: Automatic via Playwright (Google OAuth).
First run: Opens browser for Google login (one time).
Subsequent runs: Reuses saved session, auto-refreshes if expired.

Requirements:
    pip install requests playwright
    python -m playwright install chromium

Usage:
    python scripts/get_categories.py
"""

import json
import os
import time
from pathlib import Path

import requests

# Project paths
SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_API_DIR = PROJECT_ROOT / "data" / "api"

# Ensure directories exist
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
DATA_API_DIR.mkdir(parents=True, exist_ok=True)

COOKIE_FILE = CONFIG_DIR / ".dg_session.json"
PLAYWRIGHT_PROFILE = PROJECT_ROOT / ".playwright_profile"

# API Configuration
API_BASE_URL = "https://dialoggauge.yma.health/api"
DG_BASE_URL = "https://dialoggauge.yma.health"
LOCATION_ID = 10

# Cookie expires in 7 days (604800 seconds), refresh 1 hour before
COOKIE_REFRESH_BUFFER = 3600


def load_session() -> dict | None:
    """Load saved session from file."""
    if not COOKIE_FILE.exists():
        return None
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def save_session(cookie_value: str, max_age: int = 604800) -> None:
    """Save session cookie to file."""
    data = {
        "dg_session": cookie_value,
        "expires_at": int(time.time()) + max_age,
        "saved_at": int(time.time()),
    }
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Session saved to {COOKIE_FILE}")


def session_is_valid(session: dict | None) -> bool:
    """Check if session is still valid."""
    if not session:
        return False
    cookie = session.get("dg_session")
    expires_at = session.get("expires_at", 0)
    if not cookie:
        return False
    # Check if expired (with buffer)
    return expires_at > time.time() + COOKIE_REFRESH_BUFFER


def get_session_via_playwright(headless: bool = False) -> str:
    """
    Get dg_session via Playwright browser automation.
    
    Uses persistent browser profile so Google login is remembered.
    After first login, subsequent runs are automatic (no password needed).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright not installed. Run:\n"
            "  pip install playwright\n"
            "  python -m playwright install chromium"
        )
    
    print("\nStarting browser for authentication...")
    
    with sync_playwright() as p:
        # Use persistent context to remember Google login
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(PLAYWRIGHT_PROFILE),
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        
        page = browser.new_page()
        
        # Navigate to DialogGauge login
        print("Navigating to DialogGauge...")
        page.goto(f"{DG_BASE_URL}/app", wait_until="networkidle", timeout=30000)
        
        # Check if already logged in
        current_url = page.url
        if "/app" in current_url and "login" not in current_url:
            print("Already logged in!")
        else:
            # Need to go through OAuth
            print("Starting Google OAuth flow...")
            
            # Click login button if on login page
            try:
                # Wait for and click Google login button
                login_btn = page.locator("text=Google").first
                if login_btn.is_visible(timeout=3000):
                    login_btn.click()
            except Exception:
                # Maybe already redirecting to Google
                pass
            
            # Wait for Google login or auto-redirect
            print("Waiting for Google authentication...")
            print("(If browser opened, please log in with your Google account)")
            
            # Wait until we're back on DialogGauge /app
            try:
                page.wait_for_url(f"{DG_BASE_URL}/app**", timeout=120000)
                print("Authentication successful!")
            except Exception as e:
                print(f"Timeout waiting for authentication: {e}")
                print("Please complete login manually in the browser window.")
                input("Press Enter after logging in...")
        
        # Extract dg_session cookie
        cookies = browser.cookies()
        browser.close()
    
    # Find dg_session
    for cookie in cookies:
        if cookie.get("name") == "dg_session":
            cookie_value = cookie["value"]
            # Calculate max_age from expires
            expires = cookie.get("expires", 0)
            if expires > 0:
                max_age = int(expires - time.time())
            else:
                max_age = 604800  # Default 7 days
            save_session(cookie_value, max_age)
            return cookie_value
    
    raise RuntimeError("Failed to get dg_session cookie after login")


def get_session(force_refresh: bool = False) -> str:
    """
    Get valid dg_session cookie.
    
    Priority:
    1. Environment variable DG_SESSION
    2. Saved session from file (if valid)
    3. Get new session via Playwright
    """
    # Check env var
    if not force_refresh:
        env_session = os.getenv("DG_SESSION")
        if env_session:
            print("Using session from DG_SESSION environment variable")
            return env_session
        
        # Check saved session
        saved = load_session()
        if session_is_valid(saved):
            print("Using saved session from file")
            return saved["dg_session"]
        elif saved:
            print("Saved session expired, refreshing...")
    
    # Get new session via Playwright
    return get_session_via_playwright()


def get_categories(
    location_id: int = LOCATION_ID,
    flat: bool = True,
    include_archived: bool = True,
    session_cookie: str | None = None,
) -> list[dict]:
    """
    Fetch categories from the API.
    
    Args:
        location_id: Location ID to fetch categories for
        flat: If True, return flat list (no nested children)
        include_archived: If True, include archived categories
        session_cookie: Optional session cookie (auto-fetched if not provided)
    
    Returns:
        List of category dictionaries
    """
    if session_cookie is None:
        session_cookie = get_session()
    
    url = f"{API_BASE_URL}/locations/{location_id}/categories"
    
    params = {
        "flat": str(flat).lower(),
        "include_archived": str(include_archived).lower(),
    }
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    
    cookies = {"dg_session": session_cookie}
    
    print(f"\nFetching categories from: {url}")
    print(f"Parameters: {params}")
    
    response = requests.get(url, params=params, headers=headers, cookies=cookies)
    
    print(f"Status Code: {response.status_code}")
    
    # Handle expired session
    if response.status_code == 401:
        print("Session expired, refreshing...")
        session_cookie = get_session(force_refresh=True)
        response = requests.get(
            url,
            params=params,
            headers=headers,
            cookies={"dg_session": session_cookie},
        )
        print(f"Retry Status Code: {response.status_code}")
    
    if response.status_code != 200:
        print(f"Error: {response.text}")
        response.raise_for_status()
    
    return response.json()


def main():
    # Fetch categories
    categories = get_categories()
    
    # Print summary
    print(f"\nFetched {len(categories)} categories:")
    for cat in categories:
        name = cat.get("name_i18n", {}).get("en", "Unknown")
        is_archived = cat.get("is_archived", False)
        services_count = cat.get("services_count", 0)
        status = " [ARCHIVED]" if is_archived else ""
        print(f"  - {cat['id']}: {name} ({services_count} services){status}")
    
    # Save to file
    output_path = DATA_API_DIR / "categories_api_response.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)
    
    print(f"\nSaved response to: {output_path}")
    
    return categories


if __name__ == "__main__":
    main()
