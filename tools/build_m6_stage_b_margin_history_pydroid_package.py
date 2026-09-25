#!/usr/bin/env python3
from pathlib import Path

from m6.stage_b_margin_evidence import build_margin_history_pydroid_package

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "dist" / "MXM_M6_STAGE_B_MARGIN_HISTORY_PYDROID_PACKAGE.zip"


def main() -> None:
    digest = build_margin_history_pydroid_package(ROOT, TARGET)
    print(f"STAGE_B_MARGIN_PACKAGE={TARGET}")
    print(f"STAGE_B_MARGIN_SHA256={digest}")


if __name__ == "__main__":
    main()
