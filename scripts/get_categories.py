#!/usr/bin/env python3
"""
Script to fetch data from DialogGauge API (categories, services, practitioners).

Authentication: Automatic via Playwright (Google OAuth).
First run: Opens browser for Google login (one time).
Subsequent runs: Reuses saved session, auto-refreshes if expired.

Requirements:
    pip install requests playwright
    python -m playwright install chromium

Usage:
    python scripts/get_categories.py
    python scripts/get_categories.py --services
    python scripts/get_categories.py --all
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
LOCATION_ID = 17

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


def _api_request(
    endpoint: str,
    params: dict | None = None,
    session_cookie: str | None = None,
) -> list[dict]:
    """
    Make authenticated API GET request.
    
    Args:
        endpoint: API endpoint (e.g., "/locations/10/categories")
        params: Query parameters
        session_cookie: Optional session cookie (auto-fetched if not provided)
    
    Returns:
        JSON response
    """
    if session_cookie is None:
        session_cookie = get_session()
    
    url = f"{API_BASE_URL}{endpoint}"
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    
    cookies = {"dg_session": session_cookie}
    
    print(f"\nFetching from: {url}")
    if params:
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


def _api_post_request(
    endpoint: str,
    data: dict,
    session_cookie: str | None = None,
) -> dict:
    """
    Make authenticated API POST request.
    
    Args:
        endpoint: API endpoint (e.g., "/locations/17/categories")
        data: JSON body to send
        session_cookie: Optional session cookie (auto-fetched if not provided)
    
    Returns:
        JSON response
    """
    if session_cookie is None:
        session_cookie = get_session()
    
    url = f"{API_BASE_URL}{endpoint}"
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    
    cookies = {"dg_session": session_cookie}
    
    print(f"\nPOST to: {url}")
    print(f"Data: {json.dumps(data, ensure_ascii=False)}")
    
    response = requests.post(url, json=data, headers=headers, cookies=cookies)
    
    print(f"Status Code: {response.status_code}")
    
    # Handle expired session
    if response.status_code == 401:
        print("Session expired, refreshing...")
        session_cookie = get_session(force_refresh=True)
        response = requests.post(
            url,
            json=data,
            headers=headers,
            cookies={"dg_session": session_cookie},
        )
        print(f"Retry Status Code: {response.status_code}")
    
    if response.status_code not in (200, 201):
        print(f"Error: {response.text}")
        response.raise_for_status()
    
    return response.json()


def create_category(
    name: str,
    location_id: int = LOCATION_ID,
    parent_id: int | None = None,
    description: str | None = None,
    is_visible_to_ai: bool = True,
    session_cookie: str | None = None,
) -> dict:
    """
    Create a new category via API.
    
    Args:
        name: Category name (English)
        location_id: Location ID
        parent_id: Parent category ID (None for root category)
        description: Category description (optional)
        is_visible_to_ai: Whether category is visible to AI
        session_cookie: Optional session cookie (auto-fetched if not provided)
    
    Returns:
        Created category dict
    """
    data = {
        "location_id": location_id,
        "name": {"en": name},
        "is_visible_to_ai": is_visible_to_ai,
    }
    
    if parent_id is not None:
        data["parent_id"] = parent_id
    
    if description:
        data["description_i18n"] = {"en": description}
    
    return _api_post_request(
        f"/locations/{location_id}/categories",
        data=data,
        session_cookie=session_cookie,
    )


def create_service(
    name: str,
    location_id: int = LOCATION_ID,
    category_id: int | None = None,
    description: str | None = None,
    duration_minutes: int | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    price_note: str | None = None,
    is_visible_to_ai: bool = True,
    session_cookie: str | None = None,
) -> dict:
    """
    Create a new service via API.
    
    Args:
        name: Service name (English)
        location_id: Location ID
        category_id: Category ID (optional)
        description: Service description (optional)
        duration_minutes: Duration in minutes (optional)
        price_min: Minimum price (optional)
        price_max: Maximum price (optional)
        price_note: Price note (optional)
        is_visible_to_ai: Whether service is visible to AI
        session_cookie: Optional session cookie (auto-fetched if not provided)
    
    Returns:
        Created service dict
    """
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
    
    return _api_post_request(
        f"/locations/{location_id}/services",
        data=data,
        session_cookie=session_cookie,
    )


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
    params = {
        "flat": str(flat).lower(),
        "include_archived": str(include_archived).lower(),
    }
    
    return _api_request(
        f"/locations/{location_id}/categories",
        params=params,
        session_cookie=session_cookie,
    )


def get_services(
    location_id: int = LOCATION_ID,
    include_archived: bool = True,
    session_cookie: str | None = None,
) -> list[dict]:
    """
    Fetch services from the API.
    
    Args:
        location_id: Location ID to fetch services for
        include_archived: If True, include archived services
        session_cookie: Optional session cookie (auto-fetched if not provided)
    
    Returns:
        List of service dictionaries
    """
    params = {
        "include_archived": str(include_archived).lower(),
    }
    
    return _api_request(
        f"/locations/{location_id}/services",
        params=params,
        session_cookie=session_cookie,
    )


def get_practitioners(
    location_id: int = LOCATION_ID,
    include_archived: bool = True,
    session_cookie: str | None = None,
) -> list[dict]:
    """
    Fetch practitioners from the API.
    
    Args:
        location_id: Location ID to fetch practitioners for
        include_archived: If True, include archived practitioners
        session_cookie: Optional session cookie (auto-fetched if not provided)
    
    Returns:
        List of practitioner dictionaries
    """
    params = {
        "include_archived": str(include_archived).lower(),
    }
    
    return _api_request(
        f"/locations/{location_id}/practitioners",
        params=params,
        session_cookie=session_cookie,
    )


def main():
    import sys
    
    # Test POST request to create category
    if "--create-test" in sys.argv:
        print("=" * 60)
        print("TESTING: CREATE CATEGORY")
        print("=" * 60)
        
        # Get location_id from args or use default 17 (from user's example)
        location_id = 17
        for arg in sys.argv:
            if arg.startswith("--location="):
                location_id = int(arg.split("=")[1])
        
        # Get category name from args or use test name
        category_name = "TEST CATEGORY (can be deleted)"
        for arg in sys.argv:
            if arg.startswith("--name="):
                category_name = arg.split("=", 1)[1]
        
        print(f"\nCreating category:")
        print(f"  Location ID: {location_id}")
        print(f"  Name: {category_name}")
        
        try:
            result = create_category(
                name=category_name,
                location_id=location_id,
            )
            print("\n✓ SUCCESS! Created category:")
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"\n✗ FAILED: {e}")
        
        return
    
    fetch_services = "--services" in sys.argv or "--all" in sys.argv
    fetch_practitioners = "--practitioners" in sys.argv or "--all" in sys.argv
    fetch_categories = "--categories" in sys.argv or "--all" in sys.argv or (
        not fetch_services and not fetch_practitioners
    )
    
    # Fetch categories
    if fetch_categories:
        print("=" * 60)
        print("FETCHING CATEGORIES")
        print("=" * 60)
        categories = get_categories()
        
        print(f"\nFetched {len(categories)} categories:")
        for cat in categories:
            name = cat.get("name_i18n", {}).get("en", "Unknown")
            is_archived = cat.get("is_archived", False)
            services_count = cat.get("services_count", 0)
            status = " [ARCHIVED]" if is_archived else ""
            print(f"  - {cat['id']}: {name} ({services_count} services){status}")
        
        output_path = DATA_API_DIR / "categories_api_response.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(categories, f, ensure_ascii=False, indent=2)
        print(f"\nSaved to: {output_path}")
    
    # Fetch services
    if fetch_services:
        print("\n" + "=" * 60)
        print("FETCHING SERVICES")
        print("=" * 60)
        services = get_services()
        
        print(f"\nFetched {len(services)} services:")
        archived_count = sum(1 for s in services if s.get("is_archived", False))
        print(f"  - Active: {len(services) - archived_count}")
        print(f"  - Archived: {archived_count}")
        
        # Show first 10
        for svc in services[:10]:
            name = svc.get("name_i18n", {}).get("en", "Unknown")
            is_archived = svc.get("is_archived", False)
            status = " [ARCHIVED]" if is_archived else ""
            print(f"  - {svc['id']}: {name[:50]}...{status}" if len(name) > 50 else f"  - {svc['id']}: {name}{status}")
        if len(services) > 10:
            print(f"  ... and {len(services) - 10} more")
        
        output_path = DATA_API_DIR / "services_api_response.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(services, f, ensure_ascii=False, indent=2)
        print(f"\nSaved to: {output_path}")
    
    # Fetch practitioners
    if fetch_practitioners:
        print("\n" + "=" * 60)
        print("FETCHING PRACTITIONERS")
        print("=" * 60)
        try:
            practitioners = get_practitioners()
            
            print(f"\nFetched {len(practitioners)} practitioners:")
            for pract in practitioners[:10]:
                name = pract.get("name", pract.get("name_i18n", {}).get("en", "Unknown"))
                print(f"  - {pract['id']}: {name}")
            if len(practitioners) > 10:
                print(f"  ... and {len(practitioners) - 10} more")
            
            output_path = DATA_API_DIR / "practitioners_api_response.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(practitioners, f, ensure_ascii=False, indent=2)
            print(f"\nSaved to: {output_path}")
        except Exception as e:
            print(f"Failed to fetch practitioners: {e}")
    
    print("\nDone!")


if __name__ == "__main__":
    main()
