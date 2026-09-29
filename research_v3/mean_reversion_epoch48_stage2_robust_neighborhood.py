"""Outcome-blind Epoch48 MEAN_REVERSION per-symbol/context robust-region freeze."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
VERSION="MXM_EPOCH48_MEAN_REVERSION_STAGE2_SYMBOL_CONTEXT_ROBUST_REGION_V2"
FREEZE_REF="research_v3/EPOCH48_MEAN_REVERSION_STAGE2_ROBUST_NEIGHBORHOOD_FREEZE_V1.json"
PROPOSAL_REF="research_v3/ai_director/proposals/AUTO_reason_bf9cd89c9571973945f9c655002fced0.json"
PROPOSAL_FILE_SHA256="ca457153b9d77929b907eccae492322670e00b91772c627769a37ed6c78227d9"; PROPOSAL_ID="AI_E48_MR_FREEZE_01"
E47F="research_v3/EPOCH47_MEAN_REVERSION_WAVE01_COARSE_PARAMETER_REGION_FREEZE_V1.json"; E47F_SHA="cc1276c9fd3934b40db99002cb0f25a76f001efddb0d712f2ac38d5424d85fbb"
E47R="evidence/EPOCH47_MEAN_REVERSION_WAVE01_COARSE_PARAMETER_REGION_SCAN_V1.json"; E47R_SHA="a3864de83ae9ce3650fe266030dc11b9c132e84a51730b65bdb98ce223e58c03"
PLAN="data/EPOCH46_OUTCOME_BLIND_M5_ACQUISITION_WAVE_01_PLAN_V1.json"; PLAN_SHA="70706ee9c04fb262cf38be8c6cbd0fd7450c91e6d870e5c5f80c9301724ae247"
RESULT_REF="evidence/EPOCH48_MEAN_REVERSION_STAGE2_ROBUST_NEIGHBORHOOD_RESULT_V1.json"
LOOKBACKS=(12,24,48,96); THRESHOLDS=(1.0,1.5,2.0); EFFECT_SCENARIOS=(0.5,0.3,0.2); TARGET_POWER=.8; N=33; ZERO="AMD.US-PERP"
class Stage2Error(ValueError): pass
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 try: x=json.loads(Path(p).read_text(encoding="utf-8"))
 except Exception as e: raise Stage2Error(f"unreadable authority: {p}") from e
 if not isinstance(x,dict): raise Stage2Error("authority must be object")
 return x
def bound(root,ref,digest):
 p=Path(root)/ref
 if not p.is_file() or sha(p)!=digest: raise Stage2Error(f"authority hash mismatch: {ref}")
 return read(p)
def idx(c): return LOOKBACKS.index(c[0]),THRESHOLDS.index(c[1])
def _adjacent(a,b):
 la,ta=idx(a); lb,tb=idx(b); return (la==lb and abs(ta-tb)==1) or (ta==tb and abs(la-lb)==1)
def _connected_components(q):
 rem=set(q); out=[]
 while rem:
  s=rem.pop(); stack=[s]; comp=[s]
  while stack:
   x=stack.pop()
   for y in list(rem):
    if _adjacent(x,y): rem.remove(y); stack.append(y); comp.append(y)
  out.append(sorted(comp,key=idx))
 return sorted(out,key=lambda c:(-len(c),c))
def validate_freeze(f,root="."):
 if f.get("schema")!="mxm.greenfield.epoch48-mean-reversion-stage2-robust-neighborhood-freeze.v1" or f.get("status")!="PROSPECTIVELY_FROZEN_NON_ECONOMIC_STAGE2_ROBUST_REGION_IDENTIFICATION" or f.get("evidence_epoch")!=46 or f.get("family")!="MEAN_REVERSION": raise Stage2Error("bad Epoch48 freeze identity")
 law=f.get("stage2_neighborhood_law") or {}
 if law.get("scope_unit")!="SYMBOL_X_MECHANISM_X_CONTEXT_X_ROBUST_PARAMETER_REGION" or "separately for each broker symbol" not in law.get("heterogeneity_rule",""): raise Stage2Error("symbol heterogeneity authority missing")
 blob=json.dumps(law).lower()
 if "bare majority" in blob or "count of power-adequate identities" in blob: raise Stage2Error("unauthorized cohort-majority rule")
 if "0.8" not in law.get("adequate_event_density_rule",""): raise Stage2Error("target power binding missing")
 for sec in (f.get("interpretation_boundary") or {},f.get("safety") or {}):
  if any(v is True for v in sec.values() if isinstance(v,bool)): raise Stage2Error("boundary crossed")
 if f.get("accounting_effect")!={"economic_outcomes_opened":0,"v2_attempts_consumed":0,"search_budget_change":0}: raise Stage2Error("accounting effect")
 a=f.get("authority") or {}
 expected={"accepted_proposal_ref":PROPOSAL_REF,"accepted_proposal_file_sha256":PROPOSAL_FILE_SHA256,"accepted_proposal_id":PROPOSAL_ID,"epoch47_freeze_ref":E47F,"epoch47_freeze_file_sha256":E47F_SHA,"epoch47_scan_ref":E47R,"epoch47_scan_file_sha256":E47R_SHA}
 if any(a.get(k)!=v for k,v in expected.items()): raise Stage2Error("authority binding mismatch")
 p=bound(root,PROPOSAL_REF,PROPOSAL_FILE_SHA256); u=(p.get("decision") or {}).get("universe_methodology") or {}
 if p.get("proposal_id")!=PROPOSAL_ID or u.get("structural_representatives_are_economic_equivalents") is not False or "retain all such identities" not in u.get("selection_procedure",""): raise Stage2Error("proposal methodology mismatch")
 e=bound(root,E47F,E47F_SHA)
 if e.get("dependence_and_power",{}).get("target_power")!=TARGET_POWER or e.get("dependence_and_power",{}).get("standardized_effect_scenarios")!=list(EFFECT_SCENARIOS): raise Stage2Error("Epoch47 power design mismatch")
 r=bound(root,E47R,E47R_SHA)
 if r.get("scope",{}).get("identities_scanned")!=N or r.get("scope",{}).get("authentic_zero_history_identities")!=[ZERO] or r.get("grid",{}).get("symbol_cell_records")!=396 or r.get("grid",{}).get("winner_selection_performed") is not False: raise Stage2Error("Epoch47 scan scope mismatch")
 plan=read(Path(root)/PLAN)
 if plan.get("plan_sha256")!=PLAN_SHA or len(plan.get("symbols") or [])!=34: raise Stage2Error("Epoch46 context plan mismatch")
def contexts(root):
 p=read(Path(root)/PLAN); d={}
 for x in p.get("symbols") or []:
  s=x.get("broker_symbol")
  if s and s!=ZERO: d[s]={k:x.get(k) for k in ("symbol_id","peer_candidate_cohort_id","structural_stratum","minimum_directional_margin_eur","schedule_minutes_per_week")}
 if len(d)!=N: raise Stage2Error("expected 33 contexts")
 return d
def identify_symbol_regions(rows,ctx):
 grid={(l,t) for l in LOOKBACKS for t in THRESHOLDS}; by={}
 for r in rows:
  s=r.get("broker_symbol"); k=(r.get("lookback_bars"),r.get("absolute_standardized_deviation_threshold"))
  if s==ZERO or s not in ctx or k not in grid or k in by.setdefault(s,{}): raise Stage2Error("unexpected/duplicate cell")
  by[s][k]=r
 if set(by)!=set(ctx): raise Stage2Error("symbol/context mismatch")
 out=[]
 for s in sorted(by):
  if set(by[s])!=grid: raise Stage2Error("incomplete symbol grid")
  effects={}
  for eff in EFFECT_SCENARIOS:
   eligible=set(); cells=[]
   for k in sorted(grid,key=idx):
    r=by[s][k]; m=[x for x in r.get("closed_form_power_estimates") or [] if x.get("standardized_effect")==eff]
    if len(m)!=1: raise Stage2Error("power estimate mismatch")
    power=m[0].get("estimated_power"); event_ok=(int(r.get("eligible_contiguous_windows") or 0)>0 and int(r.get("reversal_event_count") or 0)>0 and r.get("event_availability_rate") is not None and float(r.get("event_availability_rate"))>0)
    ok=bool(event_ok and isinstance(power,(int,float)) and not isinstance(power,bool) and power>=TARGET_POWER)
    if ok: eligible.add(k)
    cells.append({"lookback_bars":k[0],"absolute_standardized_deviation_threshold":k[1],"eligible_contiguous_windows":r.get("eligible_contiguous_windows"),"reversal_event_count":r.get("reversal_event_count"),"event_availability_rate":r.get("event_availability_rate"),"dependence_adjusted_effective_date_clusters":r.get("dependence_adjusted_effective_date_clusters"),"estimated_power":power,"response_eligible_pre_response":ok})
   comps=_connected_components(eligible); good=[c for c in comps if len(c)>=2]
   effects[str(eff)]={"standardized_effect":eff,"target_power":TARGET_POWER,"all_12_cells":cells,"supported_parameter_neighborhoods":[[{"lookback_bars":x[0],"absolute_standardized_deviation_threshold":x[1]} for x in c] for c in good],"isolated_cells_rejected":[{"lookback_bars":c[0][0],"absolute_standardized_deviation_threshold":c[0][1]} for c in comps if len(c)==1],"supported_parameter_neighborhood_exists":bool(good)}
  out.append({"broker_symbol":s,**ctx[s],"effect_scenarios":effects,"any_supported_parameter_neighborhood":any(x["supported_parameter_neighborhood_exists"] for x in effects.values())})
 return out
def build_stage2(root="."):
 root=Path(root).resolve(); f=read(root/FREEZE_REF); validate_freeze(f,root); r=bound(root,E47R,E47R_SHA); rows=r.get("symbols") or []
 if len(rows)!=396: raise Stage2Error("incomplete Epoch47 surface")
 syms=identify_symbol_regions(rows,contexts(root)); summary={str(e):sum(x["effect_scenarios"][str(e)]["supported_parameter_neighborhood_exists"] for x in syms) for e in EFFECT_SCENARIOS}
 return {"schema":"mxm.greenfield.epoch48-mean-reversion-stage2-robust-neighborhood-result.v1","status":"COMPLETE_NON_ECONOMIC_MEAN_REVERSION_STAGE2_SYMBOL_CONTEXT_ROBUST_REGION_IDENTIFICATION","evidence_epoch":46,"research_sequence_label":"EPOCH48","family":"MEAN_REVERSION","implementation":{"version":VERSION,"freeze_ref":FREEZE_REF},"source_authority":{"accepted_proposal_ref":PROPOSAL_REF,"accepted_proposal_file_sha256":PROPOSAL_FILE_SHA256,"epoch47_freeze_ref":E47F,"epoch47_freeze_file_sha256":E47F_SHA,"epoch47_scan_ref":E47R,"epoch47_scan_file_sha256":E47R_SHA,"epoch46_context_plan_ref":PLAN},"scope":{"identities_with_accepted_rows":N,"authentic_zero_history_identity":ZERO,"zero_history_identity_excluded_from_aggregation":True,"development_only":True,"not_independent_confirmation":True,"research_unit":"SYMBOL_X_MECHANISM_X_CONTEXT_X_ROBUST_PARAMETER_REGION","cross_symbol_common_optimum_required":False},"grid":{"lookback_bars":list(LOOKBACKS),"absolute_standardized_deviation_thresholds":list(THRESHOLDS),"cell_count_per_symbol":12,"all_probes_recorded":True,"winner_selection_performed":False},"symbol_context_parameter_regions":syms,"summary":{"symbols_with_supported_regions_by_effect":summary,"symbols_total":N,"symbols_ranked":False,"family_closed":False,"global_parameter_region_selected":False},"later_step":{"stage":"CAUSAL_DEVELOPMENT_RESPONSE_SURFACE_FREEZE","status":"FRESH_SEMANTIC_RESPONSE_LAW_REQUIRED","requires_subsequent_proposal":True,"authorized_by_this_result":False},"interpretation_boundary":{"event_availability_and_power_only":True,"response_return_or_pnl_statistic_opened":False,"post_event_directional_or_return_response_computed":False,"strategy_returns_computed":False,"pnl_computed":False,"economic_outcome_opened":False,"candidate_economic_identity_created":False,"winner_cell_or_symbol_selected":False,"protected_forward_opened":False,"independent_confirmation_claimed":False,"mechanism_family_closed":False,"economic_promotion_authorized":False},"accounting_effect":{"economic_outcomes_opened":0,"v2_attempts_consumed":0,"search_budget_change":0},"safety":{"protected_forward_opened":False,"live_orders_authorized":False,"competition_start_authorized":False}}
def main(argv=None):
 p=argparse.ArgumentParser(); p.add_argument("--root",type=Path,default=Path(".")); p.add_argument("--output",type=Path,default=Path(RESULT_REF)); a=p.parse_args(argv); x=build_stage2(a.root); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(x,sort_keys=True,indent=2,allow_nan=False)+"\n",encoding="utf-8"); print(json.dumps({"status":x["status"],"summary":x["summary"]},sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
