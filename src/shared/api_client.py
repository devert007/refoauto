"""
Shared DialogGauge API client.

Handles authentication (Playwright OAuth), session management,
and all API requests (GET, POST, PUT, DELETE).
"""

import json
import os
import time
from pathlib import Path

import requests


# API Configuration
API_BASE_URL = "https://dialoggauge.yma.health/api"
DG_BASE_URL = "https://dialoggauge.yma.health"
COOKIE_REFRESH_BUFFER = 3600  # Refresh 1 hour before expiry
DEFAULT_MAX_AGE = 604800  # 7 days


class DGApiClient:
    """DialogGauge API client with automatic session management."""

    def __init__(
        self,
        cookie_file: Path | None = None,
        playwright_profile: Path | None = None,
    ):
        project_root = Path(__file__).resolve().parent.parent.parent
        self.cookie_file = cookie_file or (project_root / "config" / ".dg_session.json")
        self.playwright_profile = playwright_profile or (project_root / ".playwright_profile")
        self._session_cookie: str | None = None

        # Ensure config directory exists
        self.cookie_file.parent.mkdir(parents=True, exist_ok=True)

    # === Session Management ===

    def load_session(self) -> dict | None:
        """Load saved session from file."""
        if not self.cookie_file.exists():
            return None
        try:
            with open(self.cookie_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def save_session(self, cookie_value: str, max_age: int = DEFAULT_MAX_AGE) -> None:
        """Save session cookie to file."""
        data = {
            "dg_session": cookie_value,
            "expires_at": int(time.time()) + max_age,
            "saved_at": int(time.time()),
        }
        with open(self.cookie_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Session saved to {self.cookie_file}")

    @staticmethod
    def session_is_valid(session: dict | None) -> bool:
        """Check if session is still valid."""
        if not session:
            return False
        cookie = session.get("dg_session")
        expires_at = session.get("expires_at", 0)
        if not cookie:
            return False
        return expires_at > time.time() + COOKIE_REFRESH_BUFFER

    def get_session_via_playwright(self, headless: bool = False) -> str:
        """Get dg_session via Playwright browser automation."""
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
            browser = p.chromium.launch_persistent_context(
                user_data_dir=str(self.playwright_profile),
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )

            page = browser.new_page()

            print("Navigating to DialogGauge...")
            page.goto(f"{DG_BASE_URL}/app", wait_until="networkidle", timeout=30000)

            current_url = page.url
            if "/app" in current_url and "login" not in current_url:
                print("Already logged in!")
            else:
                print("Starting Google OAuth flow...")

                try:
                    login_btn = page.locator("text=Google").first
                    if login_btn.is_visible(timeout=3000):
                        login_btn.click()
                except Exception:
                    pass

                print("Waiting for Google authentication...")
                print("(If browser opened, please log in with your Google account)")

                try:
                    page.wait_for_url(f"{DG_BASE_URL}/app**", timeout=120000)
                    print("Authentication successful!")
                except Exception as e:
                    print(f"Timeout waiting for authentication: {e}")
                    print("Please complete login manually in the browser window.")
                    input("Press Enter after logging in...")

            cookies = browser.cookies()
            browser.close()

        for cookie in cookies:
            if cookie.get("name") == "dg_session":
                cookie_value = cookie["value"]
                expires = cookie.get("expires", 0)
                max_age = int(expires - time.time()) if expires > 0 else DEFAULT_MAX_AGE
                self.save_session(cookie_value, max_age)
                return cookie_value

        raise RuntimeError("Failed to get dg_session cookie after login")

    def get_session(self, force_refresh: bool = False) -> str:
        """
        Get valid dg_session cookie.
        Priority: 1. env DG_SESSION, 2. saved file, 3. Playwright
        """
        if not force_refresh:
            env_session = os.getenv("DG_SESSION")
            if env_session:
                print("Using session from DG_SESSION environment variable")
                return env_session

            saved = self.load_session()
            if self.session_is_valid(saved):
                print("Using saved session from file")
                return saved["dg_session"]
            elif saved:
                print("Saved session expired, refreshing...")

        return self.get_session_via_playwright()

    def check_auth_status(self) -> dict:
        """Check current auth status without triggering refresh."""
        saved = self.load_session()
        is_valid = self.session_is_valid(saved)
        return {
            "valid": is_valid,
            "expires_at": saved.get("expires_at") if saved else None,
            "saved_at": saved.get("saved_at") if saved else None,
        }

    # === HTTP Methods ===

    def _ensure_session(self) -> str:
        """Get or refresh session cookie."""
        if self._session_cookie:
            return self._session_cookie
        self._session_cookie = self.get_session()
        return self._session_cookie

    def _headers(self) -> dict:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _cookies(self, session_cookie: str) -> dict:
        return {"dg_session": session_cookie}

    def api_get(
        self,
        endpoint: str,
        params: dict | None = None,
        session_cookie: str | None = None,
    ) -> list[dict] | dict:
        """Make authenticated API GET request with auto-refresh on 401."""
        if session_cookie is None:
            session_cookie = self._ensure_session()

        url = f"{API_BASE_URL}{endpoint}"
        print(f"\nFetching from: {url}")
        if params:
            print(f"Parameters: {params}")

        response = requests.get(
            url, params=params, headers=self._headers(), cookies=self._cookies(session_cookie)
        )
        print(f"Status Code: {response.status_code}")

        if response.status_code == 401:
            print("Session expired, refreshing...")
            session_cookie = self.get_session(force_refresh=True)
            self._session_cookie = session_cookie
            response = requests.get(
                url, params=params, headers=self._headers(), cookies=self._cookies(session_cookie)
            )
            print(f"Retry Status Code: {response.status_code}")

        if response.status_code != 200:
            print(f"Error: {response.text}")
            response.raise_for_status()

        return response.json()

    def api_post(
        self,
        endpoint: str,
        data: dict,
        session_cookie: str | None = None,
    ) -> dict:
        """Make authenticated API POST request with auto-refresh on 401."""
        if session_cookie is None:
            session_cookie = self._ensure_session()

        url = f"{API_BASE_URL}{endpoint}"
        print(f"\nPOST to: {url}")
        print(f"Data: {json.dumps(data, ensure_ascii=False)}")

        response = requests.post(
            url, json=data, headers=self._headers(), cookies=self._cookies(session_cookie)
        )
        print(f"Status Code: {response.status_code}")

        if response.status_code == 401:
            print("Session expired, refreshing...")
            session_cookie = self.get_session(force_refresh=True)
            self._session_cookie = session_cookie
            response = requests.post(
                url, json=data, headers=self._headers(), cookies=self._cookies(session_cookie)
            )
            print(f"Retry Status Code: {response.status_code}")

        if response.status_code not in (200, 201):
            print(f"Error: {response.text}")
            response.raise_for_status()

        return response.json()

    def api_put(
        self,
        endpoint: str,
        data: dict,
        session_cookie: str | None = None,
    ) -> dict:
        """Make authenticated API PUT request with auto-refresh on 401."""
        if session_cookie is None:
            session_cookie = self._ensure_session()

        url = f"{API_BASE_URL}{endpoint}"
        print(f"\nPUT to: {url}")
        print(f"Data: {json.dumps(data, ensure_ascii=False)}")

        response = requests.put(
            url, json=data, headers=self._headers(), cookies=self._cookies(session_cookie)
        )
        print(f"Status Code: {response.status_code}")

        if response.status_code == 401:
            print("Session expired, refreshing...")
            session_cookie = self.get_session(force_refresh=True)
            self._session_cookie = session_cookie
            response = requests.put(
                url, json=data, headers=self._headers(), cookies=self._cookies(session_cookie)
            )
            print(f"Retry Status Code: {response.status_code}")

        if response.status_code not in (200, 201):
            print(f"Error: {response.text}")
            response.raise_for_status()

        return response.json()

    def api_delete(
        self,
        endpoint: str,
        session_cookie: str | None = None,
    ) -> dict | None:
        """Make authenticated API DELETE request with auto-refresh on 401."""
        if session_cookie is None:
            session_cookie = self._ensure_session()

        url = f"{API_BASE_URL}{endpoint}"
        print(f"\nDELETE: {url}")

        response = requests.delete(
            url, headers=self._headers(), cookies=self._cookies(session_cookie)
        )
        print(f"Status Code: {response.status_code}")

        if response.status_code == 401:
            print("Session expired, refreshing...")
            session_cookie = self.get_session(force_refresh=True)
            self._session_cookie = session_cookie
            response = requests.delete(
                url, headers=self._headers(), cookies=self._cookies(session_cookie)
            )
            print(f"Retry Status Code: {response.status_code}")

        if response.status_code not in (200, 204):
            print(f"Error: {response.text}")
            response.raise_for_status()

        if response.status_code == 204:
            return None
        return response.json()

    # === High-Level API Methods ===

    def get_categories(
        self,
        location_id: int,
        flat: bool = True,
        include_archived: bool = True,
    ) -> list[dict]:
        """Fetch categories for a location."""
        params = {
            "flat": str(flat).lower(),
            "include_archived": str(include_archived).lower(),
        }
        return self.api_get(f"/locations/{location_id}/categories", params=params)

    def get_services(
        self,
        location_id: int,
        include_archived: bool = True,
    ) -> list[dict]:
        """Fetch services for a location."""
        params = {"include_archived": str(include_archived).lower()}
        return self.api_get(f"/locations/{location_id}/services", params=params)

    def get_practitioners(
        self,
        location_id: int,
        include_archived: bool = True,
    ) -> list[dict]:
        """Fetch practitioners for a location."""
        params = {"include_archived": str(include_archived).lower()}
        return self.api_get(f"/locations/{location_id}/practitioners", params=params)

    def create_category(
        self,
        location_id: int,
        name: str,
        parent_id: int | None = None,
        description: str | None = None,
        is_visible_to_ai: bool = True,
    ) -> dict:
        """Create a new category."""
        data = {
            "location_id": location_id,
            "name": {"en": name},
            "is_visible_to_ai": is_visible_to_ai,
        }
        if parent_id is not None:
            data["parent_id"] = parent_id
        if description:
            data["description_i18n"] = {"en": description}
        return self.api_post(f"/locations/{location_id}/categories", data=data)

    def create_service(
        self,
        location_id: int,
        name: str,
        category_id: int | None = None,
        description: str | None = None,
        duration_minutes: int | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        price_note: str | None = None,
        is_visible_to_ai: bool = True,
    ) -> dict:
        """Create a new service."""
        data = {
            "location_id": location_id,
            "name": {"en": name},
            "is_visible_to_ai": is_visible_to_ai,
        }
        if category_id is not None:
            data["category_id"] = category_id
        if description:
            data["description"] = {"en": description}
        if duration_minutes is not None:
            data["duration_minutes"] = duration_minutes
        if price_min is not None:
            data["price_min"] = price_min
        if price_max is not None:
            data["price_max"] = price_max
        if price_note:
            data["price_note"] = {"en": price_note}
        return self.api_post(f"/locations/{location_id}/services", data=data)

    def update_service(
        self,
        location_id: int,
        service_id: int,
        data: dict,
    ) -> dict:
        """Update an existing service."""
        return self.api_put(f"/locations/{location_id}/services/{service_id}", data=data)

    def delete_service(
        self,
        location_id: int,
        service_id: int,
    ) -> dict | None:
        """Delete a service."""
        return self.api_delete(f"/locations/{location_id}/services/{service_id}")

    def create_service_practitioner(
        self,
        location_id: int,
        service_id: int,
        practitioner_id: int,
    ) -> dict:
        """Link a practitioner to a service."""
        data = {
            "service_id": service_id,
            "practitioner_id": practitioner_id,
        }
        return self.api_post(f"/locations/{location_id}/service-practitioners", data=data)


# Module-level convenience: default client instance
_default_client: DGApiClient | None = None


def get_default_client() -> DGApiClient:
    """Get or create the default API client instance."""
    global _default_client
    if _default_client is None:
        _default_client = DGApiClient()
    return _default_client
