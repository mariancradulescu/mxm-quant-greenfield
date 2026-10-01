from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from research_core_v3.crm_adbe_m5_temporal_capture import validate_plan
from research_core_v3.pydroid_crm_adbe_m5_temporal_launcher import local_preflight
from tools.build_crm_adbe_m5_temporal_package import build

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "data" / "CRM_ADBE_M5_TEMPORAL_ACQUISITION_PLAN_V1.json"

plan = json.loads(PLAN.read_text(encoding="utf-8"))
validate_plan(plan)
pre = local_preflight()
assert pre["symbols"] == ["CRM.US-24", "ADBE.US-24"], pre
assert pre["resolution"] == "M5", pre
assert pre["interval"] == {
    "start_utc": "2025-01-02T00:00:00Z",
    "end_utc": "2025-09-14T23:59:59Z",
}, pre
assert pre["orders_permitted"] is False
assert pre["account_mutation_permitted"] is False
assert pre["fill_authority"] is False
assert pre["strategy_outcomes_computed"] is False
assert pre["protected_forward_opened"] is False

path, report = build()
with zipfile.ZipFile(path, "r") as z:
    assert z.testzip() is None
assert report["status"] == "PASS"
assert report["zip_crc"] == "PASS"
assert report["broker_contacted"] is False
assert report["acquisition_launched"] is False
assert hashlib.sha256(path.read_bytes()).hexdigest() == report["package_sha256"]

print("CRM_ADBE_PACKAGE_VALIDATION_PASS")
print(json.dumps(report, sort_keys=True))
