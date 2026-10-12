"""One-use, additive path identity correction for encrypted decision readback.
Prior readback source and the failed V1 action remain byte-identical.
"""
import os, json, sys
from datetime import datetime, timezone
from research_core_v4.pepperstone_decision_readback_20261012_v1 import runner_v1 as first
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt

e=rt.e
P="research_core_v4/pepperstone_decision_readback_20261012_v1/"

def gate_v2():
    head=os.environ["GITHUB_SHA"]
    a=json.loads((e.a.ROOT/(P+"EXECUTION_V2.json")).read_text())
    e.w.v2.runtime(head)
    first.need(a["authority"]=="OWNER_STANDING_PEPPERSTONE_MACHINE_SIDE_READONLY_20261012",
               "STANDING_AUTHORITY")
    first.need(a["scope"]=="ONE_USE_ONLY_PRIVATE_DECISION_READBACK_EXISTING_SUCCESS_RESULT_V2",
               "SCOPE")
    for k in ("broker_requests","orders","protected_forward","cloud_deployment",
              "new_external_sources","scientific_replay","independent_alpha_promotion"):
        first.need(a[k] is False, "NO_EXTERNAL_OR_ORDER_SCOPE")
    expected=e.w.old.REPO+("/.github/workflows/"
       "mxm-owner-private-decision-readback-20261012-v2.yml@refs/heads/")+
       e.w.old.BRANCH
    first.need(os.environ.get("GITHUB_EVENT_NAME")=="push", "PUSH_ONLY")
    first.need(os.environ.get("GITHUB_WORKFLOW_REF")==expected,
               "CORRECTED_WORKFLOW_PATH_MATCH")
    first.need(datetime.now(timezone.utc).isoformat()<a["expires_utc"],
               "ONE_USE_EXPIRY")
    first.need(e.w.old.api("git/ref/heads/"+e.w.old.BRANCH)["object"]["sha"]==head,
               "HEAD_DRIFT")
    e.a.ancestor(a["base_head"],head)
    old,now=first.inventory(a["base_head"]),first.inventory(head)
    first.need(all(now.get(k)==v for k,v in old.items()), "IMMUTABLE_OLD_SOURCES")
    for path,expect in a["bindings"].items():
        first.need(e.w.old.filehash(path)==expect,"SOURCE_BINDING")
    e.w.old.verify_science()
    first.need(not e.w.v2.existing_ref(a["one_use_ref"]), "ONE_USE_CONSUMED")
    e.w.old.api("git/refs",{"ref":"refs/tags/"+a["one_use_ref"],"sha":head})
    return head,a

if __name__=="__main__":
    if sys.argv[1:]==["--selftest"]:
        first.selftest()
        print("PASS_CORRECTED_DECISION_READBACK_WORKFLOW_ID_SELFTEST",flush=True)
    else:
        first.gate=gate_v2
        first.main()
