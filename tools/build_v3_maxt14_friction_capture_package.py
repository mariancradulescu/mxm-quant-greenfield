#!/usr/bin/env python3
"""Build deterministic Android package for V3 maxT14 authentic friction capture."""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "dist" / "MXM_V3_MAXT14_FRICTION_CAPTURE_PACKAGE_V4.zip"

FILES = (
    "V3_MAXT14_FRICTION_CAPTURE_RUN.py",
    "research_core_v3/__init__.py",
    "research_core_v3/v3_friction_capture.py",
    "research_core_v3/pydroid_v3_friction_launcher.py",
    "research_core_v3/state/MAXT14_AUTHENTIC_FRICTION_ACQUISITION_PLAN_V1.json",
    "research_core_v3/state/CORRECTED_FRICTION_SCOPE_V2_PACK_00.zip",
    "research_core_v3/state/CORRECTED_FRICTION_SCOPE_V2_PACK_01.zip",
    "research_core_v3/state/CORRECTED_FRICTION_SCOPE_V2_PACK_03.zip",
    "research_core_v3/state/CORRECTED_FRICTION_SCOPE_V2_PACK_04.zip",
    "m6/__init__.py",
    "m6/_ctrader_capture_base.py",
    "m6/ctrader_capture.py",
    "m6/ctrader_transport.py",
    "m6/cost_evidence.py",
    "m6/pydroid_oauth.py",
    "m6/ctrader_proto/__init__.py",
    "m6/ctrader_proto/OpenApiCommonModelMessages_pb2.py",
    "m6/ctrader_proto/OpenApiCommonMessages_pb2.py",
    "m6/ctrader_proto/OpenApiModelMessages_pb2.py",
    "m6/ctrader_proto/OpenApiMessages_pb2.py",
    "m6/ctrader_proto/LICENSE_SPOTWARE_OPENAPIPY.txt",
    "tools/requirements-m6-capture.txt",
    "README_V3_MAXT14_FRICTION_CAPTURE.txt",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    missing = [rel for rel in FILES if not (ROOT / rel).is_file()]
    if missing:
        raise SystemExit(f"missing package source files: {missing}")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        TARGET, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as zf:
        for rel in FILES:
            path = ROOT / rel
            info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    with zipfile.ZipFile(TARGET) as zf:
        if tuple(zf.namelist()) != FILES:
            raise SystemExit("deterministic package member/order mismatch")
    print(f"PACKAGE={TARGET}")
    print(f"SHA256={sha256_file(TARGET)}")


if __name__ == "__main__":
    main()
