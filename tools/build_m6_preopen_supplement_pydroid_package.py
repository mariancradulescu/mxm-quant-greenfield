#!/usr/bin/env python3
from pathlib import Path
from m6.preopen_supplement import build_preopen_pydroid_package
ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/"dist"/"MXM_M6_PREOPEN_SUPPLEMENT_PYDROID_PACKAGE.zip"
def main():
    digest=build_preopen_pydroid_package(ROOT,TARGET)
    print(f"PREOPEN_PACKAGE={TARGET}")
    print(f"PREOPEN_SHA256={digest}")
if __name__=="__main__": main()
