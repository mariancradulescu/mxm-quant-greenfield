#!/usr/bin/env python3
"""Android/Pydroid entry point for the bounded global V3 friction triage."""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
ROOT = Path(__file__).resolve().parent
REQ = ROOT / "tools" / "requirements-m6-capture.txt"
REQUIRED = "3.20.1"


def _ready() -> bool:
    try:
        return package_version("protobuf") == REQUIRED
    except PackageNotFoundError:
        return False


def main() -> None:
    if not _ready():
        print("[BOOTSTRAP] Installing Android-safe protobuf 3.20.1...")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--only-binary=:all:",
                "--no-deps",
                "-r",
                str(REQ),
            ],
            check=False,
        )
        importlib.invalidate_caches()
        if result.returncode != 0 or not _ready():
            print("[BOOTSTRAP FAIL] protobuf unavailable; no broker request was made.")
            raise SystemExit(2)
    from research_core_v3.pydroid_v3_friction_staged_launcher import main as launcher
    launcher()


if __name__ == "__main__":
    main()
