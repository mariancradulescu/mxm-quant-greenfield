"""Bind accepted post-C032 work and advance the material evidence epoch once."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from research_v3.autonomous_control_plane import validate_repository_state
from research_v3.evidence_epoch import advance_evidence_epoch
from research_v3.runtime_v2_primitives import atomic_write_json, load_json, sha256_file, iso

EPOCH_REL=Path("research_v3/RESEARCH_EVIDENCE_EPOCH_V1.json")
NEXT_REL=Path("research_v3/runtime_v2_acceptance/NEXT_AUTONOMOUS_STATE.json")
RECOVERY_REL=Path("research_v3/ai_director/PROVIDER_RECOVERY_STATE.json")
ACCEPT_REL=Path("research_v3/EPOCH20_POST_C032_DECISION_ACCEPTANCE_V1.json")
REFS=[
    "research_v3/EPOCH20_POST_C032_INFORMATION_GAIN_DECISION_V1.json",
    "evidence/EPOCH20_C006_SESSION_CALENDAR_PREREQUISITE_AUDIT_V1.json",
    "research_v3/EPOCH20_SERIAL_DEPENDENCE_NON_ECONOMIC_FREEZE_V1.json",
    "evidence/EPOCH20_SERIAL_DEPENDENCE_SCREEN_V1.json",
]

def reconcile(root:Path)->dict:
    root=root.resolve()
    epoch=load_json(root/EPOCH_REL,{})
    if epoch.get("current_epoch")==21:
        receipt=load_json(root/ACCEPT_REL,{})
        if receipt.get("status")=="ACCEPTED_NON_ECONOMIC_POST_C032" and receipt.get("economic_effect",{}).get("attempts_consumed")==0:
            return {"status":"ALREADY_RECONCILED","evidence_epoch":21}
        raise RuntimeError("Epoch 21 exists without matching receipt")
    if epoch.get("current_epoch")!=20:
        raise RuntimeError("Unexpected evidence epoch; reconcile LIVE before mutation")
    recovery=load_json(root/RECOVERY_REL,{})
    if recovery.get("status")!="PROVIDER_AVAILABLE_AFTER_ENTITLEMENT_PROBE":
        raise RuntimeError("Copilot entitlement not proven available")
    state=dict(load_json(root/NEXT_REL,{}) or {})
    if state.get("status")!="C032_RESULT_RECORDED_PENDING_EXACT_HEAD_GREEN" or state.get("accounting")!={"economic_outcomes_opened":28,"v2_attempts_used":20,"v2_search_budget_remaining":64}:
        raise RuntimeError("Unexpected post-C032 state/accounting; no automatic rewrite")
    docs={rel:load_json(root/rel,{}) for rel in REFS}
    decision=docs[REFS[0]]
    result=docs[REFS[3]]
    if decision.get("evidence_epoch_seen")!=20 or decision.get("provider",{}).get("kind")!="EXTERNAL_CHATGPT_GENERAL_REASONING":
        raise RuntimeError("External reasoning provenance/epoch mismatch")
    if result.get("source_zip_sha256")!="64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503" or len(result.get("series",{}))!=40:
        raise RuntimeError("Accepted structural result binding mismatch")
    if result.get("economic_effect")!={"outcomes_opened":0,"attempts_consumed":0,"budget_change":0}:
        raise RuntimeError("Non-economic result altered accounting")
    baseline=validate_repository_state(root)["accounting"]
    receipt={
        "schema":"mxm.greenfield.epoch20-post-c032-decision-acceptance.v1",
        "status":"ACCEPTED_NON_ECONOMIC_POST_C032",
        "accepted_utc":iso(),
        "provider":{"kind":"EXTERNAL_CHATGPT_GENERAL_REASONING","vendor":"OpenAI","model":None},
        "evidence_epoch_seen":20,
        "decision_ref":REFS[0],
        "bound_refs_and_sha256":[{"ref":rel,"sha256":sha256_file(root/rel)} for rel in REFS],
        "finding":"C006 calendar prerequisite unresolved; frozen 40-series serial-dependence screen accepted as descriptive development evidence only.",
        "economic_effect":{"outcomes_opened":0,"attempts_consumed":0,"budget_change":0},
        "protected_forward_opened":False,
        "c032_rerun":False,
    }
    atomic_write_json(root/ACCEPT_REL,receipt)
    reason="Accepted hash-bound external epoch-20 reasoning and completed non-economic 40-symbol M5 structural evidence. C032 remains gross-edge failed and closed only as an exact identity; new descriptive evidence requires one fresh semantic interpretation, without economic rerun or attempt."
    advance_evidence_epoch(root,event_class="MATERIAL_DEVELOPMENT_STRUCTURAL_EVIDENCE_ACCEPTED",
                           refs=[str(ACCEPT_REL),REFS[3]],reason=reason,advanced_utc=iso())
    state.update({
        "status":"FRESH_GENERAL_AI_REASONING_REQUIRED",
        "next_action":"AI_REASSESS_HIGHEST_INFORMATION_LEGAL_NEXT_ACTION_FROM_CURRENT_EVIDENCE_EPOCH",
        "ai_reasoning_required":True,
        "research_judgment_required":True,
        "user_action_required":False,
        "current_research_evidence_epoch":21,
        "authorizing_evidence_epoch":20,
        "external_data_gate":None,
        "post_c032_decision_acceptance_ref":str(ACCEPT_REL),
        "latest_material_structural_result_ref":REFS[3],
        "reason":reason,
    })
    atomic_write_json(root/NEXT_REL,state)
    after=validate_repository_state(root)["accounting"]
    if after!=baseline:
        raise RuntimeError("Reconciliation changed economic accounting")
    return {"status":"RECONCILED_FRESH_REASONING_REQUIRED","evidence_epoch":21,
            "accounting":after,"receipt_ref":str(ACCEPT_REL)}

def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--root",default=".")
    args=p.parse_args()
    print(json.dumps(reconcile(Path(args.root)),sort_keys=True))

if __name__=="__main__":
    main()
