"""V3 last bounded attempt: correct one SHA256 manifest typo without changing model or reducer."""
import os,json,sys
from datetime import datetime,timezone
from research_core_v4.pepperstone_continuity_numeric_v1 import runner_v1 as original
from research_core_v4.pepperstone_continuity_numeric_v1 import runner_v2 as previous
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
e=rt.e
P="research_core_v4/pepperstone_continuity_numeric_v1/"
def gate_v3():
    h=os.environ["GITHUB_SHA"]
    a=json.loads((e.a.ROOT/(P+"EXECUTION_V3.json")).read_text())
    e.w.v2.runtime(h)
    original.need(a["authority"]=="OWNER_STANDING_PEPPERSTONE_MACHINE_SIDE_READONLY_20261012","OWNER_AUTHORITY")
    original.need(a["stage"]=="FINAL_SHA_CORRECTION_OF_NATIVE_SAVED_PAIR_RECOVERY","STAGE")
    original.need(not any(a[k] for k in ("broker_requests","orders","protected_forward",
      "cloud_deployment","closed_exact_replay","new_external_sources",
      "authentication_changes","independent_alpha_promotion")),"READ_ONLY_SCOPE")
    original.need(os.environ.get("GITHUB_EVENT_NAME")=="push" and
      os.environ.get("GITHUB_WORKFLOW_REF")==e.w.old.REPO+
      "/.github/workflows/mxm-native-saved-economic-recovery-20261012-v3.yml@refs/heads/"+
      e.w.old.BRANCH,"TRIGGER_SCOPE")
    original.need(datetime.now(timezone.utc).isoformat()<a["expires_utc"],"EXPIRED")
    original.need(e.w.old.api("git/ref/heads/"+e.w.old.BRANCH)["object"]["sha"]==h,"HEAD_DRIFT")
    e.a.ancestor(a["base_head"],h)
    for path,hash_expected in a["bindings"].items():
        original.need(e.w.old.filehash(path)==hash_expected,"EXACT_SOURCE_HASH_DRIFT")
    older,newer=original.inventory(a["base_head"]),original.inventory(h)
    original.need(all(newer.get(path)==blob for path,blob in older.items()),"EXISTING_SOURCE_CHANGED")
    e.w.old.verify_science()
    original.need(not e.w.v2.existing_ref(a["one_use_ref"]),"INVOCATION_CONSUMED")
    e.w.old.api("git/refs",{"ref":"refs/tags/"+a["one_use_ref"],"sha":h})
    return h,a
if __name__=="__main__":
    if sys.argv[1:]==["--selftest"]:
        original.selftest()
        previous.selftest()
    else:
        previous.gate=gate_v3
        previous.main()
