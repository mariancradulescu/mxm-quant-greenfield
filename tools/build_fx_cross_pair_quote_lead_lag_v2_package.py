#!/usr/bin/env python3
"""Build deterministic authoritative V2 lead-lag Android package and package authority."""
from __future__ import annotations
import hashlib, json, os, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NAME="MXM_V3_FX_CROSS_PAIR_QUOTE_LEAD_LAG_PILOT_PACKAGE_V2_DIAGNOSTIC.zip"
TARGET=ROOT/"dist"/NAME
AUTH=ROOT/"research_core_v3/state/FX_CROSS_PAIR_QUOTE_LEAD_LAG_PACKAGE_AUTHORITY_V2.json"
FILES=(
"V3_FX_CROSS_PAIR_QUOTE_LEAD_LAG_PILOT_RUN.py",
"research_core_v3/__init__.py",
"research_core_v3/fx_cross_pair_quote_lead_lag_capture.py",
"research_core_v3/pydroid_fx_cross_pair_quote_lead_lag_launcher.py",
"research_core_v3/state/FX_CROSS_PAIR_QUOTE_LEAD_LAG_PREOUTCOME_AUDIT_V1.json",
"research_core_v3/state/FX_CROSS_PAIR_QUOTE_LEAD_LAG_DEVELOPMENT_DESIGN_V1.json",
"research_core_v3/state/FX_CROSS_PAIR_QUOTE_LEAD_LAG_ACQUISITION_PLAN_V2.json",
"research_core_v3/state/FX_CROSS_PAIR_QUOTE_LEAD_LAG_PATH_OBSERVABILITY_FREEZE_V1.json",
"m6/__init__.py","m6/_ctrader_capture_base.py","m6/ctrader_capture.py","m6/ctrader_transport.py","m6/cost_evidence.py","m6/pydroid_oauth.py",
"m6/ctrader_proto/__init__.py","m6/ctrader_proto/OpenApiCommonModelMessages_pb2.py","m6/ctrader_proto/OpenApiCommonMessages_pb2.py","m6/ctrader_proto/OpenApiModelMessages_pb2.py","m6/ctrader_proto/OpenApiMessages_pb2.py","m6/ctrader_proto/LICENSE_SPOTWARE_OPENAPIPY.txt",
"tools/requirements-m6-capture.txt","README_FX_CROSS_PAIR_QUOTE_LEAD_LAG_V2.txt",
)
def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
 return h.hexdigest()
def canon(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def main():
 missing=[x for x in FILES if not (ROOT/x).is_file()]
 if missing:raise SystemExit(f"missing package files: {missing}")
 TARGET.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(TARGET,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for rel in FILES:
   p=ROOT/rel;i=zipfile.ZipInfo(rel,date_time=(1980,1,1,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=0o644<<16
   z.writestr(i,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
 with zipfile.ZipFile(TARGET) as z:
  if tuple(z.namelist())!=FILES:raise SystemExit("package member/order mismatch")
  if z.testzip() is not None:raise SystemExit("package CRC failure")
 package_sha=sha(TARGET)
 authority={
  "schema":"mxm.research-core-v3.fx-cross-pair-quote-lead-lag-package-authority.v2",
  "status":"OFFLINE_VALIDATED_READY_FOR_MINIMAL_USER_DEVICE_EXECUTION",
  "package_name":NAME,"package_sha256":package_sha,"package_bytes":TARGET.stat().st_size,
  "entry_point":"V3_FX_CROSS_PAIR_QUOTE_LEAD_LAG_PILOT_RUN.py",
  "expected_output":"MXM_V3_FX_CROSS_PAIR_QUOTE_LEAD_LAG_PILOT_EVIDENCE_V2.zip",
  "build_source_head":os.getenv("GITHUB_SHA","LOCAL"),
  "primary_design_ref":"research_core_v3/state/FX_CROSS_PAIR_QUOTE_LEAD_LAG_DEVELOPMENT_DESIGN_V1.json",
  "primary_design_sha256":"d275f41ee22bd97f10fc5892e390b74c6cfa209ae80691a9de7e9cc89765a5f8",
  "frozen_primary_tests":72,
  "acquisition_plan_ref":"research_core_v3/state/FX_CROSS_PAIR_QUOTE_LEAD_LAG_ACQUISITION_PLAN_V2.json",
  "acquisition_plan_binding_sha256":"eaa46220c925dc461f39b33c60f3e1a90b76ee7c678a8d8acfa7a26180826d71",
  "diagnostic_freeze_ref":"research_core_v3/state/FX_CROSS_PAIR_QUOTE_LEAD_LAG_PATH_OBSERVABILITY_FREEZE_V1.json",
  "diagnostic_freeze_sha256":"e7e1e196263e9e06a0c33a0e411554f9523d8c37365c29cb5ea90b0574f0839d",
  "diagnostic_horizon_seconds":900,
  "supersedes":{"package_name":"MXM_V3_FX_CROSS_PAIR_QUOTE_LEAD_LAG_PILOT_PACKAGE_V1.zip","package_sha256":"ac25a14f20bebfd5b8a1d2fd5d23775dea1a3c509906a52dbe67b5410e9a0784","execution_authority":False},
  "offline_validation":{"python_compile":"PASS_BY_WORKFLOW","authority_preflight":"PASS_BY_WORKFLOW","zip_crc":"PASS","package_members":len(FILES),"raw_ticks_in_transfer":False,"fill_authority":False,"orders_permitted":False,"protected_forward_opened":False},
  "governance":{"primary_scientific_design_changed":False,"diagnostic_fields_enter_primary_maxT":False,"candidate_freeze_from_capture":False,"automatic_additional_acquisition":False,"runtime_v2_reactivated":False}
 }
 authority["canonical_sha256"]=hashlib.sha256(canon(authority)).hexdigest()
 AUTH.write_text(json.dumps(authority,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
 print(f"PACKAGE={TARGET}");print(f"SHA256={package_sha}");print(f"AUTHORITY={AUTH}")
if __name__=="__main__":main()
