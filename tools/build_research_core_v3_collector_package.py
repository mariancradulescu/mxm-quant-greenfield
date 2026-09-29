from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "dist" / "MXM_RESEARCH_CORE_V3_FULL_FRONTIER_CAPTURE_V2.zip"
FILES = (
    "RESEARCH_CORE_V3_M5_CAPTURE_RUN.py",
    "data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_EPOCH22_V1.json",
    "evidence/CROSS_SECTIONAL_PEER_COHORT_INDEX_V1.json",
    "research_core_v3/__init__.py",
    "research_core_v3/adaptive_collector.py",
    "research_core_v3/pydroid_adaptive_launcher.py",
    "research_v3/__init__.py",
    "research_v3/capture_identity.py",
    "competition/__init__.py",
    "competition/frontier_data_capture.py",
    "m6/__init__.py",
    "m6/_ctrader_capture_base.py",
    "m6/ctrader_capture.py",
    "m6/ctrader_transport.py",
    "m6/pydroid_oauth.py",
    "m6/ctrader_proto/__init__.py",
    "m6/ctrader_proto/OpenApiCommonModelMessages_pb2.py",
    "m6/ctrader_proto/OpenApiCommonMessages_pb2.py",
    "m6/ctrader_proto/OpenApiModelMessages_pb2.py",
    "m6/ctrader_proto/OpenApiMessages_pb2.py",
    "m6/ctrader_proto/LICENSE_SPOTWARE_OPENAPIPY.txt",
    "tools/requirements-m6-capture.txt",
)


def build():
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(TARGET, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in FILES:
            path = ROOT / rel
            if not path.is_file():
                raise FileNotFoundError(rel)
            info = zipfile.ZipInfo(rel, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    digest = hashlib.sha256(TARGET.read_bytes()).hexdigest()
    print(TARGET)
    print(digest)
    return TARGET, digest


if __name__ == "__main__":
    build()
