#!/usr/bin/env python3
"""One-button Android/Pydroid entry point for the MXM M6 read-only capture.

Android compatibility rule: no Twisted/pyOpenSSL/cryptography/Rust toolchain.
Only the universal pure-Python protobuf runtime is installed on first run.
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path

# Force protobuf's pure-Python backend. This is portable on Pydroid Python 3.13/aarch64.
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

ROOT = Path(__file__).resolve().parent
REQUIREMENTS_PATH = ROOT / "tools" / "requirements-m6-capture.txt"
REQUIRED_PROTOBUF = "3.20.1"


def runtime_dependency_status() -> dict:
    try:
        actual = package_version("protobuf")
    except PackageNotFoundError:
        actual = None
    return {
        "ready": actual == REQUIRED_PROTOBUF,
        "packages": {"protobuf": actual},
        "problems": [] if actual == REQUIRED_PROTOBUF else [
            f"protobuf: installed={actual or 'missing'} required={REQUIRED_PROTOBUF}"
        ],
        "rust_required": False,
        "cryptography_required": False,
    }


def _ensure_runtime_dependencies() -> None:
    if not REQUIREMENTS_PATH.is_file():
        print(f"[BOOTSTRAP FAIL] Missing {REQUIREMENTS_PATH}")
        raise SystemExit(2)

    before = runtime_dependency_status()
    if before["ready"]:
        print("[BOOTSTRAP PASS] Pure-Python protobuf runtime already installed.")
        return

    print("[BOOTSTRAP] Installing Android-safe protobuf runtime...")
    for problem in before["problems"]:
        print("[BOOTSTRAP]", problem)
    print("[BOOTSTRAP] Source builds are disabled; Rust/cryptography are not used.")

    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--only-binary=:all:",
        "--no-deps",
        "-r",
        str(REQUIREMENTS_PATH),
    ]
    try:
        completed = subprocess.run(command, check=False)
    except OSError as exc:
        print(f"[BOOTSTRAP FAIL] Could not start pip: {type(exc).__name__}: {exc}")
        raise SystemExit(2) from None

    if completed.returncode != 0:
        print("[BOOTSTRAP FAIL] Universal protobuf wheel installation failed.")
        print(
            "No OAuth or broker capture was attempted. Check Pydroid internet access "
            "and RUN this same file again."
        )
        raise SystemExit(2)

    importlib.invalidate_caches()
    after = runtime_dependency_status()
    if not after["ready"]:
        print("[BOOTSTRAP FAIL] protobuf 3.20.1 is still unavailable after pip.")
        raise SystemExit(2)

    print("[BOOTSTRAP PASS] protobuf 3.20.1 installed. Rust is not required.")


def main() -> None:
    _ensure_runtime_dependencies()
    from m6.pydroid_launcher import main as launcher_main
    launcher_main()


if __name__ == "__main__":
    main()
