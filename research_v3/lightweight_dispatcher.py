"""Lightweight read-only dispatcher for Actions control-plane routing."""
from __future__ import annotations
import argparse, json, os
from pathlib import Path
from typing import Any

from research_v3.execution_router import classify_execution, liveness_fingerprint
from research_v3.general_ai_director_bridge import NEXT_STATE_REL
from research_v3.runtime_v2_primitives import load_json

DEDUP_REL=Path("research_v3/LIVENESS_DEDUP_V1.json")

def classify(root_value:str|Path=".")->dict[str,Any]:
    root=Path(root_value).resolve()
    state=dict(load_json(root/NEXT_STATE_REL,{}) or {})
    route=classify_execution(root,state)
    fp=liveness_fingerprint(root,state)
    dedup=load_json(root/DEDUP_REL,{}) or {}
    completed=dedup.get("last_completed_fingerprint")
    duplicate=bool(completed and completed==fp)
    execution_class=route["execution_class"]
    dispatch_required=execution_class in {
        "DETERMINISTIC_OPERATION","SEMANTIC_REASONING","NOVEL_AI_IMPLEMENTATION",
        "ECONOMIC_EXECUTION","CTRADER_BUILD_OR_CERTIFICATION","AUTHORITY_CI",
    } and not duplicate
    return {
        **route,
        "liveness_fingerprint":fp,
        "duplicate_completed_fingerprint":duplicate,
        "dispatch_required":dispatch_required,
        "status":state.get("status"),
        "next_action":state.get("next_action"),
        "evidence_epoch":state.get("current_research_evidence_epoch") or state.get("evidence_epoch"),
    }

def _write_outputs(path:str,payload:dict[str,Any])->None:
    pairs={
        "execution_class":payload["execution_class"],
        "fingerprint":payload["liveness_fingerprint"],
        "duplicate":"true" if payload["duplicate_completed_fingerprint"] else "false",
        "dispatch_required":"true" if payload["dispatch_required"] else "false",
    }
    with open(path,"a",encoding="utf-8") as f:
        for k,v in pairs.items():
            f.write(f"{k}={v}\n")

def main(argv=None)->int:
    p=argparse.ArgumentParser()
    p.add_argument("command",choices=("classify",))
    p.add_argument("--root",default=".")
    p.add_argument("--github-output",default="")
    a=p.parse_args(argv)
    out=classify(a.root)
    if a.github_output:
        _write_outputs(a.github_output,out)
    print(json.dumps(out,sort_keys=True,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
