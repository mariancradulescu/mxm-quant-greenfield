from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "mariancradulescu/mxm-quant-greenfield"
BRANCH = "performance-research-v3-20260922"
SCIENTIFIC_SOURCE_HEAD = "68bdee4b51244ae50acd56fe868468b96106450f"
SEED = 20261002
PERMUTATIONS = 1023
ENCRYPTION_FORMAT = "OPENPGP_SYMMETRIC_AES256_WITH_INTEGRITY_PROTECTION"

ARM_REL = "research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_V3_ARM_V1.json"
STATE_REL = "research_core_v4/state/V4_STATE.json"
RECOVERY_AUTH_REL = "research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_AUTHORITY_V3.json"
EXEC_AUTH_REL = "research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_EXECUTION_AUTHORITY_V3.json"
WORKFLOW_REL = ".github/workflows/v4-greenfield-recovery-v3.yml"
STAGING_REL = "research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_RECOVERY_V3_GREENFIELD_INPUT_STAGING_CERTIFICATE_V1.json"
RESULT_REL = "research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json"
LOCK_REL = "research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_V3_ATTEMPT_LOCK_V1.txt"
INPUT_PREFIX = "research_core_v4/runtime_inputs/V4_EXACT_M5_INPUT_BUNDLE_V1.gpg.part-"

FROZEN_HASHES = {
    "design": ("research_core_v4/state/FIRST_REAL_MARKET_DESIGN_V2.json", "3f9a6b1da92b9904da91e86d005f26e8e99d93e5e3497e1b8a72b59b1d4e590e"),
    "evaluator": ("research_core_v4/response_evaluator_v3.py", "bb846fb3bbbe567c53587a6c22b344ffe39af7129db5e9a4a39c77026f3ade2a"),
    "runner": ("research_core_v4/development_execution_runner_v1.py", "cebcf2ad4f88e40d575cb46ffc14e0862107b47a84260a15b3310f075af4f79d"),
    "semantics": ("research_core_v4/frozen_v2_semantics.py", "0a7bda1afe5cbe79373ee833e9d09febc08721d1826d94435f74d900f74f26ed"),
}

def require(condition: bool, message: str) -> None:
    if not condition:
        raise PermissionError("RECOVERY_V3_PREARM_GATE_FAIL " + message)

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def canonical_sha256(value: Any) -> str:
    return sha256_bytes(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8"))

def load_json(path: Path) -> dict:
    value=json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value,dict),f"JSON object required: {path}")
    return value

def parse_json_object_bytes(data: bytes,label: str) -> dict:
    require(bool(data.strip()),f"{label} empty")
    try: value=json.loads(data.decode("utf-8"))
    except Exception as exc: raise PermissionError(f"RECOVERY_V3_PREARM_GATE_FAIL {label} malformed") from exc
    require(isinstance(value,dict),f"{label} must be an object")
    return value

def _exact_series(root: Path) -> list[dict]:
    recovery=load_json(root/RECOVERY_AUTH_REL); execution=load_json(root/EXEC_AUTH_REL)
    a=recovery["frozen_reference"]["exact_18_series"]; b=execution["bindings"]["development_series"]
    require(a==b,"Recovery V3 exact-series binding differs from Execution Authority V3")
    require(len(a)==18,"exact series count is not 18")
    return a

