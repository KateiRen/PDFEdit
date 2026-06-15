from __future__ import annotations

import sys
from pathlib import Path

BLOCKED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


def main() -> int:
    blocked_files = [
        f for f in sys.argv[1:] if Path(f).suffix.lower() in BLOCKED_EXTENSIONS
    ]

    if not blocked_files:
        return 0

    print("Blocked: committing PDF/image files is not allowed:")
    for file_path in blocked_files:
        print(f"  - {file_path}")
    print("Please remove these files from the commit.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
