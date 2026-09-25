#!/usr/bin/env python3
"""Build the deterministic, secret-free Pydroid deployment ZIP."""
from pathlib import Path

from m6.ctrader_capture import build_pydroid_package

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "dist" / "MXM_M6_CAPTURE_PYDROID_PACKAGE.zip"


def main() -> None:
    digest = build_pydroid_package(ROOT, TARGET)
    print(f"PACKAGE={TARGET}")
    print(f"SHA256={digest}")


if __name__ == "__main__":
    main()
