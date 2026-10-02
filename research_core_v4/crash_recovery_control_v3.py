from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
S="research_core_v4/state/"
STATE=ROOT/(S+"V4_STATE.json"); AUTH=ROOT/(S+"FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_AUTHORITY_V3.json")
BENCH=ROOT/(S+"V4_GREENFIELD_REFERENCE_RUNTIME_BENCHMARK_RESULT_V1.json"); EQUIV=ROOT/(S+"V4_GREENFIELD_EXECUTION_SEMANTIC_EQUIVALENCE_V1.json")
ARCH=ROOT/(S+"V4_GREENFIELD_EXECUTION_ARCHITECTURE_V1.json"); TRANSPORT=ROOT/(S+"V4_GREENFIELD_ENCRYPTED_INPUT_TRANSPORT_V1.json")
SUPER=ROOT/(S+"V4_PRIVATE_RUNTIME_PROPOSAL_SUPERSESSION_V1.json"); TEMPLATE=ROOT/"research_core_v4/runtime/v4_greenfield_recovery_v3_runtime_template.yml"
HIST={
S+"FIRST_V4_DEVELOPMENT_RESPONSE_OPENING_LOCK_V1.txt":"1e75c3a2e9aeaf6099e57545ad9fb62ca3311445",
S+"FIRST_V4_DEVELOPMENT_RESPONSE_OPENING_INTERRUPTION_V1.json":"f0d94c13d14a61be297d401b63d62cd4d9f2ac4d",
S+"FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_AUTHORITY_V1.json":"174555058661b6cc03d9e1a30e95aaa7a79586da",
S+"FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_LOCK_V1.txt":"b6b189b17e8af8f06e2d5cd3ef11dda9069ede89",
S+"FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_ATTEMPT_V1.json":"e71021da081f400f20f5d7278526ccd1a06086ca",
S+"FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_EXECUTION_OPENING_LOCK_V1.txt":"1e75c3a2e9aeaf6099e57545ad9fb62ca3311445",
S+"FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_FAILURE_V1.json":"911811af014c2179cf3289245530569b8e419f0d"}
PRIVATE={
S+"V4_EXECUTION_SURFACE_DECISION_V1.json":"9b6f03d7f13eb2dcb9bea3a46a4323443d13b4d3",
S+"V4_PRIVATE_INPUT_TRANSPORT_DECISION_V1.json":"b0571e7da70745d8996374828c888b7add95f053",
"research_core_v4/runtime/v4_recovery_v2_private_runtime_template.yml":"c700cba0acd1d963d83a42fdb970342b32009b2d",
S+"FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_AUTHORITY_V2.json":"e293affbea4c6d3e96b671d8914d0ec8fbe750e8"}
SCI={
S+"FIRST_REAL_MARKET_DESIGN_V2.json":"3f9a6b1da92b9904da91e86d005f26e8e99d93e5e3497e1b8a72b59b1d4e590e",
"research_core_v4/response_evaluator_v3.py":"bb846fb3bbbe567c53587a6c22b344ffe39af7129db5e9a4a39c77026f3ade2a",
"research_core_v4/development_execution_runner_v1.py":"cebcf2ad4f88e40d575cb46ffc14e0862107b47a84260a15b3310f075af4f79d",
"research_core_v4/frozen_v2_semantics.py":"0a7bda1afe5cbe79373ee833e9d09febc08721d1826d94435f74d900f74f26ed"}
RESULTS=(S+"FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json",S+"FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json.tmp","V4_FIRST_DEVELOPMENT_RESPONSE_RESULT_V1.json","V4_FIRST_DEVELOPMENT_RESPONSE_RESULT_V1.json.tmp")
ARM=ROOT/(S+"FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_V3_ARM_V1.json")
STAGING=ROOT/(S+"FIRST_V4_DEVELOPMENT_RESPONSE_RECOVERY_V3_GREENFIELD_INPUT_STAGING_CERTIFICATE_V1.json")
def load(p): return json.loads(p.read_text(encoding="utf-8"))
def sha256(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def blob(p):
 d=p.read_bytes(); return hashlib.sha1(b"blob "+str(len(d)).encode()+b"\0"+d).hexdigest()
def req(c,m):
 if not c: raise PermissionError("RECOVERY_V3_CONTROL_FAIL "+m)
def verify_staged_directory(root,auth):
 from research_core_v4 import development_execution_runner_v1 as r
 out={}
 for x in auth["frozen_reference"]["exact_18_series"]:
  sid=int(x["symbol_id"]); p=root/f"{sid}_M5.csv"; req(p.exists(),f"missing staged series {sid}")
  bars,d=r.verify_series_file(p,x); out[str(sid)]={"sha256":d,"rows":len(bars)}
 req(len(out)==18,"staged series count"); return out
def validate_current_control_plane():
 st=load(STATE); a=load(AUTH); b=load(BENCH); e=load(EQUIV); ar=load(ARCH); tr=load(TRANSPORT); su=load(SUPER)
 for p,h in HIST.items(): req(blob(ROOT/p)==h,"historical bytes changed: "+p)
 for p,h in PRIVATE.items(): req(blob(ROOT/p)==h,"private proposal bytes changed: "+p)
 for p,h in SCI.items(): req(sha256(ROOT/p)==h,"frozen science changed: "+p)
 req(su["status"].startswith("SUPERSEDED_BEFORE_ARM_OR_REAL_EXECUTION"),"private proposal not superseded")
 req(b["status"]=="PASS_REFERENCE_SOURCE_RUNTIME_WITH_SAFE_MARGIN" and b["evidence_boundary"]["synthetic_only"] and not b["evidence_boundary"]["real_market_response_values_used"],"runtime evidence boundary")
 req(b["full_synthetic_result"]["event_count"]==118262 and b["measured_margin_multiple_vs_available_limit"]>10,"runtime margin")
 req(e["status"]=="PASS_EXACT_REFERENCE_BYTE_IDENTITY_NO_REIMPLEMENTATION" and e["execution_implementation"]["identity_with_reference"] and not e["execution_implementation"]["fast_reimplementation_created"],"semantic identity")
 req(ar["canonical_repository"]=="mariancradulescu/mxm-quant-greenfield" and not ar["current_authorization"]["real_development_response_execution"],"architecture authorization")
 req(not tr["staging_certificate_present_now"] and not tr["real_execution_authorized"],"transport authorization")
 req(a["status"]=="PREPARED_NOT_ARMED_NOT_EXECUTED" and not a["real_development_response_execution_authorized"] and not a["arm_authorized"],"authority status")
 req(a["accepted_canonical_result_count_at_prepare"]==0 and a["accepted_canonical_result_limit"]==1 and not a["automatic_retry"] and a["future_process_attempt_limit_after_explicit_arm"]==1,"authority result/retry")
 req(len(a["frozen_reference"]["exact_18_series"])==18 and a["frozen_reference"]["execution_is_byte_identical_to_reference"],"reference binding")
 fw=st["first_wave"]; p=st["recovery_v3_preparation"]; g=st["governance"]
 req(st["status"]=="FIRST_REAL_MARKET_DESIGN_V2_GREENFIELD_RECOVERY_V3_PREPARED_NOT_ARMED_NOT_EXECUTED","state status")
 req(fw["development_outcomes_opened"] and not fw["development_execution_completed"] and not fw["development_raw_result_persisted"] and not fw["development_result_interpreted"],"development state")
 req(not fw["deterministic_crash_recovery_authorized"] and not fw["further_recovery_attempt_authorized"] and not fw["current_recovery_execution_authorized"],"current recovery authorization")
 req(p["status"]=="PREPARED_NOT_ARMED_NOT_EXECUTED" and p["canonical_repository"]=="mariancradulescu/mxm-quant-greenfield" and not p["second_repository_allowed"],"V3 prep")
 req(not p["input_staging_certificate_present"] and not p["arm_present"] and not p["real_execution_authorized"] and p["accepted_canonical_result_count"]==0 and p["accepted_canonical_result_limit"]==1 and p["process_attempts_started"]==0 and not p["automatic_retry"],"V3 boundary")
 req(not fw["confirmation_execution_authorized"] and not fw["confirmation_outcomes_opened"] and not g["broker_acquisition_authorized"] and not g["protected_forward_opened"] and not g["candidate_promotion_authorized"] and not g["live_trading_started"],"downstream opened")
 req(not ARM.exists() and not STAGING.exists(),"ARM or staging certificate exists")
 req(not [x for x in RESULTS if (ROOT/x).exists()],"canonical result exists")
 t=TEMPLATE.read_text(); req("mxm-quant-director" not in t and "68bdee4b51244ae50acd56fe868468b96106450f" in t,"runtime template binding")
 return {"schema":"mxm.research-core-v4.greenfield-recovery-v3-control-validation.v1","status":"PASS_GREENFIELD_RECOVERY_V3_PREPARED_NOT_ARMED_NO_REAL_RESPONSE_EXECUTION","accepted_canonical_result_count":0,"accepted_canonical_result_limit":1,"real_execution_authorized":False,"arm_present":False,"input_staging_present":False,"process_attempts_started":0,"scientific_source_unchanged":True,"historical_locks_unchanged":True,"private_runtime_proposal_preserved_and_superseded":True,"execution_is_byte_identical_reference":True,"runtime_margin_multiple":b["measured_margin_multiple_vs_available_limit"]}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--verify-staged-directory",type=Path); x=ap.parse_args(); a=load(AUTH)
 print(json.dumps({"status":"PASS_STAGED_EXACT_18_SERIES","series":verify_staged_directory(x.verify_staged_directory,a)},sort_keys=True) if x.verify_staged_directory else json.dumps(validate_current_control_plane(),sort_keys=True))
if __name__=="__main__": main()
