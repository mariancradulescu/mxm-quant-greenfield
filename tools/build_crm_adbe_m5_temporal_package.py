from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "dist" / "MXM_V3_CRM_ADBE_M5_TEMPORAL_COLLECTOR_V1.zip"
REPORT = ROOT / "dist" / "CRM_ADBE_M5_PACKAGE_BUILD_REPORT_V1.json"

SOURCE_AUTHORITY_HEAD = "68863e3f5c9a9ec462518a89af7af7ed50a568cc"
RUN_ONLY = "CRM_ADBE_M5_CAPTURE_RUN.py"
RETURN_ONLY = "MXM_V3_CRM_ADBE_M5_TEMPORAL_EVIDENCE_V1.zip"

FILES = (
    "CRM_ADBE_M5_CAPTURE_RUN.py",
    "README_CRM_ADBE_M5_CAPTURE.txt",
    "data/CRM_ADBE_M5_TEMPORAL_ACQUISITION_PLAN_V1.json",
    "research_core_v3/__init__.py",
    "research_core_v3/crm_adbe_m5_temporal_capture.py",
    "research_core_v3/pydroid_crm_adbe_m5_temporal_launcher.py",
    "research_core_v3/state/CRM_ADBE_M5_PREACQUISITION_PROVENANCE_AUDIT_V1.json",
    "research_core_v3/state/CRM_ADBE_INTRADAY_RV_TEMPORAL_RETEST_PACKAGE_V1.json",
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

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def build() -> tuple[Path, dict]:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with zipfile.ZipFile(TARGET, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in sorted(FILES):
            path = ROOT / rel
            if not path.is_file():
                raise FileNotFoundError(rel)
            data = path.read_bytes()
            rows.append({"path": rel, "sha256": sha256_bytes(data), "size_bytes": len(data)})
            info = zipfile.ZipInfo(rel, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

        manifest = {
            "schema": "mxm.research-core-v3.crm-adbe-m5-temporal-collector-package-manifest.v1",
            "status": "VALIDATED_READY_FOR_USER_EXECUTION",
            "source_authority_head": SOURCE_AUTHORITY_HEAD,
            "package_name": TARGET.name,
            "run_only": RUN_ONLY,
            "return_only": RETURN_ONLY,
            "exact_scope": {
                "symbols": ["CRM.US-24", "ADBE.US-24"],
                "resolution": "M5",
                "interval": ["2025-01-02T00:00:00Z", "2025-09-14T23:59:59Z"],
            },
            "read_only": True,
            "orders": False,
            "account_mutation": False,
            "fill_authority": False,
            "bid_ask": False,
            "ticks": False,
            "strategy_outcomes_on_device": False,
            "files": rows,
        }
        data = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")
        info = zipfile.ZipInfo("PACKAGE_MANIFEST.json", (1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        z.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    with zipfile.ZipFile(TARGET, "r") as z:
        bad = z.testzip()
        if bad is not None:
            raise RuntimeError(f"ZIP CRC validation failed at {bad}")
        names = [x.filename for x in z.infolist() if not x.is_dir()]
        if names.count(RUN_ONLY) != 1:
            raise RuntimeError("run file missing or duplicated")
        if "PACKAGE_MANIFEST.json" not in names:
            raise RuntimeError("package manifest missing")

    digest = hashlib.sha256(TARGET.read_bytes()).hexdigest()
    report = {
        "schema": "mxm.research-core-v3.crm-adbe-m5-package-build-report.v1",
        "status": "PASS",
        "source_authority_head": SOURCE_AUTHORITY_HEAD,
        "package_name": TARGET.name,
        "package_sha256": digest,
        "package_size_bytes": TARGET.stat().st_size,
        "zip_crc": "PASS",
        "run_only": RUN_ONLY,
        "return_only": RETURN_ONLY,
        "entry_count": len(FILES) + 1,
        "read_only": True,
        "broker_contacted": False,
        "acquisition_launched": False,
    }
    REPORT.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return TARGET, report

if __name__ == "__main__":
    path, report = build()
    print(path)
    print(json.dumps(report, sort_keys=True))
