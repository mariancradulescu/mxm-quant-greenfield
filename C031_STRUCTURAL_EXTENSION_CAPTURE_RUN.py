#!/usr/bin/env python3
"""Android/Pydroid entry point for the minimal C031 structural extension M5 capture."""
from __future__ import annotations
import importlib, os, subprocess, sys
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION","python")
ROOT=Path(__file__).resolve().parent
REQ=ROOT/"tools"/"requirements-m6-capture.txt"
REQUIRED="3.20.1"
def runtime_dependency_status():
    try: actual=package_version("protobuf")
    except PackageNotFoundError: actual=None
    return {"ready":actual==REQUIRED,"protobuf":actual,"required":REQUIRED,"cryptography_required":False,"rust_required":False}
def main():
    status=runtime_dependency_status()
    if not status["ready"]:
        result=subprocess.run([sys.executable,"-m","pip","install","--disable-pip-version-check","--only-binary=:all:","--no-deps","-r",str(REQ)],check=False)
        importlib.invalidate_caches(); status=runtime_dependency_status()
        if result.returncode!=0 or not status["ready"]:
            print("[BOOTSTRAP FAIL] protobuf unavailable; no broker request made"); raise SystemExit(2)
    from research_v3.pydroid_c031_structural_extension_launcher import main as launcher
    launcher()
if __name__=="__main__": main()
