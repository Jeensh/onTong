"""ontong CLI entry. Run via `python -m backend.cli` or `ontong` (after poetry install)."""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(prog="ontong", description="onTong administration CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    from backend.cli.migrate import register_migrate
    register_migrate(sub)

    args = parser.parse_args()
    if hasattr(args, "func"):
        return args.func(args) or 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
