#!/usr/bin/env python3
"""Check that Python files don't exceed max line count."""

import os
import sys
from pathlib import Path

MAX_LINES = int(os.getenv("MAX_FILE_LINES", "200"))
IGNORE_PATTERNS = ["__pycache__", ".git", "tests", "examples", "scripts"]


def should_check_file(filepath: Path) -> bool:
    if not filepath.suffix == ".py":
        return False
    parts = filepath.parts
    return not any(pattern in parts for pattern in IGNORE_PATTERNS)


def check_files() -> int:
    src_dir = Path("src")
    if not src_dir.exists():
        return 0

    errors = []
    for py_file in src_dir.rglob("*.py"):
        if not should_check_file(py_file):
            continue
        with open(py_file, "r", encoding="utf-8") as f:
            line_count = sum(1 for _ in f)
        if line_count > MAX_LINES:
            rel_path = py_file.relative_to(Path.cwd())
            errors.append(f"{rel_path}: {line_count} lines (max {MAX_LINES})")

    if errors:
        print("Files exceeding maximum line count:")
        for err in errors:
            print(f"  {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(check_files())

