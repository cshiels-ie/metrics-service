"""
Management command for dynamic settings (Phase 2).

This command provides CLI access to the dynamic settings system, allowing
administrators to view, modify, and manage settings without using the API.
"""

import json

from django.core.management.base import BaseCommand, CommandError

from apps.core.dynamic_settings import DYNAMIC_KEYS, get_dynamic_setting, set_dynamic_setting
from apps.core.models import Setting


class Command(BaseCommand):
    """Manage dynamic settings from the command line."""

    help = "Manage dynamic settings (Phase 2 runtime configuration)"

    def add_arguments(self, parser):
        """Define command arguments and subcommands."""
        subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to run")
        subparsers.required = True

        # Get setting value
        get_parser = subparsers.add_parser("get", help="Get the current value of a setting")
        get_parser.add_argument("key", help="Setting key name")

        # Set setting value
        set_parser = subparsers.add_parser("set", help="Set a new value for a setting")
        set_parser.add_argument("key", help="Setting key name")
        set_parser.add_argument("value", help="New value (JSON format)")
        set_parser.add_argument(
            "--category",
            default="",
            help="Category for organization (e.g., 'security', 'features')",
        )

        # List all settings
        list_parser = subparsers.add_parser("list", help="List all current settings")
        list_parser.add_argument(
            "--all-versions",
            action="store_true",
            help="Show all versions, not just latest",
        )

        # Show available dynamic keys
        subparsers.add_parser("keys", help="List all available dynamic keys")

        # Show setting history
        history_parser = subparsers.add_parser("history", help="Show version history for a setting")
        history_parser.add_argument("key", help="Setting key name")

        # Revert to previous version
        revert_parser = subparsers.add_parser("revert", help="Revert a setting to a previous version")
        revert_parser.add_argument("key", help="Setting key name")
        revert_parser.add_argument("version", type=int, help="Version number to revert to")

    def handle(self, *args, **options):
        """Handle the command execution."""
        subcommand = options["subcommand"]

        if subcommand == "get":
            self.handle_get(options["key"])
        elif subcommand == "set":
            self.handle_set(options["key"], options["value"], options["category"])
        elif subcommand == "list":
            self.handle_list(options["all_versions"])
        elif subcommand == "keys":
            self.handle_keys()
        elif subcommand == "history":
            self.handle_history(options["key"])
        elif subcommand == "revert":
            self.handle_revert(options["key"], options["version"])

    def handle_get(self, key: str):
        """Get the current value of a setting."""
        if key not in DYNAMIC_KEYS:
            raise CommandError(f"Key '{key}' is not a dynamic setting. Use 'keys' to see available keys.")

        value = get_dynamic_setting(key)
        if value is None:
            self.stdout.write(self.style.WARNING(f"Setting '{key}' not found (using static default)"))
            return

        setting = Setting.get_latest(key)
        if setting:
            self.stdout.write(self.style.SUCCESS(f"Key: {key}"))
            self.stdout.write(f"Value: {json.dumps(value, indent=2)}")
            self.stdout.write(f"Version: {setting.version}")
            self.stdout.write(f"Changed by: {setting.changed_by or 'system'}")
            self.stdout.write(f"Changed at: {setting.changed_at}")
            self.stdout.write(f"Source: {setting.source}")

    def handle_set(self, key: str, value_str: str, category: str):
        """Set a new value for a setting."""
        if key not in DYNAMIC_KEYS:
            raise CommandError(
                f"Key '{key}' is not a dynamic setting. Available keys: {', '.join(sorted(DYNAMIC_KEYS))}"
            )

        # Parse JSON value
        try:
            value = json.loads(value_str)
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON value: {e}")

        # Set the value
        try:
            set_dynamic_setting(key, value, source="management_command", category=category)
            self.stdout.write(self.style.SUCCESS(f"Successfully set {key} = {json.dumps(value)}"))

            # Show the new version
            setting = Setting.get_latest(key)
            if setting:
                self.stdout.write(f"New version: {setting.version}")
        except Exception as e:
            raise CommandError(f"Failed to set setting: {e}")

    def handle_list(self, all_versions: bool):
        """List all current settings."""
        if all_versions:
            settings = Setting.objects.all().order_by("key", "-version")
            self.stdout.write(self.style.SUCCESS("All settings (all versions):"))
        else:
            # Get only latest versions
            settings = []
            for key in DYNAMIC_KEYS:
                latest = Setting.get_latest(key)
                if latest:
                    settings.append(latest)

            if not settings:
                self.stdout.write(self.style.WARNING("No settings found"))
                return

            self.stdout.write(self.style.SUCCESS("Current settings (latest versions):"))

        # Display settings in a table format
        self.stdout.write("")
        self.stdout.write(f"{'Key':<30} {'Version':<8} {'Changed By':<20} {'Changed At'}")
        self.stdout.write("-" * 100)

        for setting in settings:
            changed_by = setting.changed_by.username if setting.changed_by else "system"
            self.stdout.write(
                f"{setting.key:<30} {setting.version:<8} {changed_by:<20} {setting.changed_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        self.stdout.write("")
        self.stdout.write(f"Total: {len(settings)} setting{'s' if len(settings) != 1 else ''}")

    def handle_keys(self):
        """List all available dynamic keys."""
        self.stdout.write(self.style.SUCCESS("Available dynamic keys:"))
        self.stdout.write("")
        for key in sorted(DYNAMIC_KEYS):
            # Check if this key has been set
            setting = Setting.get_latest(key)
            status = "✓ set" if setting else "  not set"
            self.stdout.write(f"  {status}  {key}")

        self.stdout.write("")
        self.stdout.write(f"Total: {len(DYNAMIC_KEYS)} dynamic key{'s' if len(DYNAMIC_KEYS) != 1 else ''}")

    def handle_history(self, key: str):
        """Show version history for a setting."""
        if key not in DYNAMIC_KEYS:
            raise CommandError(f"Key '{key}' is not a dynamic setting.")

        versions = Setting.get_history(key)
        if not versions.exists():
            self.stdout.write(self.style.WARNING(f"No history found for '{key}'"))
            return

        self.stdout.write(self.style.SUCCESS(f"Version history for '{key}':"))
        self.stdout.write("")
        self.stdout.write(f"{'Version':<8} {'Value':<40} {'Changed By':<20} {'Changed At'}")
        self.stdout.write("-" * 120)

        for version in versions:
            try:
                value = json.loads(version.value)
                value_str = json.dumps(value)
                if len(value_str) > 37:
                    value_str = value_str[:37] + "..."
            except json.JSONDecodeError:
                value_str = version.value[:40]

            changed_by = version.changed_by.username if version.changed_by else "system"
            self.stdout.write(
                f"{version.version:<8} {value_str:<40} {changed_by:<20} {version.changed_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        self.stdout.write("")
        self.stdout.write(f"Total: {versions.count()} version{'s' if versions.count() != 1 else ''}")

    def handle_revert(self, key: str, version: int):
        """Revert a setting to a previous version."""
        if key not in DYNAMIC_KEYS:
            raise CommandError(f"Key '{key}' is not a dynamic setting.")

        # Get the specified version
        old_version = Setting.get_version(key, version)
        if not old_version:
            raise CommandError(f"Version {version} not found for key '{key}'")

        # Get the value
        try:
            value = json.loads(old_version.value)
        except json.JSONDecodeError as e:
            raise CommandError(f"Failed to parse value from version {version}: {e}")

        # Create new version with old value
        try:
            set_dynamic_setting(key, value, source="management_command_revert", category=old_version.category)

            new_setting = Setting.get_latest(key)
            self.stdout.write(self.style.SUCCESS(f"Successfully reverted '{key}' to version {version}"))
            self.stdout.write(f"New version: {new_setting.version}")
            self.stdout.write(f"Value: {json.dumps(value, indent=2)}")
        except Exception as e:
            raise CommandError(f"Failed to revert setting: {e}")
