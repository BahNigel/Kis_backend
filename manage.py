#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    # Ensure project root is on PYTHONPATH
    current_path = os.path.dirname(os.path.abspath(__file__))
    if current_path not in sys.path:
        sys.path.insert(0, current_path)

    # Set default settings module (local/dev)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Make sure it's installed and "
            "available on your PYTHONPATH. Activate your virtualenv if needed."
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
