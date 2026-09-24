#!/usr/bin/env python3
from __future__ import annotations
import hashlib,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/"dist"/"MXM_BREAKOUT_FADE_NETH25_TRANSACTION_LOCAL_COST_PACKAGE_V1.zip"
FILES=(
    "BREAKOUT_FADE_NETH25_TRANSACTION_LOCAL_COST_RUN.py",
    "data/BREAKOUT_FADE_NETH25_TRANSACTION_LOCAL_COST_CAPTURE_PLAN_V1.json",
    "research_v3/EPOCH18_BREAKOUT_FADE_NETH25_COST_EXTENSION_DECISION_V1.json",
    "data/COMPETITION_ULTRA_FAST_DISCOVERY_PROTOCOL_V3.json",
    "research_v3/__init__.py",
    "research_v3/breakout_volatility_event_availability_screen.py",
    "research_v3/breakout_volatility_30m_persistence_screen.py",
    "research_v3/breakout_fade_neth25_cost_capture.py",
    "research_v3/pydroid_breakout_fade_neth25_cost_launcher.py",
    "competition/__init__.py","competition/ultra_fast_capture.py","competition/friction_costs.py","competition/frontier_data_capture.py",
    "m6/__init__.py","m6/_ctrader_capture_base.py","m6/ctrader_capture.py","m6/ctrader_transport.py","m6/pydroid_oauth.py","m6/cost_evidence.py",
    "m6/ctrader_proto/__init__.py","m6/ctrader_proto/OpenApiCommonModelMessages_pb2.py","m6/ctrader_proto/OpenApiCommonMessages_pb2.py",
    "m6/ctrader_proto/OpenApiModelMessages_pb2.py","m6/ctrader_proto/OpenApiMessages_pb2.py","m6/ctrader_proto/LICENSE_SPOTWARE_OPENAPIPY.txt",
    "tools/requirements-m6-capture.txt",
)

def main():
    missing=[x for x in FILES if not (ROOT/x).is_file()]
    if missing:
        raise SystemExit(f"missing package files: {missing}")
    TARGET.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(TARGET,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for rel in FILES:
            info=zipfile.ZipInfo(rel,(1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            z.writestr(info,(ROOT/rel).read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    print(f"NETH25_COST_PACKAGE={TARGET}")
    print(f"NETH25_COST_PACKAGE_SHA256={hashlib.sha256(TARGET.read_bytes()).hexdigest()}")

if __name__=="__main__":
    main()
