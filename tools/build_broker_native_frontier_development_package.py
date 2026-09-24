#!/usr/bin/env python3
from __future__ import annotations
import hashlib,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/"dist"/"MXM_BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_PACKAGE_V1.zip"
FILES=(
"BROKER_NATIVE_FRONTIER_DEVELOPMENT_RUN.py",
"data/BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_PLAN_V1.json",
"data/BROKER_NATIVE_FRONTIER_M5_PROBE_ACCEPTANCE_V1.json",
"evidence/BROKER_NATIVE_FRONTIER_M5_TOPOLOGY_REPORT_V1.json",
"data/BROKER_NATIVE_ADAPTIVE_INFORMATION_FRONTIER_V1.json",
"research_v3/__init__.py","research_v3/broker_native_frontier_development_capture.py","research_v3/pydroid_broker_native_frontier_development_launcher.py",
"competition/__init__.py","competition/frontier_data_capture.py",
"m6/__init__.py","m6/_ctrader_capture_base.py","m6/ctrader_capture.py","m6/ctrader_transport.py","m6/pydroid_oauth.py",
"m6/ctrader_proto/__init__.py","m6/ctrader_proto/OpenApiCommonModelMessages_pb2.py","m6/ctrader_proto/OpenApiCommonMessages_pb2.py",
"m6/ctrader_proto/OpenApiModelMessages_pb2.py","m6/ctrader_proto/OpenApiMessages_pb2.py","m6/ctrader_proto/LICENSE_SPOTWARE_OPENAPIPY.txt",
"tools/requirements-m6-capture.txt")
def main():
    missing=[x for x in FILES if not (ROOT/x).is_file()]
    if missing: raise SystemExit(f"missing package files: {missing}")
    TARGET.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(TARGET,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for rel in FILES:
            i=zipfile.ZipInfo(rel,(1980,1,1,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=0o644<<16
            z.writestr(i,(ROOT/rel).read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    print(f"BROKER_NATIVE_FRONTIER_DEVELOPMENT_PACKAGE={TARGET}")
    print(f"BROKER_NATIVE_FRONTIER_DEVELOPMENT_PACKAGE_SHA256={hashlib.sha256(TARGET.read_bytes()).hexdigest()}")
if __name__=="__main__":main()
