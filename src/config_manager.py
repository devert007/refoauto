#!/usr/bin/env python3
"""
Configuration Manager for Multi-Client Setup

Manages configuration for different clients (hortman, milena, etc.)
Reads from clients_config.json and .env file.

Usage:
    from src.config_manager import get_client_config, get_active_client

    config = get_client_config()  # Gets active client config
    config = get_client_config("milena")  # Gets specific client config

    # Access paths
    scripts_dir = config.scripts_dir
    data_dir = config.data_dir
    location_ids = config.get_location_ids()
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional


class ClientConfig:
    """Configuration for a single client."""

    def __init__(self, client_name: str, config_dict: dict, project_root: Path):
        self.client_name = client_name
        self.enabled = config_dict.get("enabled", True)
        self.display_name = config_dict.get("display_name", client_name.title())

        # Paths
        base_path = config_dict.get("base_path", f"src/{client_name}")
        self.base_dir = project_root / base_path
        self.scripts_dir = self.base_dir / "scripts"
        self.models_dir = self.base_dir / "models"
        self.tests_dir = self.base_dir / "tests"
        self.data_dir = self.base_dir / "data"
        self.data_output_dir = self.data_dir / "output"
        self.data_input_dir = self.data_dir / "input"
        self.data_api_dir = self.data_dir / "api"
        self.docs_dir = self.base_dir / "docs"
        self.config_dir = self.base_dir / "config"

        # Locations
        self.locations = config_dict.get("locations", [])
        self.branch_to_location = config_dict.get("branch_to_location", {})

    def get_location_ids(self) -> List[int]:
        """Get all location IDs for this client."""
        return [loc["location_id"] for loc in self.locations if loc.get("location_id")]

    def get_location_by_branch(self, branch: str) -> Optional[int]:
        """Get location ID by branch name."""
        return self.branch_to_location.get(branch)

    def get_branch_by_location(self, location_id: int) -> Optional[str]:
        """Get branch name by location ID."""
        for branch, loc_id in self.branch_to_location.items():
            if loc_id == location_id:
                return branch
        return None

    def get_location_info(self, location_id: int) -> Optional[Dict]:
        """Get full location info by ID."""
        for loc in self.locations:
            if loc.get("location_id") == location_id:
                return loc
        return None

    def __repr__(self):
        return f"ClientConfig(name={self.client_name}, locations={len(self.locations)})"


class ConfigManager:
    """Manages configuration for all clients."""

    def __init__(self, config_file: Optional[Path] = None):
        # Find project root (directory containing clients_config.json)
        if config_file:
            self.config_file = config_file
            self.project_root = config_file.parent
        else:
            # Search for config file starting from current directory
            current = Path(__file__).resolve().parent.parent
            while current != current.parent:
                config_path = current / "clients_config.json"
                if config_path.exists():
                    self.config_file = config_path
                    self.project_root = current
                    break
                current = current.parent
            else:
                raise FileNotFoundError(
                    "clients_config.json not found. "
                    "Please create it in your project root."
                )

        # Load configuration
        with open(self.config_file, encoding="utf-8") as f:
            self.raw_config = json.load(f)

        # Load .env if exists
        self._load_env()

        # Parse clients
        self.clients: Dict[str, ClientConfig] = {}
        for client_name, client_data in self.raw_config.get("clients", {}).items():
            self.clients[client_name] = ClientConfig(
                client_name,
                client_data,
                self.project_root
            )

        # Determine active client
        self.active_client_name = self._get_active_client_name()

    def _load_env(self):
        """Load .env file if it exists."""
        env_file = self.project_root / ".env"
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if "=" in line:
                            key, value = line.split("=", 1)
                            os.environ[key.strip()] = value.strip()

    def _get_active_client_name(self) -> str:
        """Determine which client is active."""
        # Priority: env var > config file > first enabled client
        active = os.getenv("ACTIVE_CLIENT")
        if active and active in self.clients:
            return active

        active = self.raw_config.get("active_client")
        if active and active in self.clients:
            return active

        # Fall back to first enabled client
        for name, config in self.clients.items():
            if config.enabled:
                return name

        raise ValueError("No active client configured")

    def get_client(self, client_name: Optional[str] = None) -> ClientConfig:
        """Get configuration for a specific client or the active one."""
        if client_name is None:
            client_name = self.active_client_name

        if client_name not in self.clients:
            raise ValueError(
                f"Client '{client_name}' not found. "
                f"Available clients: {list(self.clients.keys())}"
            )

        config = self.clients[client_name]
        if not config.enabled:
            print(f"Warning: Client '{client_name}' is disabled in config")

        return config

    def list_clients(self) -> List[str]:
        """List all available client names."""
        return list(self.clients.keys())

    def list_enabled_clients(self) -> List[str]:
        """List all enabled client names."""
        return [name for name, config in self.clients.items() if config.enabled]


# Global config manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get or create the global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_client_config(client_name: Optional[str] = None) -> ClientConfig:
    """
    Get configuration for a client.

    Args:
        client_name: Name of client (e.g., "hortman", "milena").
                    If None, returns active client config.

    Returns:
        ClientConfig instance with paths and location info
    """
    return get_config_manager().get_client(client_name)


def get_active_client() -> str:
    """Get the name of the active client."""
    return get_config_manager().active_client_name


def list_clients() -> List[str]:
    """List all available client names."""
    return get_config_manager().list_clients()


def list_enabled_clients() -> List[str]:
    """List all enabled client names."""
    return get_config_manager().list_enabled_clients()


if __name__ == "__main__":
    # Test/demo
    print("=== Configuration Manager Demo ===\n")

    manager = get_config_manager()
    print(f"Project root: {manager.project_root}")
    print(f"Active client: {manager.active_client_name}")
    print(f"Available clients: {manager.list_clients()}")
    print(f"Enabled clients: {manager.list_enabled_clients()}\n")

    # Show active client config
    config = get_client_config()
    print(f"Active Client: {config.display_name}")
    print(f"  Base dir: {config.base_dir}")
    print(f"  Scripts dir: {config.scripts_dir}")
    print(f"  Data dir: {config.data_dir}")
    print(f"  Location IDs: {config.get_location_ids()}")
    print(f"  Locations:")
    for loc in config.locations:
        print(f"    - {loc['name']} (ID: {loc['location_id']}, branch: {loc['branch']})")
