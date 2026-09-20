#!/usr/bin/env python3
"""Android/Pydroid entry point for Stage-B historical margin evidence."""
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


def runtime_dependency_status() -> dict[str, object]:
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


def main() -> None:
    status = runtime_dependency_status()
    if not status["ready"]:
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
        status = runtime_dependency_status()
        if result.returncode != 0 or not status["ready"]:
            print(
                "[BOOTSTRAP FAIL] protobuf runtime unavailable; "
                "no broker request was made."
            )
            raise SystemExit(2)
    from m6.pydroid_stage_b_margin_launcher import main as launcher
    launcher()


if __name__ == "__main__":
    main()
