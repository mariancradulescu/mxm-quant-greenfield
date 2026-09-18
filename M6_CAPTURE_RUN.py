#!/usr/bin/env python3
"""One-button Android/Pydroid entry point for the MXM M6 read-only capture.

This file deliberately uses only the Python standard library until the runtime
requirements have been verified/installed. That makes a fresh extracted package
self-bootstrapping on Pydroid.
"""
from __future__ import annotations

import importlib
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIREMENTS_PATH = ROOT / "tools" / "requirements-m6-capture.txt"

_REQUIRED_EXACT = {
    "ctrader-open-api": "0.9.2",
    "requests": "2.32.3",
}


def _service_identity_compatible(value: str) -> bool:
    try:
        parts = value.split(".")
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
    except (TypeError, ValueError):
        return False
    return major == 24 and minor >= 1


def runtime_dependency_status() -> dict:
    status = {"ready": True, "packages": {}, "problems": []}
    for package, expected in _REQUIRED_EXACT.items():
        try:
            actual = package_version(package)
        except PackageNotFoundError:
            actual = None
        status["packages"][package] = actual
        if actual != expected:
            status["ready"] = False
            status["problems"].append(
                f"{package}: installed={actual or 'missing'} required={expected}"
            )

    try:
        service_identity = package_version("service-identity")
    except PackageNotFoundError:
        service_identity = None
    status["packages"]["service-identity"] = service_identity
    if service_identity is None or not _service_identity_compatible(service_identity):
        status["ready"] = False
        status["problems"].append(
            "service-identity: installed="
            f"{service_identity or 'missing'} required=>=24.1.0,<25"
        )
    return status


def _ensure_runtime_dependencies() -> None:
    if not REQUIREMENTS_PATH.is_file():
        print(f"[BOOTSTRAP FAIL] Missing {REQUIREMENTS_PATH}")
        raise SystemExit(2)

    before = runtime_dependency_status()
    if before["ready"]:
        print("[BOOTSTRAP PASS] cTrader runtime dependencies already installed.")
        return

    print("[BOOTSTRAP] Installing required cTrader runtime packages automatically...")
    for problem in before["problems"]:
        print("[BOOTSTRAP]", problem)
    print("[BOOTSTRAP] This first-run installation can take a few minutes in Pydroid.")

    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "-r",
        str(REQUIREMENTS_PATH),
    ]
    try:
        completed = subprocess.run(command, check=False)
    except OSError as exc:
        print(f"[BOOTSTRAP FAIL] Could not start pip: {type(exc).__name__}: {exc}")
        raise SystemExit(2) from None

    if completed.returncode != 0:
        print("[BOOTSTRAP FAIL] Automatic package installation failed.")
        print(
            "Check internet access/Pydroid Pip support, then RUN this same file again. "
            "No OAuth or broker capture was attempted."
        )
        raise SystemExit(2)

    importlib.invalidate_caches()
    after = runtime_dependency_status()
    if not after["ready"]:
        print("[BOOTSTRAP FAIL] pip finished but required versions are still unavailable:")
        for problem in after["problems"]:
            print("[BOOTSTRAP]", problem)
        print("STOPPED before OAuth and before broker capture.")
        raise SystemExit(2)

    print("[BOOTSTRAP PASS] Required cTrader runtime installed successfully.")


def main() -> None:
    _ensure_runtime_dependencies()

    # Import the real runtime only after bootstrap succeeds.
    from m6.pydroid_launcher import main as launcher_main

    launcher_main()


if __name__ == "__main__":
    main()
