"""Additive V2 save-only repair: frozen models generate exactly TWO family rows per event.
Nothing in previously accepted source or original V1 execution code is modified.
"""
import os,json,pathlib,tempfile,subprocess,sys
from datetime import datetime,timezone
from collections import defaultdict
from research_core_v4.pepperstone_continuity_numeric_v1 import runner_v1 as old
from research_core_v4.cost_frequency_discovery_v1.kernel_v1 import FAMILIES
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.executable_coverage_diagnostic_v1.runner_v1 import relay
e=rt.e
P="research_core_v4/pepperstone_continuity_numeric_v1/"
PHASE="GATE_V2"

def deduplicate_saved_family_rows(saved):
    src=saved["events"]
    groups=defaultdict(list)
    for row in src:
        old.need(row["family"] in FAMILIES,"UNRECOGNIZED_FAMILY")
        groups[row["sid"],row["t"],row["h"]].append(row)
    old.need(len(groups)==saved["summary"]["new_predictive_events"],"UNPAIRED_EVENT_COUNT")
    kept=[]
    for key in sorted(groups):
        pair=groups[key]
        old.need(len(pair)==len(FAMILIES) and
                 set(z["family"] for z in pair)==set(FAMILIES),"PAIR_IDENTITY")
        p=next(z for z in pair if z["family"]==FAMILIES[0])
        q=next(z for z in pair if z["family"]==FAMILIES[1])
        # Require that price, quote, timing, risk and cost facts agree exactly.
        # Different model-side labels and admissions remain in the original source.
        for name in ("entry","accounts","net_sides","iso","exit","prior"):
            old.need(p.get(name)==q.get(name),"PAIR_BASE_FACT_DRIFT")
        kept.append(p)
    result=dict(saved)
    result["events"]=kept
    return result

def gate():
    h=os.environ["GITHUB_SHA"]
    a=json.loads((e.a.ROOT/(P+"EXECUTION_V2.json")).read_text())
    e.w.v2.runtime(h)
    old.need(a["authority"]=="OWNER_STANDING_PEPPERSTONE_MACHINE_SIDE_READONLY_20261012",
             "STANDING_AUTHORITY")
    old.need(a["stage"]=="FROZEN_V1_SAVED_EVENT_PAIR_CARDINALITY_REPAIR_ONLY",
             "REPAIR_SCOPE")
    old.need(not any(a[k] for k in ("broker_requests","orders","protected_forward",
             "cloud_deployment","closed_exact_replay","new_external_sources",
             "authentication_changes","independent_alpha_promotion")),"SCOPE")
    old.need(os.environ.get("GITHUB_EVENT_NAME")=="push" and
        os.environ.get("GITHUB_WORKFLOW_REF")==e.w.old.REPO+
        "/.github/workflows/mxm-native-saved-economic-recovery-20261012-v2.yml@refs/heads/"+
        e.w.old.BRANCH,"WORKFLOW_SCOPE")
    old.need(datetime.now(timezone.utc).isoformat()<a["expires_utc"],"EXPIRED")
    old.need(e.w.old.api("git/ref/heads/"+e.w.old.BRANCH)["object"]["sha"]==h,
             "LIVE_HEAD_DRIFT")
    e.a.ancestor(a["base_head"],h)
    for path,sha in a["bindings"].items():
        old.need(e.w.old.filehash(path)==sha,"SOURCE_HASH_DRIFT")
    original,current=old.inventory(a["base_head"]),old.inventory(h)
    old.need(all(current.get(p)==v for p,v in original.items()),"FREEZE_PRESERVED")
    e.w.old.verify_science()
    old.need(not e.w.v2.existing_ref(a["one_use_ref"]),"ONEUSE_ALREADY_CONSUMED")
    e.w.old.api("git/refs",{"ref":"refs/tags/"+a["one_use_ref"],"sha":h})
    return h,a

def selftest():
    src={"summary":{"new_predictive_events":1},
         "events":[{"family":fam,"sid":1,"t":1736294400,"h":15,
                    "entry":{"eligible":True},"accounts":{"x":[1,2]},
                    "net_sides":[.1,-.2],"iso":"2025-W02","exit":1736295300,
                    "prior":{"r":1},"model_side":1 if i==0 else -1}
                    for i,fam in enumerate(FAMILIES)]}
    out=deduplicate_saved_family_rows(src)
    assert len(out["events"])==1 and len(src["events"])==2
    src["events"][1]["accounts"]["x"][0]=4
    try:
        deduplicate_saved_family_rows(src)
    except Exception:
        print("PASS_FROZEN_TWO_FAMILY_DEDUP_AND_DRIFT_FAILCLOSED",flush=True)
    else:
        raise AssertionError("UNDETECTED_PAIR_DRIFT")

def main():
    global PHASE
    os.umask(0o077)
    h,a=gate()
    with tempfile.TemporaryDirectory(prefix="mxm-native-recovery-v2-",dir=os.environ["RUNNER_TEMP"]) as td:
        tmp=pathlib.Path(td)
        PHASE="OWNER_KEY_AND_AUTHENTIC_CIPHER_V2"
        key,fp=e.w.old._private_key_from_secret(tmp)
        old.need(fp==e.w.old.FP,"OWNER_KEY_FINGERPRINT")
        saved,provenance=load_asset(key,fp,tmp,a["encrypted_source"])
        PHASE="PAIR_CONSERVATION_AND_NUMERIC_EXISTING_COHORT"
        unpaired_count=len(saved["events"])
        recovered=deduplicate_saved_family_rows(saved)
        out=old.diagnostic(recovered,a["source_head"])
        out["original_frozen_family_rows"]=unpaired_count
        out["distinct_economic_events"]=len(recovered["events"])
        out["family_pair_accounting"]="BOTH_FAMILIES_IDENTICAL_PRICE_COST_FACTS_DIFFERENT_FROZEN_PREDICTIONS"
        out["recovery_v1_failure_ref"]={"run":38239172730,"job":114777229028,
              "exact_code":"EVENT_COUNT","security":"FAILED_CLOSED_AFTER_PRIVATE_DECRYPT_NO_PUBLIC_PLAINTEXT"}
        out["source_provenance"]=provenance
        out["source_ciphertext_sha256"]=a["encrypted_source"]["ciphertext_sha256"]
        compact={k:out[k] for k in ("schema","source_head","classification","scenario",
              "preoutcome_cohort_and_market_support","horizon_week_hindsight_upper_envelope",
              "entry_reasons","MAE_MFE","HARD21","new_broker_requests","orders",
              "independent_replication","original_frozen_family_rows",
              "distinct_economic_events","family_pair_accounting")}
        compact["source_provenance"]=provenance
        PHASE="ENCRYPTED_AUTHENTIC_RESULT_V2"
        rt.output(h,a,tmp,key,"nativecontinuity2",out,compact)
        PHASE="ENCRYPTED_OWNER_SESSION_RELAY_V2"
        relay(h,a,tmp,compact)
        print("PASS_SAVED_PEPPERSTONE_NUMERIC_RESULT_V2_PRIVATE_ONLY",flush=True)

if __name__=="__main__":
    if sys.argv[1:]==["--selftest"]:
        selftest()
    else:
        try:main()
        except Exception as exc:
            rt.fail(exc,PHASE)
            raise SystemExit(1) from None
