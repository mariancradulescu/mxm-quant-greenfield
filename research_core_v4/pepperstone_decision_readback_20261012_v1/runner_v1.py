"""Read decision-relevant numeric aggregates from ALREADY ENCRYPTED Pepperstone V3 output.
No broker requests, no original model/kernel evaluation, no public private metrics.
"""
import os, json, pathlib, tempfile, subprocess, sys, math
from datetime import datetime, timezone
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.executable_coverage_diagnostic_v1.runner_v1 import relay
from research_core_v4.pepperstone_continuity_numeric_v1 import runner_v1 as prior

e = rt.e
P = "research_core_v4/pepperstone_decision_readback_20261012_v1/"
PHASE = "SOURCE_GUARD"

def need(check, code):
    e.w.old.need(bool(check),code)

def inventory(ref):
    return dict(line.split("\t",1)[::-1] for line in
                subprocess.check_output(["git","ls-tree","-r",ref],
                    cwd=e.a.ROOT,text=True).splitlines())

def number(x):
    need(type(x) in (int,float) and math.isfinite(x), "DECISION_NUMERIC_VALUE")
    return x

def summarize(saved):
    need(saved["schema"]=="mxm.private.saved.costfrequency.20261012.economic.headroom.v1",
         "EXPECTED_RECOVERED_SCHEMA")
    need(saved["classification"]=="SAVED_ECONOMIC_NUMERIC_DIAGNOSTIC_NO_NEW_PREDICTOR",
         "NO_MODEL_PROMOTION")
    need(saved["source_head"]=="962d1afc8918afdc6ad42759c659bc54aa48023e",
         "EXPECTED_ORIGINAL_BROKER_RESEARCH")
    need(saved["HARD21"]=="NOT_DEMONSTRATED" and saved["new_broker_requests"]==0
         and saved["orders"]==0,"NO_LIVE_EXECUTION")
    support=saved["preoutcome_cohort_and_market_support"]
    horizons=saved["horizon_week_hindsight_upper_envelope"]
    need(len(horizons)==3 and sorted(x["horizon_minutes"] for x in horizons)==[15,60,240],
         "FROZEN_HORIZONS")
    need(saved["distinct_economic_events"]==support["new_predictive_events"],
         "PAIRED_EVENT_CONSERVATION")
    need(saved["original_frozen_family_rows"]==2*saved["distinct_economic_events"],
         "TWO_FROZEN_FAMILIES")
    result=[]
    counts_total=0
    for row in sorted(horizons,key=lambda x:x["horizon_minutes"]):
        h=row["horizon_minutes"]
        weeks=row["weeks"]
        need(len(weeks)==40,"FROZEN_WEEKS")
        need(len({w["iso"] for w in weeks})==40,"DISTINCT_WEEK_IDS")
        sums={k:0 for k in ("entries","entry_admissible","both_sides_priced",
          "priced_eligible","positive_hindsight","positive_hindsight_distinct_clocks",
          "negative_both","gross_side_eur","all_cost_side_eur","net_side_eur")}
        rows=[]
        for z in weeks:
            need(z["horizon_minutes"]==h,"HORIZON_ROW")
            for k in sums:sums[k]+=number(z[k])
            en=int(z["entries"])
            elig=int(z["entry_admissible"])
            priced=int(z["both_sides_priced"])
            elpriced=int(z["priced_eligible"])
            favorable=int(z["positive_hindsight"])
            timestamps=int(z["positive_hindsight_distinct_clocks"])
            need(0<=elpriced<=elig<=en and 0<=priced<=en and elpriced<=priced
                and 0<=timestamps<=favorable<=elpriced,"COUNT_MONOTONICITY")
            need(bool(z["optimistic_ge21_tickets"])==(favorable>=21) and
                 bool(z["optimistic_ge21_distinct_clocks"])==(timestamps>=21),
                 "HARD21_WEEK_FLAG_BINDING")
            # Missing quotes and inadmissible entries may overlap: separate exclusion causes.
            rows.append({"iso":z["iso"],"candidate_events":en,
               "structurally_admissible":elig,
               "two_sided_priced":priced,"eligible_priced":elpriced,
               "unpriced_total":en-priced,
               "admissible_but_unpriced":elig-elpriced,
               "structural_rejections":en-elig,
               "positive_best_side_after_outcome":favorable,
               "positive_distinct_clocks":timestamps,
               "optimistic_21_events":favorable>=21,
               "optimistic_21_clocks":timestamps>=21,
               "gross_best_side_eur":z["gross_side_eur"] if elpriced else None,
               "cost_best_side_eur":z["all_cost_side_eur"] if elpriced else None,
               "net_best_side_eur":z["net_side_eur"] if elpriced else None})
        need(sums["entries"]==support["new_predictive_events"]//3,
             "HORIZON_EVENT_CONSERVATION")
        need(int(sums["positive_hindsight"]>=sums["positive_hindsight_distinct_clocks"]),
             "TIMESTAMPS_VS_EVENTS")
        weeks21=sum(1 for z in rows if z["optimistic_21_events"])
        clocks21=sum(1 for z in rows if z["optimistic_21_clocks"])
        need(weeks21==row["weeks_with_21_hindsight_positive_tickets"] and
             clocks21==row["weeks_with_21_hindsight_positive_distinct_clocks"],
             "WEEK_COUNT_IDENTITY")
        counts_total+=sums["entries"]
        sums["structurally_rejected"]=sums["entries"]-sums["entry_admissible"]
        sums["admissible_but_unpriced"]=sums["entry_admissible"]-sums["priced_eligible"]
        sums["two_sided_unpriced"]=sums["entries"]-sums["both_sides_priced"]
        sums["weeks_optimistic_ge21_events"]=weeks21
        sums["weeks_optimistic_ge21_distinct_clocks"]=clocks21
        if not sums["priced_eligible"]:
            for k in ("gross_side_eur","all_cost_side_eur","net_side_eur"):sums[k]=None
        result.append({"horizon_minutes":h,"totals":sums,
                       "sampled_iso_week_rows":rows})
    need(counts_total==support["new_predictive_events"],"GLOBAL_EVENT_CONSERVATION")
    kinds=[]
    for item in result:
        v=item["totals"]
        kinds.append("NO_PRICED_ELIGIBLE_SUPPORT" if not v["priced_eligible"] else
            "NO_21_POSITIVE_DISTINCT_CLOCKS_ON_ANY_SAMPLED_WEEK"
            if v["weeks_optimistic_ge21_distinct_clocks"]==0 else
            "HINDSIGHT_OPPORTUNITY_SUPPORT_ONLY_NOT_CAUSAL_SIGNAL")
    return {"schema":"mxm.private.native.decision.readback.20261012.v1",
       "source_head":saved["source_head"],
       "existing_successful_recovery_run":38239902202,
       "existing_successful_recovery_job":114779637754,
       "source_one_use_recovery_head":"39554ca653a162d27962f72f78ae17c9e86a9c3e",
       "scope":"EXISTING_NUMERIC_FIELDS_REDUCED_NO_NEW_MARKET_OR_PREDICTION_CALCULATION",
       "frozen_scenario":saved["scenario"],
       "starting_capital_eur":200,
       "aggregate_risk_ceiling_eur":2,
       "aggregate_margin_ceiling_eur":80,
       "minimum_cash_reserve_eur":120,
       "horizon_totals_and_sampled_weeks":result,
       "entry_exclusion_reasons":saved["entry_reasons"],
       "source_support":support,
       "local_horizon_classifications":dict(zip((15,60,240),kinds)),
       "original_predictive_family_reports_unchanged":saved["original_predictive_family_reports"],
       "original_portfolio_matched_baselines_unchanged":saved["original_portfolio_matched_baselines"],
       "original_feasibility_unchanged":saved["original_feasibility"],
       "historical_terms":"CURRENT_OCT2026_REFERENCE_NOT_ASOF_2025_EXECUTION_COSTS",
       "hindsight_opportunity":"BEST_SIDE_SELECTED_USING_FUTURE_RETURNS_NOT_TRADABLE",
       "gross_cost_net":"ONLY_BEST_SIDE_AFTER_OUTCOME_PAIRS_NOT_REALIZED_TRADER_RETURN",
       "risk_limit":"PER_EVENT_PROXY_NOT_INTRA_BAR_STRESS_PROOF",
       "MAE_MFE":"NOT_OBSERVABLE_IN_THIS_SAVED_ENDPOINT_ONLY_RESULT",
       "HARD21":"NOT_DEMONSTRATED_NONCONSECUTIVE_SAMPLED_WEEKS_NO_ORDERS",
       "predictor_qualified":False,
       "new_broker_requests":0,"new_trading_orders":0,
       "new_predictive_outcomes_recomputed":0,
       "protected_forward":False,"cloud_deployment":False,
       "scientific_hypotheses_new":0,
       "further_pilot":"NOT_AUTHORIZED_BY_THIS_READBACK",
       "owner_private_only":True}