def expected_runtime_bindings(root: Path) -> dict:
    state=load_json(root/STATE_REL); recovery=load_json(root/RECOVERY_AUTH_REL); series=_exact_series(root)
    frozen={}
    for key,(rel,expected) in FROZEN_HASHES.items():
        actual=sha256_file(root/rel); require(actual==expected,f"frozen science changed: {rel}"); frozen[key]=actual
    prep=state.get("recovery_v3_preparation",{})
    require(prep.get("accepted_canonical_result_count")==0,"canonical accepted result count is not zero")
    require(prep.get("real_execution_authorized") is False,"real execution already authorized in V4_STATE")
    require(prep.get("arm_present") is False,"V4_STATE already claims ARM present")
    return {
        "canonical_repository":REPOSITORY,"research_branch":BRANCH,"scientific_source_head":SCIENTIFIC_SOURCE_HEAD,
        "frozen_hashes":frozen,"recovery_v3_authority_sha256":sha256_file(root/RECOVERY_AUTH_REL),
        "canonical_v4_state_sha256":sha256_file(root/STATE_REL),"installed_runtime_workflow_sha256":sha256_file(root/WORKFLOW_REL),
        "staging_certificate_sha256":sha256_file(root/STAGING_REL) if (root/STAGING_REL).exists() else None,
        "exact_18_series_manifest_sha256":canonical_sha256(series),"exact_18_series":series,"seed":SEED,"permutations":PERMUTATIONS,
        "accepted_canonical_result_count":0,
        "source_archives":{"original_sha256":recovery["frozen_reference"]["original_archive_sha256"],"delta_sha256":recovery["frozen_reference"]["delta_archive_sha256"]},
    }

def validate_arm_document(arm:dict,expected:dict,*,actual_head:str,actual_parent:str,changed_paths:list[str],result_present:bool,lock_present:bool)->dict:
    require(arm.get("schema")=="mxm.research-core-v4.recovery-v3-arm.v1","ARM schema")
    require(arm.get("status")=="ARMED_NOT_EXECUTED","ARM status")
    require(arm.get("arm_commit")==actual_head,"ARM commit binding")
    require(arm.get("pre_arm_parent_head")==actual_parent,"wrong or stale pre-arm parent HEAD")
    require(changed_paths==[ARM_REL],"ARM commit contains unrelated mutation")
    require(arm.get("canonical_repository")==expected["canonical_repository"],"ARM repository binding")
    require(arm.get("research_branch")==expected["research_branch"],"ARM branch binding")
    require(arm.get("scientific_source_head")==expected["scientific_source_head"],"ARM scientific source head")
    require(arm.get("frozen_hashes")==expected["frozen_hashes"],"ARM frozen science hashes")
    require(arm.get("recovery_v3_authority_sha256")==expected["recovery_v3_authority_sha256"],"ARM Recovery V3 authority hash")
    require(arm.get("canonical_v4_state_sha256")==expected["canonical_v4_state_sha256"],"ARM V4_STATE hash")
    require(arm.get("installed_runtime_workflow_sha256")==expected["installed_runtime_workflow_sha256"],"ARM installed workflow hash")
    require(expected.get("staging_certificate_sha256") is not None,"staging certificate absent")
    require(arm.get("staging_certificate_sha256")==expected["staging_certificate_sha256"],"ARM staging certificate hash")
    require(arm.get("exact_18_series_manifest_sha256")==expected["exact_18_series_manifest_sha256"],"ARM exact 18-series manifest identity")
    require(arm.get("seed")==SEED,"ARM seed"); require(arm.get("permutations")==PERMUTATIONS,"ARM permutations")
    require(arm.get("accepted_canonical_result_count")==0,"ARM accepted result count")
    require(arm.get("no_prior_recovery_v3_attempt_lock") is True,"ARM prior-lock declaration")
    require(arm.get("no_canonical_result_present") is True,"ARM result-absence declaration")
    require(not result_present,"canonical development result already exists")
    require(not lock_present,"Recovery V3 attempt lock already exists")
    return {"status":"PASS_ARM_PAYLOAD_VALIDATED_BEFORE_LOCK","pre_arm_parent_head":actual_parent}

