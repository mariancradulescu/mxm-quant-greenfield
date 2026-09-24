#!/usr/bin/env python3
"""Pydroid single-file entry point for the read-only crossalign M5 capture."""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
REQUIRED = "3.20.1"
PLAN = Path("data/CROSSALIGN_FOUR_SYMBOL_M5_CAPTURE_PLAN_V1.json")


def package_root():
    """Locate the extracted package even under Pydroid's exec(open(...)) runner."""
    candidates = (
        globals().get("mainpyfile"),
        globals().get("__file__"),
        sys.argv[0],
    )
    for candidate in candidates:
        if not candidate:
            continue
        parent = Path(candidate).expanduser().resolve().parent
        if (parent / PLAN).is_file() and (parent / "m6").is_dir():
            return parent
    current = Path.cwd().resolve()
    if (current / PLAN).is_file() and (current / "m6").is_dir():
        return current
    raise SystemExit("[PACKAGE ERROR] Extract the ZIP and run this root-level file from the extracted package.")


ROOT = package_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
REQ = ROOT / "tools" / "requirements-m6-capture.txt"


def runtime_dependency_status():
    try:
        actual = package_version("protobuf")
    except PackageNotFoundError:
        actual = None
    return {
        "ready": actual == REQUIRED,
        "protobuf": actual,
        "required": REQUIRED,
        "cryptography_required": False,
        "rust_required": False,
    }


def main():
    status = runtime_dependency_status()
    if not status["ready"]:
        result = subprocess.run(
            [
                sys.executable, "-m", "pip", "install",
                "--disable-pip-version-check", "--only-binary=:all:",
                "--no-deps", "-r", str(REQ),
            ],
            check=False,
        )
        importlib.invalidate_caches()
        status = runtime_dependency_status()
        if result.returncode != 0 or not status["ready"]:
            print("[BOOTSTRAP FAIL] protobuf unavailable; no broker request made")
            raise SystemExit(2)
    from research_v3.pydroid_crossalign_four_symbol_launcher import main as launch
    launch()


if __name__ == "__main__":
    main()
