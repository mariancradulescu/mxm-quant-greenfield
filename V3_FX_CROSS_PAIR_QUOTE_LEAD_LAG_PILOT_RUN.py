#!/usr/bin/env python3
"""Android/Pydroid entry point for FX cross-pair quote lead/lag pilot V2."""
import importlib, os, subprocess, sys
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION","python")
ROOT=Path(__file__).resolve().parent
REQ=ROOT/"tools"/"requirements-m6-capture.txt"
def _ready():
    try:return package_version("protobuf")=="3.20.1"
    except PackageNotFoundError:return False
def main():
    if not _ready():
        print("[BOOTSTRAP] Installing Android-safe protobuf 3.20.1...")
        x=subprocess.run([sys.executable,"-m","pip","install","--disable-pip-version-check","--only-binary=:all:","--no-deps","-r",str(REQ)],check=False)
        importlib.invalidate_caches()
        if x.returncode!=0 or not _ready():
            print("[BOOTSTRAP FAIL] protobuf unavailable; no broker request was made."); raise SystemExit(2)
    from research_core_v3.pydroid_fx_cross_pair_quote_lead_lag_launcher import main as launch
    launch()
if __name__=="__main__": main()