def validate_staging_certificate_document(cert:dict,expected:dict,*,part_records:list[dict],reconstructed_bundle_sha256:str)->dict:
    require(cert.get("schema")=="mxm.research-core-v4.recovery-v3-greenfield-input-staging-certificate.v1","staging certificate schema")
    require(cert.get("status")=="STAGED_VALIDATED_NOT_ARMED_NOT_EXECUTED","staging certificate status")
    require(cert.get("canonical_repository")==expected["canonical_repository"],"staging repository")
    require(cert.get("research_branch")==expected["research_branch"],"staging branch")
    require(isinstance(cert.get("staging_commit"),str) and len(cert["staging_commit"])==40,"staging commit")
    require(cert.get("scientific_source_head")==expected["scientific_source_head"],"staging scientific source head")
    require(cert.get("recovery_v3_authority_sha256")==expected["recovery_v3_authority_sha256"],"staging authority hash")
    require(cert.get("installed_runtime_workflow_sha256")==expected["installed_runtime_workflow_sha256"],"staging workflow hash")
    require(cert.get("accepted_canonical_result_count")==0,"staging accepted result count")
    require(cert.get("arm_present_at_staging") is False,"staging ARM-absence assertion")
    require(cert.get("real_execution_authorized_at_staging") is False,"staging execution authorization assertion")
    require(cert.get("encryption_format")==ENCRYPTION_FORMAT,"staging encryption format")
    require(cert.get("source_archives")==expected["source_archives"],"staging source archive provenance")
    require(cert.get("exact_18_series")==expected["exact_18_series"],"staging exact 18-series bindings")
    require(cert.get("exact_18_series_manifest_sha256")==expected["exact_18_series_manifest_sha256"],"staging exact-series manifest identity")
    declared=cert.get("encrypted_parts"); require(isinstance(declared,list) and declared,"staging encrypted-parts manifest")
    require(declared==part_records,"staging encrypted-part filenames/digests/sizes")
    names=[x["filename"] for x in part_records]; require(names==sorted(names),"encrypted parts are not in deterministic ordered concatenation")
    require(cert.get("encrypted_part_order")==names,"staging encrypted part order")
    require(cert.get("encrypted_bundle_sha256")==reconstructed_bundle_sha256,"staging reconstructed encrypted bundle hash")
    return {"status":"PASS_STAGING_CERTIFICATE_AND_ENCRYPTED_PARTS","encrypted_part_count":len(part_records)}

def inspect_encrypted_parts(root:Path,cert:dict)->tuple[list[dict],str]:
    declared=cert.get("encrypted_parts"); require(isinstance(declared,list) and declared,"certificate has no encrypted parts")
    names=[x.get("filename") for x in declared]
    require(all(isinstance(x,str) and x.startswith(INPUT_PREFIX) and ".." not in x for x in names),"invalid encrypted-part filename")
    require(names==sorted(names),"encrypted parts not declared in deterministic order")
    records=[]; h=hashlib.sha256()
    for item in declared:
        path=root/item["filename"]; require(path.is_file(),f"encrypted part missing: {item['filename']}")
        digest=sha256_file(path); size=path.stat().st_size
        require(digest==item.get("sha256"),f"encrypted part digest mismatch: {item['filename']}")
        require(size==item.get("size_bytes"),f"encrypted part size mismatch: {item['filename']}")
        records.append({"filename":item["filename"],"sha256":digest,"size_bytes":size})
        with path.open("rb") as f:
            for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return records,h.hexdigest()

def validate_staging_certificate(root:Path)->dict:
    expected=expected_runtime_bindings(root); cert_path=root/STAGING_REL
    require(cert_path.is_file(),"staging certificate absent")
    cert=parse_json_object_bytes(cert_path.read_bytes(),"staging certificate")
    records,bundle_sha=inspect_encrypted_parts(root,cert)
    return validate_staging_certificate_document(cert,expected,part_records=records,reconstructed_bundle_sha256=bundle_sha)

def _git(root:Path,*args:str,check:bool=True)->str:
    p=subprocess.run(["git","-C",str(root),*args],text=True,capture_output=True)
    if check and p.returncode!=0: raise PermissionError("RECOVERY_V3_PREARM_GATE_FAIL git "+" ".join(args)+": "+p.stderr.strip())
    return p.stdout.strip()

