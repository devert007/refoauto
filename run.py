#!/usr/bin/env python3
"""
Universal script runner for multi-client setup.

Usage:
    python run.py [client_name] script_name [args...]
    python run.py [client_name] generate [options]
    python run.py web [--port PORT]

Examples:
    python run.py hortman get_categories --all
    python run.py milena process_data
    python run.py sync_with_api  # Uses active client
    python run.py web             # Start web UI on port 8080
    python run.py web --port 3000
    python run.py milena generate                     # Full generation
    python run.py hortman generate --categories-only  # Only categories
    python run.py milena generate --sync              # Generate + sync

Available scripts:
    - get_categories: Fetch categories/services/practitioners from API
    - sync_with_api: Sync local JSON with API IDs
    - process_data: Process raw input data
    - fix_locations: Fix data distribution across locations
    - print_quality: Print quality report
    - generate: Generate output JSON using Claude AI
    - web: Start web UI server
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.config_manager import get_client_config, list_clients


def print_usage():
    print(__doc__)
    print("\nAvailable clients:")
    for client in list_clients():
        print(f"  - {client}")
    print("\nCurrent working directory:", os.getcwd())


def main():
    if len(sys.argv) < 2:
        print_usage()
        return 1

    args = sys.argv[1:]

    # Special command: web server
    if args[0] == "web":
        web_args = [sys.executable, str(project_root / "web" / "server.py")] + args[1:]
        import subprocess
        env = os.environ.copy()
        env["PYTHONPATH"] = str(project_root)
        result = subprocess.run(web_args, env=env)
        return result.returncode

    # Special command: generate (requires client name before or uses active)
    # Handle: "run.py milena generate ..." or "run.py generate ..."
    all_clients = list_clients()
    if args[0] in all_clients and len(args) > 1 and args[1] == "generate":
        gen_args = [sys.executable, str(project_root / "src" / "shared" / "generate_pipeline.py"), args[0]] + args[2:]
        import subprocess
        env = os.environ.copy()
        env["PYTHONPATH"] = str(project_root)
        result = subprocess.run(gen_args, env=env)
        return result.returncode
    elif args[0] == "generate":
        from src.config_manager import get_active_client
        active = get_active_client()
        gen_args = [sys.executable, str(project_root / "src" / "shared" / "generate_pipeline.py"), active] + args[1:]
        import subprocess
        env = os.environ.copy()
        env["PYTHONPATH"] = str(project_root)
        result = subprocess.run(gen_args, env=env)
        return result.returncode

    # Determine client and script
    client_name = None
    script_name = None

    if args[0] in all_clients:
        # Explicit client specified
        client_name = args[0]
        if len(args) < 2:
            print(f"Error: No script specified for client '{client_name}'")
            print_usage()
            return 1
        script_name = args[1]
        script_args = args[2:]
    else:
        # Use active client
        script_name = args[0]
        script_args = args[1:]

    # Get client config
    try:
        config = get_client_config(client_name)
    except Exception as e:
        print(f"Error loading client config: {e}")
        return 1

    print(f"Using client: {config.display_name} ({config.client_name})")
    print(f"Base directory: {config.base_dir}")
    print(f"Script: {script_name}")
    print()

    # Map script names to files
    script_map = {
        "get_categories": "get_categories.py",
        "sync_with_api": "sync_with_api.py",
        "process_data": "process_data.py",
        "fix_locations": "fix_locations.py",
        "print_quality": "print_quality.py",
        "regenerate_data": "regenerate_data.py",
        "parse_practitioners": "parse_practitioners_sheet.py",
        "merge_descriptions": "merge_descriptions.py",
        "generate_categories": "generate_categories.py",
        "translate": "translate.py",
        "delete_duplicates": "delete_duplicates.py",
    }

    script_file = script_map.get(script_name, f"{script_name}.py")
    script_path = config.scripts_dir / script_file

    if not script_path.exists():
        print(f"Error: Script not found: {script_path}")
        print(f"\nAvailable scripts in {config.scripts_dir}:")
        for f in config.scripts_dir.glob("*.py"):
            if f.name != "__init__.py":
                print(f"  - {f.stem}")
        return 1

    # Change to client directory so relative paths work
    os.chdir(config.base_dir)

    # Execute script with project root in PYTHONPATH
    print(f"Executing: {script_path}")
    print(f"Working directory: {os.getcwd()}")
    print("-" * 60)

    cmd_args = [sys.executable, str(script_path)] + script_args

    import subprocess
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)
    result = subprocess.run(cmd_args, env=env)

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
