"""Secure, one-use re-entry into EXISTING Pepperstone economic data. No new broker sends.
Outcomes are used ONLY for a labelled hindsight feasibility envelope, never to pick a tradable signal.
"""
import os, json, pathlib, tempfile, subprocess, math, sys
from datetime import datetime, timezone
from collections import defaultdict, Counter
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.executable_coverage_diagnostic_v1.runner_v1 import relay

e = rt.e
P = "research_core_v4/pepperstone_continuity_numeric_v1/"
PHASE = "GATE"

def need(test, code):
    e.w.old.need(bool(test), code)

def inventory(ref):
    return dict(row.split("\t", 1)[::-1] for row in
                subprocess.check_output(["git", "ls-tree", "-r", ref],
                                        cwd=e.a.ROOT, text=True).splitlines())

def num(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    z = float(value)
    return z if math.isfinite(z) else None

def diagnostic(source, original_sha):
    """Measure ONLY cost/quote support and impossible-to-trade hindsight ceilings.
    Every source entry remains in the denominator; censored exits remain censored.
    This is NOT a predictor, comparison selection, or strategy performance estimate.
    """
    need(source.get("all_original_exacts_unchanged") is True, "SOURCE_FREEZE")
    s = source["summary"]
    need(s["source_head"] == original_sha, "SAVED_HEAD")
    events = source["events"]
    need(len(events) == s["new_predictive_events"], "EVENT_COUNT")
    eligible_weeks = set(s["weeks"])
    need(len(eligible_weeks) == 40, "FROZEN_40_WEEK_SUPPORT")
    need(int(s["stage_a_count"]) <= 192 and int(s["deep_count"]) <= 64,
         "FROZEN_COHORT_SCOPE")
    keys = set()
    table = defaultdict(lambda: dict(entries=0, entry_admissible=0,
                       both_sides_priced=0, priced_eligible=0, positive_hindsight=0,
                       positive_hindsight_distinct_clocks=set(), negative_both=0,
                       positive_model_observed=0, gross_side_eur=0.0,
                       net_side_eur=0.0, all_cost_side_eur=0.0))
    reasons = Counter()
    class_support = Counter()
    n_horizon = Counter()
    for rec in events:
        sid = rec["sid"]
        t = rec["t"]
        h = rec["h"]
        iso = rec["iso"]
        need(isinstance(sid,int) and isinstance(t,int) and
             h in (15,60,240) and iso in eligible_weeks, "EVENT_DOMAIN")
        need(t+60*h < int(datetime(2026,9,17,tzinfo=timezone.utc).timestamp()),
             "PROTECTED_FORWARD_DOMAIN")
        key = (sid,t,h)
        need(key not in keys, "DUPLICATE_EVENT")
        keys.add(key)
        z = table[(iso,h)]
        z["entries"] += 1
        n_horizon[h] += 1
        en = rec.get("entry",{})
        reason = en.get("state","UNKNOWN_ENTRY")
        reasons[str(reason)] += 1
        class_support[(str(rec.get("class","UNKNOWN")),h)] += 1
        is_eligible = en.get("eligible") is True
        if is_eligible:
            margin = num(en.get("margin_eur"))
            risk = num(en.get("risk_eur"))
            if margin is None or risk is None or margin > 80 or risk > 2 or margin < 0 or risk < 0:
                is_eligible = False
                reasons["CONSERVATIVE_MISSING_OR_ABOVE_EUR200_MARGIN_RISK"] += 1
        if is_eligible:
            z["entry_admissible"] += 1
        scenarios = rec.get("accounts") or {}
        two = scenarios.get("S2_F010_DAY")
        if not isinstance(two,list) or len(two)!=2 or not all(isinstance(x,dict) for x in two):
            continue
        m = [num(side.get("net_eur")) for side in two]
        g = [num(side.get("gross_eur")) for side in two]
        if any(x is None for x in m+g):
            continue
        z["both_sides_priced"] += 1
        if not is_eligible:
            continue
        z["priced_eligible"] += 1
        # This maximizes hindsight after reading outcomes: an optimistic diagnostic
        # not an allowed trade decision, upper bound on opportunity availability only.
        idx = 0 if m[0]>=m[1] else 1
        z["gross_side_eur"] += g[idx]
        z["net_side_eur"] += m[idx]
        z["all_cost_side_eur"] += g[idx]-m[idx]
        if m[0] <= 0 and m[1] <= 0:
            z["negative_both"] += 1
        if m[idx] > 0:
            z["positive_hindsight"] += 1
            z["positive_hindsight_distinct_clocks"].add(t)
        # Model results are separately stored in the original source; the
        # present diagnostic never recomputes, reselects, or rebrands them.
    complete = []
    for h in (15,60,240):
        weeks = []
        for w in s["weeks"]:
            v = table[w,h]
            v = dict(v)
            v["positive_hindsight_distinct_clocks"] = len(v["positive_hindsight_distinct_clocks"])
            v["iso"] = w
            v["horizon_minutes"] = h
            v["optimistic_ge21_tickets"] = v["positive_hindsight"] >= 21
            v["optimistic_ge21_distinct_clocks"] = v["positive_hindsight_distinct_clocks"]>=21
            weeks.append(v)
        complete.append({"horizon_minutes":h,
                         "weeks":weeks,
                         "weeks_with_21_hindsight_positive_tickets":sum(w["optimistic_ge21_tickets"] for w in weeks),
                         "weeks_with_21_hindsight_positive_distinct_clocks":sum(w["optimistic_ge21_distinct_clocks"] for w in weeks),
                         "missing_every_other_week":True,
                         "consecutive_iso_week_proof":"NOT_POSSIBLE_FROM_FROZEN_EVERY14DAY_SAMPLE"})
    return {
      "schema":"mxm.private.saved.costfrequency.20261012.economic.headroom.v1",
      "source_head":original_sha,
      "classification":"SAVED_ECONOMIC_NUMERIC_DIAGNOSTIC_NO_NEW_PREDICTOR",
      "denominator":"ALL_FROZEN_NATIVE_DEVELOPMENT_EVENTS_INCLUDING_CENSORED_AND_REJECTED",
      "hindsight_selection_prohibited_for_strategy":True,
      "hindsight_net_not_tradable_not_alpha":True,
      "validity_of_old_dated_terms":"CURRENT_REFERENCE_NOT_HISTORICAL_EXECUTION",
      "scenario":"S2_F010_DAY_TWO_BPS_PER_SIDE_AND_0.10_EUR_PER_DAY_FUNDING_STRESS",
      "one_position_optimistic_21_events_not_concurrent_cash_solvable":True,
      "capital":{"starting_eur":200,"risk_aggregate_max_eur":2,
                 "margin_aggregate_max_eur":80,"reserve_min_eur":120},
      "preoutcome_cohort_and_market_support":{
        "catalog":s["catalog"],"stage_a_count":s["stage_a_count"],
        "stage_a_four_period_pass":s["stage_a_four_period_pass"],
        "deep_count":s["deep_count"],
        "fixed_cohort_frames":s["fixed_cohort_frames"],
        "quote_accepted_frames":s["quote_accepted_frames"],
        "quote_required_boundaries":s["quote_required_boundaries"],
        "quote_valid_fresh_complete":s["quote_valid_fresh_complete"],
        "requests":s["requests"],"new_predictive_events":len(events),
        "resource_limited_frames":s["resource_limited_frames"]},
      "entry_reasons":dict(reasons),
      "horizon_count":dict(n_horizon),
      "class_support":[{"class":k[0],"horizon":k[1],"count":n}
                       for k,n in sorted(class_support.items())],
      "horizon_week_hindsight_upper_envelope":complete,
      "original_predictive_family_reports":s.get("predictive"),
      "original_portfolio_matched_baselines":s.get("portfolios"),
      "original_feasibility":s.get("feasibility"),
      "MAE_MFE":"NOT_AVAILABLE_FROM_ENDPOINT_ONLY_EVENTS;NEEDS_CAUSAL_INTRATRADE_M5_OR_TICK_REUSE",
      "true_fills":"NOT_AVAILABLE","HARD21":"NOT_DEMONSTRATED",
      "independent_replication":"NOT_PERFORMED",
      "new_broker_requests":0,"orders":0,"protected_forward":False,
      "cloud_deployment":False,"closed_exact_replay":False
    }

def gate():
    head = os.environ["GITHUB_SHA"]
    auth = json.loads((e.a.ROOT/(P+"EXECUTION_V1.json")).read_text())
    e.w.v2.runtime(head)
    need(auth["authority"] == "OWNER_STANDING_PEPPERSTONE_MACHINE_SIDE_READONLY_20261012",
         "STANDING_OWNER_AUTHORITY")
    need(auth["stage"] == "SAVED_NUMERIC_RECOVERY_ONLY_ONE_USE", "STAGE_SCOPE")
    need(not any(auth[n] for n in ("broker_requests","orders","protected_forward",
                                  "cloud_deployment","closed_exact_replay","new_external_sources",
                                  "authentication_changes","independent_alpha_promotion")),
         "READ_ONLY_SCOPE")
    need(os.environ.get("GITHUB_EVENT_NAME")=="push" and
         os.environ.get("GITHUB_WORKFLOW_REF")==
           e.w.old.REPO+"/.github/workflows/mxm-pepperstone-continuity-numeric-20261012-v1.yml@refs/heads/"+e.w.old.BRANCH,
         "TRIGGER_SCOPE")
    need(datetime.now(timezone.utc).isoformat()<auth["expires_utc"],"INVOCATION_EXPIRED")
    need(e.w.old.api("git/ref/heads/"+e.w.old.BRANCH)["object"]["sha"]==head,"HEAD_DRIFT")
    e.a.ancestor(auth["base_head"],head)
    for path, sha in auth["bindings"].items():
        need(e.w.old.filehash(path)==sha,"SOURCE_SHA_DRIFT")
    old, current = inventory(auth["base_head"]), inventory(head)
    need(all(current.get(path)==blob for path,blob in old.items()),"OLD_SOURCE_MODIFICATION")
    e.w.old.verify_science()
    need(not e.w.v2.existing_ref(auth["one_use_ref"]),"ONE_USE_CONSUMED")
    e.w.old.api("git/refs", {"ref":"refs/tags/"+auth["one_use_ref"],"sha":head})
    return head,auth

def selftest():
    src={"all_original_exacts_unchanged":True,"summary":{
        "source_head":"a"*40,"new_predictive_events":3,"weeks":[f"2025-W{w:02d}" for w in range(1,41)],
        "stage_a_count":1,"deep_count":1,"catalog":{},"stage_a_four_period_pass":1,
        "fixed_cohort_frames":3,"quote_accepted_frames":3,"quote_required_boundaries":3,
        "quote_valid_fresh_complete":3,"requests":{},"resource_limited_frames":0},
        "events":[]}
    for i in range(3):
        src["events"].append({"sid":1,"t":1736294400+i*3600,"h":15,
            "iso":"2025-W01","class":"FX","entry":{"state":"ELIGIBLE","eligible":True,
                      "margin_eur":20,"risk_eur":1},
            "accounts":{"S2_F010_DAY":[
              {"net_eur":.11,"gross_eur":.17},
              {"net_eur":-.14,"gross_eur":-.08}]}})
    out=diagnostic(src,"a"*40)
    first=out["horizon_week_hindsight_upper_envelope"][0]["weeks"][0]
    assert first["positive_hindsight"]==3 and first["priced_eligible"]==3
    assert first["positive_hindsight_distinct_clocks"]==3
    assert abs(first["all_cost_side_eur"]-.18)<1e-9
    src["events"][0]["entry"]["risk_eur"]=2.1
    assert diagnostic(src,"a"*40)["horizon_week_hindsight_upper_envelope"][0]["weeks"][0]["priced_eligible"]==2
    print("PASS_SYNTHETIC_HEADROOM_ONLY_NO_BROKER",flush=True)

def main():
    global PHASE
    os.umask(0o077)
    head,auth=gate()
    with tempfile.TemporaryDirectory(prefix="mxm-native-recovery-",dir=os.environ["RUNNER_TEMP"]) as td:
        tmp=pathlib.Path(td)
        PHASE="OWNER_KEY_BOUND_AND_SAVED_CIPHER"
        key,fp=e.w.old._private_key_from_secret(tmp)
        need(fp==e.w.old.FP,"OWNER_EXISTING_KEY_FINGERPRINT")
        source,provenance=load_asset(key,fp,tmp,auth["encrypted_source"])
        PHASE="NUMERIC_EXISTING_COHORT_HEADROOM"
        out=diagnostic(source,auth["source_head"])
        out["source_provenance"]=provenance
        out["source_ciphertext_sha256"]=auth["encrypted_source"]["ciphertext_sha256"]
        compact={k:out[k] for k in ("schema","source_head","classification",
          "scenario","preoutcome_cohort_and_market_support","horizon_week_hindsight_upper_envelope",
          "entry_reasons","MAE_MFE","HARD21","new_broker_requests","orders","independent_replication")}
        compact["source_provenance"]=provenance
        PHASE="ENCRYPTED_PRIVATE_RESULTS"
        rt.output(head,auth,tmp,key,"nativecontinuity",out,compact)
        PHASE="ENCRYPTED_PRIVATE_SESSION_READBACK"
        # Reuses existing audited encrypted relay; outputs ciphertext and public status only.
        relay(head,auth,tmp,compact)
        print("PASS_SECURE_EXISTING_NATIVE_NUMERIC_RECOVERY_NO_PUBLIC_OUTCOMES",flush=True)

if __name__=="__main__":
    if sys.argv[1:]==["--selftest"]:
        selftest()
    else:
        try:
            main()
        except Exception as exc:
            rt.fail(exc,PHASE)
            raise SystemExit(1) from None
