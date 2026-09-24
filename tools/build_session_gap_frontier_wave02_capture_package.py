from __future__ import annotations
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "dist" / "MXM_SESSION_GAP_FRONTIER_WAVE_02_M5_BID_ASK_CAPTURE_PACKAGE.zip"
FILES = (
    "SESSION_GAP_FRONTIER_WAVE_02_CAPTURE_RUN.py",
    "data/SESSION_GAP_FRONTIER_WAVE_02_M5_CAPTURE_PLAN_V1.json",
    "research_v3/__init__.py",
    "research_v3/session_gap_frontier_wave02_capture.py",
    "research_v3/pydroid_session_gap_frontier_wave02_launcher.py",
    "m6/__init__.py", "m6/_ctrader_capture_base.py", "m6/ctrader_capture.py", "m6/ctrader_transport.py",
    "m6/cost_evidence.py", "m6/pydroid_oauth.py", "m6/ctrader_proto/__init__.py",
    "m6/ctrader_proto/OpenApiCommonModelMessages_pb2.py", "m6/ctrader_proto/OpenApiCommonMessages_pb2.py",
    "m6/ctrader_proto/OpenApiModelMessages_pb2.py", "m6/ctrader_proto/OpenApiMessages_pb2.py",
    "m6/ctrader_proto/LICENSE_SPOTWARE_OPENAPIPY.txt", "tools/requirements-m6-capture.txt",
)

def main():
    missing = [item for item in FILES if not (ROOT / item).is_file()]
    if missing:
        raise SystemExit(f"missing package files: {missing}")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(TARGET, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for item in FILES:
            info = zipfile.ZipInfo(item, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (ROOT / item).read_bytes())
    print(f"{TARGET} SHA256={hashlib.sha256(TARGET.read_bytes()).hexdigest()}")

if __name__ == "__main__":
    main()