def gate():
    h=os.environ["GITHUB_SHA"]
    auth=json.loads((e.a.ROOT/(P+"EXECUTION_V1.json")).read_text())
    e.w.v2.runtime(h)
    need(auth["authority"]=="OWNER_STANDING_PEPPERSTONE_MACHINE_SIDE_READONLY_20261012",
         "OWNER_AUTHORITY")
    need(auth["scope"]=="ONE_USE_ONLY_PRIVATE_DECISION_READBACK_EXISTING_SUCCESS_RESULT",
         "LIMITED_READBACK")
    for key in ("broker_requests","orders","protected_forward",
         "cloud_deployment","new_external_sources","scientific_replay",
         "independent_alpha_promotion"):
        need(auth[key] is False,"SCOPE_VIOLATION")
    need(os.environ.get("GITHUB_EVENT_NAME")=="push" and
         os.environ.get("GITHUB_WORKFLOW_REF")==e.w.old.REPO+
         "/.github/workflows/mxm-private-decision-readback-20261012-v1.yml@refs/heads/"+
         e.w.old.BRANCH,"WORKFLOW_TRUST")
    need(datetime.now(timezone.utc).isoformat()<auth["expires_utc"],
         "INVOCATION_EXPIRED")
    need(e.w.old.api("git/ref/heads/"+e.w.old.BRANCH)["object"]["sha"]==h,
         "LIVE_HEAD_DRIFT")
    e.a.ancestor(auth["base_head"],h)
    orig,now=inventory(auth["base_head"]),inventory(h)
    need(all(now.get(k)==v for k,v in orig.items()),"IMMUTABLE_FILES_PRESERVED")
    for path,expected in auth["bindings"].items():
        need(e.w.old.filehash(path)==expected,"SOURCE_SHA_DRIFT")
    e.w.old.verify_science()
    need(not e.w.v2.existing_ref(auth["one_use_ref"]),"ONE_USE_CONSUMED")
    e.w.old.api("git/refs",{"ref":"refs/tags/"+auth["one_use_ref"],"sha":h})
    return h,auth