def validate_runtime_gate(root:Path=ROOT)->dict:
    arm_path=root/ARM_REL; require(arm_path.is_file(),"ARM file absent at ARM-triggered runtime")
    arm=parse_json_object_bytes(arm_path.read_bytes(),"ARM")
    head=_git(root,"rev-parse","HEAD"); parents=_git(root,"rev-list","--parents","-n","1","HEAD").split()
    require(len(parents)==2,"ARM commit must have exactly one parent"); parent=parents[1]
    changed=[x for x in _git(root,"diff-tree","--no-commit-id","--name-only","-r","HEAD").splitlines() if x]
    expected=expected_runtime_bindings(root)
    validate_arm_document(arm,expected,actual_head=head,actual_parent=parent,changed_paths=changed,result_present=(root/RESULT_REL).exists(),lock_present=(root/LOCK_REL).exists())
    staging=validate_staging_certificate(root); cert=load_json(root/STAGING_REL)
    ancestry=subprocess.run(["git","-C",str(root),"merge-base","--is-ancestor",cert["staging_commit"],parent])
    require(ancestry.returncode==0,"staging commit is not an ancestor of the validated pre-arm parent")
    for item in cert["encrypted_parts"]:
        unchanged=subprocess.run(["git","-C",str(root),"diff","--quiet",cert["staging_commit"],parent,"--",item["filename"]])
        require(unchanged.returncode==0,f"encrypted part changed after staging commit: {item['filename']}")
    return {"schema":"mxm.research-core-v4.recovery-v3-runtime-prearm-validation.v1","status":"PASS_ALL_PRELOCK_PREOPEN_GATES","arm_commit":head,"pre_arm_parent_head":parent,"staging_status":staging["status"],"response_opened":False,"attempt_lock_persisted_by_gate":False}

def verify_plaintext_directory(raw_root:Path,root:Path=ROOT)->dict:
    expected=_exact_series(root); wanted={f"{int(x['symbol_id'])}_M5.csv":x for x in expected}
    actual={p.name for p in raw_root.glob("*_M5.csv") if p.is_file()}; require(actual==set(wanted),"plaintext staged directory file-set differs from exact 18-series set")
    rows_out=[]
    for name in sorted(wanted,key=lambda n:int(n.split("_")[0])):
        item=wanted[name]; path=raw_root/name; require(sha256_file(path)==item["series_sha256"],f"plaintext SHA256 mismatch: {name}")
        with path.open("r",encoding="utf-8",newline="") as f:
            reader=csv.DictReader(f); require("time_utc" in (reader.fieldnames or []),f"time_utc absent: {name}")
            count=0; first=None; last=None
            for row in reader:
                t=row["time_utc"]; first=t if first is None else first; last=t; count+=1
        require(count==item["row_count"],f"plaintext row count mismatch: {name}")
        require(first==item["first_timestamp_utc"],f"plaintext first timestamp mismatch: {name}")
        require(last==item["last_timestamp_utc"],f"plaintext last timestamp mismatch: {name}")
        rows_out.append({"symbol":item["symbol"],"symbol_id":item["symbol_id"],"sha256":item["series_sha256"],"row_count":count,"first_timestamp_utc":first,"last_timestamp_utc":last,"source_archive_sha256":item["source_archive_sha256"]})
    return {"status":"PASS_EXACT_18_PLAINTEXT_SERIES","series":rows_out,"response_opened":False}

def main()->None:
    ap=argparse.ArgumentParser(); ap.add_argument("--validate-runtime",action="store_true"); ap.add_argument("--validate-staging-only",action="store_true"); ap.add_argument("--verify-plaintext-dir",type=Path)
    args=ap.parse_args(); selected=int(args.validate_runtime)+int(args.validate_staging_only)+int(args.verify_plaintext_dir is not None)
    if selected!=1: raise SystemExit("choose exactly one validation mode")
    out=validate_runtime_gate(ROOT) if args.validate_runtime else validate_staging_certificate(ROOT) if args.validate_staging_only else verify_plaintext_directory(args.verify_plaintext_dir,ROOT)
    print(json.dumps(out,sort_keys=True))

if __name__=="__main__": main()
