"""Bounded zero-human continuation loop across AI reasoning and AI implementation."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from research_v3.autonomous_control_plane import validate_repository_state
from research_v3.general_ai_director_bridge import drain
from research_v3.general_ai_implementation_executor import execute as implement, implementation_required
from research_v3.general_ai_reasoning_provider import wake as reason, reasoning_required
from research_v3.runtime_v2_primitives import load_json
from research_v3.general_ai_director_bridge import NEXT_STATE_REL

VERSION="MXM_GENERAL_AI_AUTONOMY_LOOP_V1"

def run(root_value=".",*,git_checkpoint=False,git_push=False,max_cycles=8):
    root=Path(root_value).resolve(); trace=[]
    for cycle in range(1,max_cycles+1):
        validate_repository_state(root)
        state=dict(load_json(root/NEXT_STATE_REL,{}) or {})
        if state.get("user_action_required") is True:
            return {"status":"EXTERNAL_USER_ACTION_REQUIRED","cycles":cycle-1,"trace":trace,"next_state":state}
        if reasoning_required(state):
            r=reason(root,git_checkpoint=git_checkpoint,git_push=git_push)
            d=drain(root,git_checkpoint=git_checkpoint,git_push=git_push)
            trace.append({"cycle":cycle,"kind":"GENERAL_AI_REASONING","reasoning":r,"drain_status":d.get("status")})
            continue
        if implementation_required(state):
            out=implement(root,git_checkpoint=git_checkpoint,git_push=git_push)
            trace.append({"cycle":cycle,"kind":"GENERAL_AI_IMPLEMENTATION","result_status":out.get("status")})
            if out.get("status") in {"EXTERNAL_DATA_REQUIRED","PENDING_EXACT_HEAD_GREEN"}:
                return {"status":out["status"],"cycles":cycle,"trace":trace,"result":out}
            continue
        return {"status":"QUIESCENT_NO_ACTION","cycles":cycle-1,"trace":trace,"next_state":state}
    return {"status":"BOUNDED_CONTINUATION_CHECKPOINT","cycles":max_cycles,"trace":trace,
            "next_state":dict(load_json(root/NEXT_STATE_REL,{}) or {})}

def main(argv=None):
    p=argparse.ArgumentParser(description=VERSION); p.add_argument("command",choices=("continue",)); p.add_argument("--root",default=".")
    p.add_argument("--git-checkpoint",action="store_true"); p.add_argument("--git-push",action="store_true"); p.add_argument("--max-cycles",type=int,default=8); a=p.parse_args(argv)
    out=run(a.root,git_checkpoint=a.git_checkpoint,git_push=a.git_push,max_cycles=a.max_cycles)
    print(json.dumps(out,sort_keys=True,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
