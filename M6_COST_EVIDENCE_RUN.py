#!/usr/bin/env python3
"""Android/Pydroid entry point for bounded Tier-1 BID/ASK cost evidence."""
from __future__ import annotations
import importlib, os, subprocess, sys
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION","python")
ROOT=Path(__file__).resolve().parent
REQ=ROOT/"tools"/"requirements-m6-capture.txt"
REQUIRED="3.20.1"

def _ready():
    try: return package_version("protobuf")==REQUIRED
    except PackageNotFoundError: return False

def main():
    if not _ready():
        print("[BOOTSTRAP] Installing Android-safe protobuf 3.20.1...")
        result=subprocess.run([
            sys.executable,"-m","pip","install","--disable-pip-version-check",
            "--only-binary=:all:","--no-deps","-r",str(REQ)
        ],check=False)
        importlib.invalidate_caches()
        if result.returncode!=0 or not _ready():
            print("[BOOTSTRAP FAIL] protobuf runtime unavailable; no broker request was made.")
            raise SystemExit(2)
    from m6.pydroid_cost_launcher import main as launcher
    launcher()

if __name__=="__main__":
    main()