def selftest():
    # No real source. Check that the reused numeric structure can be aggregated
    # without touching the underlying model or private release.
    head="962d1afc8918afdc6ad42759c659bc54aa48023e"
    weeks=[f"2025-W{1+2*i:02d}" for i in range(26)]+[f"2026-W{1+2*i:02d}" for i in range(14)]
    assert len(set(weeks))==40
    src={"schema":"mxm.private.saved.costfrequency.20261012.economic.headroom.v1",
       "classification":"SAVED_ECONOMIC_NUMERIC_DIAGNOSTIC_NO_NEW_PREDICTOR",
       "source_head":head,"HARD21":"NOT_DEMONSTRATED",
       "new_broker_requests":0,"orders":0,
       "distinct_economic_events":120,
       "original_frozen_family_rows":240,
       "scenario":"S2_F010_DAY",
       "entry_reasons":{},
       "original_predictive_family_reports":{},
       "original_portfolio_matched_baselines":{},
       "original_feasibility":{},
       "preoutcome_cohort_and_market_support":{"new_predictive_events":120},
       "horizon_week_hindsight_upper_envelope":[]}
    for h in (15,60,240):
        slots=[]
        for w in weeks:
            slots.append({"iso":w,"horizon_minutes":h,"entries":1,
                "entry_admissible":1,"both_sides_priced":1,"priced_eligible":1,
                "positive_hindsight":1,"positive_hindsight_distinct_clocks":1,
                "negative_both":0,"gross_side_eur":.14,
                "all_cost_side_eur":.04,"net_side_eur":.10,
                "optimistic_ge21_tickets":False,
                "optimistic_ge21_distinct_clocks":False})
        src["horizon_week_hindsight_upper_envelope"].append({
            "horizon_minutes":h,"weeks":slots,
            "weeks_with_21_hindsight_positive_tickets":0,
            "weeks_with_21_hindsight_positive_distinct_clocks":0})
    report=summarize(src)
    assert len(report["horizon_totals_and_sampled_weeks"])==3
    assert report["horizon_totals_and_sampled_weeks"][0]["totals"]["entries"]==40
    assert abs(report["horizon_totals_and_sampled_weeks"][0]["totals"]["net_side_eur"]-4.0)<.001
    print("PASS_DECISION_READBACK_SYNTHETIC_ACCOUNTING_ONLY",flush=True)

def main():
    global PHASE
    os.umask(0o077)
    h,auth=gate()
    with tempfile.TemporaryDirectory(prefix="mxm-private-decision-readback-",dir=os.environ["RUNNER_TEMP"]) as td:
        tmp=pathlib.Path(td)
        PHASE="OWNER_PRIVATE_KEY_AND_PREVIOUS_ENCRYPTED_RESULT"
        key,fp=e.w.old._private_key_from_secret(tmp)
        need(fp==e.w.old.FP,"OWNER_KEY_IDENTITY")
        saved,proof=load_asset(key,fp,tmp,auth["encrypted_source"])
        PHASE="REDUCE_SAVED_DECISION_RELEVANT_FIELDS"
        result=summarize(saved)
        result["input_ciphertext_provenance"]=proof
        PHASE="OWNER_ENCRYPTED_OUTPUT"
        # Existing signed output + encrypted owner result; no stdout data rows.
        compact={k:v for k,v in result.items() if k not in (
          "original_predictive_family_reports_unchanged",
          "original_portfolio_matched_baselines_unchanged",
          "original_feasibility_unchanged")}
        rt.output(h,auth,tmp,key,"nativedecision",result,compact)
        PHASE="RECIPIENT_ENCRYPTED_SESSION_READBACK"
        relay(h,auth,tmp,compact)
        print("PASS_PRIVATE_DECISION_AGGREGATES_15_60_240_NO_PUBLIC_NUMBERS",flush=True)

if __name__=="__main__":
    if sys.argv[1:]==["--selftest"]:
        selftest()
    else:
        try:main()
        except Exception as err:
            rt.fail(err,PHASE)
            raise SystemExit(1) from None
