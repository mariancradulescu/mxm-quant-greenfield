#!/usr/bin/env python3
from pathlib import Path
from m6.cost_evidence import build_cost_pydroid_package

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/"dist"/"MXM_M6_COST_EVIDENCE_PYDROID_PACKAGE.zip"

def main():
    digest=build_cost_pydroid_package(ROOT,TARGET)
    print(f"COST_PACKAGE={TARGET}")
    print(f"COST_SHA256={digest}")

if __name__=="__main__":
    main()
