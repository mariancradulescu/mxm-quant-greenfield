"""Deterministic treatment of a new AI authority request; no provider retries."""
from __future__ import annotations
import json
import re
from pathlib import Path
from research_v3.evidence_eligibility import role_for, FORBIDDEN
from research_v3.runtime_v2_primitives import sha256_file, atomic_write_json, iso

REQUEST=Path("research_v3/ai_director/ADDITIONAL_AUTHORITY_REQUEST_V1.json")
ACCEPT=Path("research_v3/ai_director/ADDITIONAL_AUTHORITY_ACCEPTANCE_V1.json")
REF_RE=re.compile(r"^[A-Za-z0-9_./-]{1,220}$")

def resolve(root:Path)->dict:
    request=json.loads((root/REQUEST).read_text(encoding="utf-8"))
    if request.get("status")!="ADDITIONAL_AUTHORITY_REQUIRED":
        raise ValueError("no pending authority request")
    requested=request.get("requested_authority_or_class")
    if not isinstance(requested,str) or not REF_RE.fullmatch(requested) or ".." in Path(requested).parts:
        return {"status":"UNRESOLVED_AUTHORITY_CLASS","reason":"A precise safe repository ref is required"}
    ref=Path(requested)
    path=(root/ref).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        return {"status":"AUTHORITY_NOT_PRESENT","requested_ref":requested}
    registry=json.loads((root/"research_v3/ai_director/EVIDENCE_ELIGIBILITY_V1.json").read_text(encoding="utf-8"))
    binding=next((row for row in registry.get("bindings",[]) if row.get("ref")==requested),None)
    if binding is None:
        return {"status":"AUTHORITY_NOT_CLASSIFIED","requested_ref":requested,
                "reason":"An existing file is not automatically prospective authority; record an explicit evidence-role binding first."}
    role=binding["role"]
    if role != role_for(requested) and role_for(requested) in FORBIDDEN:
        return {"status":"AUTHORITY_ROLE_CONFLICT","requested_ref":requested,"role":role}
    if role in FORBIDDEN or role=="HISTORICAL_CONTEXT_ONLY" or binding.get("prospective_reuse") is not True:
        return {"status":"AUTHORITY_HISTORICAL_ONLY","requested_ref":requested,"role":role}
    doc={"schema":"mxm.greenfield.additional-authority-acceptance.v1",
         "status":"ELIGIBLE_AUTHORITY_ADDED_TO_NEW_PACKET",
         "original_request_id":request.get("request_id"),
         "requested_ref":requested,"sha256":sha256_file(path),"role":role,
         "evidence_epoch":request.get("evidence_epoch"),
         "outcomes_opened":0,"v2_attempts_consumed":0,
         "accepted_utc":iso()}
    atomic_write_json(root/ACCEPT,doc)
    return doc
