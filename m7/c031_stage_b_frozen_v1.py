"""Prospectively frozen C031 Stage-B current-configuration evaluator.
Import is non-economic. Execution requires a separate exact-head-green authorization.
"""
from __future__ import annotations
import bisect,gzip,hashlib,json
from dataclasses import asdict
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from typing import Any,Mapping
from competition.continuous_account_replay_v2 import CapitalEvent, replay_continuous_account, FEASIBLE, UNRESOLVED

VERSION="MXM_C031_STAGE_B_CURRENT_CONFIG_SHARED_ACCOUNT_V1"
SPEC_HASH="4a57910026bc8df63446fa8024ac86a18ce8a732039a9388f704a50bbccfc4e1"
GUARD=Decimal("1.5")
FROZEN={
"C031_STAGE_B_PRE_ECONOMIC_INTENTS_V1.json.gz":("8ee0c9626fa567cdff0f4d1152c0b74760f31ead19fecafdcf8c909e4e69dbcb","de1e6aaf92dff31e16ec9374a3e9bde2b419fffdb77d720ff9cf04ee06310bb3"),
"C031_STAGE_B_PRE_ECONOMIC_MARKET_PATH_V1.json.gz":("475f98f62c4091aa5a71800424fa9e4f206a6aeb5c44b6a30cf050dbbab9fff6","f0f389083bad73d0728648016e3e9c6fbb200bd6d63d582b13d0005ad9ef636b"),
"C031_STAGE_B_CAUSAL_CONVERSION_H1_V1.json.gz":("9aa8ecf6c953fbb0c7e4e402140e58f383f0d49752908370b1fd7b57bb8c29bb","04a6e63ca5192f35b1ca3d2eba3c76e1d16374f51a69d450a100360fcbac8cfe"),
"C031_STAGE_B_BROKER_BINDINGS_V1.json.gz":("d8fc967fca473bfc34187df19ffbd39fa4311aa4bb3850c641ecbc7272e6283d","8a5e4e9b812c239c661e4f33eb3cbda85f334a107047196ddb8d3cc8d295e46a"),
}
class C031StageBError(ValueError): pass

def _d(x): return Decimal(str(x))
def _dt(s): return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc)
def _load(root,name):
 p=Path(root)/name
 if not p.is_file(): raise C031StageBError(f"missing frozen input: {name}")
 b=p.read_bytes(); gz,raw=FROZEN[name]
 if hashlib.sha256(b).hexdigest()!=gz: raise C031StageBError(f"compressed hash drift: {name}")
 data=gzip.decompress(b)
 if hashlib.sha256(data).hexdigest()!=raw: raise C031StageBError(f"raw hash drift: {name}")
 return json.loads(data)

def load_frozen_inputs(root):
 x={"intents":_load(root,list(FROZEN)[0]),"paths":_load(root,list(FROZEN)[1]),"conversion":_load(root,list(FROZEN)[2]),"broker":_load(root,list(FROZEN)[3])}
 if x["intents"]["manifest"]["candidate_spec_hash"]!=SPEC_HASH or x["paths"]["candidate_spec_hash"]!=SPEC_HASH: raise C031StageBError("spec binding drift")
 if len(x["intents"]["intents"])!=129 or x["paths"]["bar_count"]!=1666 or len(x["broker"]["symbols"])!=10: raise C031StageBError("frozen count drift")
 if any(len(x["conversion"]["series"][m])!=1587 for m in ("EURUSD","EURJPY","EURCHF")): raise C031StageBError("conversion count drift")
 return x

class Conversion:
 def __init__(self,doc):
  self.s={}
  for q,m in {"USD":"EURUSD","JPY":"EURJPY","CHF":"EURCHF"}.items():
   rows=doc["series"][m]; self.s[q]=([int(r["timestampMs"])+3600000 for r in rows],[_d(r["close"]) for r in rows])
 def rate(self,quote,ts):
  if quote=="EUR": return Decimal(1)
  if quote not in self.s: raise C031StageBError(f"unsupported quote {quote}")
  a,c=self.s[quote]; i=bisect.bisect_right(a,int(_dt(ts).timestamp()*1000))-1
  if i<0 or c[i]<=0: raise C031StageBError("causal conversion unavailable")
  return Decimal(1)/c[i]

def _events(x,stress=False):
 intents={i["intent_id"]:i for i in x["intents"]["intents"]}; paths={p["intent_id"]:p for p in x["paths"]["paths"]}; conv=Conversion(x["conversion"]); out=[]
 for iid,i in sorted(intents.items(),key=lambda kv:(kv[1]["entry_utc"],kv[1]["symbol"],kv[0])):
  b=x["broker"]["symbols"][i["symbol"]]; p=paths.get(iid)
  if not p or p["entry_utc"]!=i["entry_utc"] or p["exit_utc"]!=i["exit_utc"]: raise C031StageBError("path binding drift")
  bars=p["bars"]; ep=_d(bars[0]["open"]); xp=_d(bars[-1]["open"])
  if ep!=_d(i["entry_price"]) or xp!=_d(i["exit_price"]): raise C031StageBError("price parity drift")
  rate=conv.rate(b["quote_asset"],i["entry_utc"]); units=_d(b["base_units_at_min_volume"]); cost=abs(ep*units*rate)*_d(b["roundtrip_cost_fraction"])
  margin=_d(b["buy_margin_eur_current"] if i["direction"]=="LONG" else b["sell_margin_eur_current"])
  feas=FEASIBLE if b["directional_feasibility_summary"]=="BOTH_FEASIBLE" else UNRESOLVED
  out.append(CapitalEvent(i["entry_utc"],"ENTRY","V2-C031",i["symbol"],iid,direction=i["direction"],direction_feasibility=feas,volume_cents=int(b["min_volume_cents"]),min_volume_cents=int(b["min_volume_cents"]),step_volume_cents=int(b["step_volume_cents"]),max_volume_cents=int(b["max_volume_cents"]),margin_eur=margin,price=ep,base_units=units,quote_to_eur_rate=rate,transaction_cost_eur=cost))
  for bar in bars[1:-1]:
   mark=_d(bar["low"] if stress and i["direction"]=="LONG" else bar["high"] if stress else bar["open"])
   out.append(CapitalEvent(bar["timestamp_utc"],"MARK","V2-C031",i["symbol"],iid,price=mark,quote_to_eur_rate=conv.rate(b["quote_asset"],bar["timestamp_utc"])))
  out.append(CapitalEvent(i["exit_utc"],"EXIT","V2-C031",i["symbol"],iid,price=xp,quote_to_eur_rate=conv.rate(b["quote_asset"],i["exit_utc"])))
 return out

def _safe_auth(a):
 if a.get("schema")!="mxm.greenfield.c031-stage-b-execution-authorization.v1" or a.get("status")!="AUTHORIZED_AFTER_EXACT_HEAD_GREEN": raise C031StageBError("Stage-B economics not authorized")
 if a.get("candidate_spec_hash")!=SPEC_HASH or not a.get("economic_execution_id"): raise C031StageBError("authorization identity drift")
 if a.get("protected_forward_opened") is not False or a.get("live_orders_authorized") is not False: raise C031StageBError("authorization safety drift")

def execute_after_authorization(input_dir,*,authorization:Mapping[str,Any]):
 _safe_auth(authorization); x=load_frozen_inputs(input_dir); acc=x["broker"]["account"]
 levels=[_d(v["marginLevelThreshold"]) for v in acc["margin_call_thresholds"]]
 if max(levels)!=GUARD or acc["stop_out_level_state"]!="UNKNOWN_NOT_IDENTIFIED_BY_PROTOOA_TRADER_OR_MARGIN_CALL_LIST": raise C031StageBError("stop-out authority requires re-freeze")
 kw=dict(starting_equity_eur=200,account_type=acc["account_type"],total_margin_calculation_type=acc["total_margin_calculation_type"],same_symbol_overlap_allowed=False,entry_margin_level_floor_ratio=GUARD,unresolved_stop_out_guard_ratio=GUARD)
 base=replay_continuous_account(_events(x,False),**kw); stress=replay_continuous_account(_events(x,True),**kw)
 dep=base.status=="HALT_UNRESOLVED_BROKER_STOP_OUT" or stress.status=="HALT_UNRESOLVED_BROKER_STOP_OUT" or base.accepted_entries!=stress.accepted_entries
 status="UNRESOLVED_BROKER_STOP_OUT_DEPENDENCY" if dep else "CAPITAL_PATH_FAILURE" if base.status!="COMPLETE" or stress.status!="COMPLETE" else "CURRENT_CONFIG_REALIZABLE_WITH_MARGIN_CONSTRAINTS" if base.rejected_entries else "CURRENT_CONFIG_REALIZABLE_ALL_FROZEN_SIGNALS"
 strip=lambda r:{k:v for k,v in asdict(r).items() if k!="decisions"}
 def ser(v):
  if isinstance(v,Decimal): return float(v)
  if isinstance(v,dict): return {k:ser(x) for k,x in v.items()}
  if isinstance(v,(list,tuple)): return [ser(x) for x in v]
  return v
 result={"schema":"mxm.greenfield.c031-stage-b-current-config-result.v1","version":VERSION,"candidate_id":"V2-C031","candidate_spec_hash":SPEC_HASH,"economic_execution_id":authorization["economic_execution_id"],"status":status,
 "scenario_boundary":{"current_configuration_applied_to_development":True,"historical_point_in_time_margin_certification":False,"exact_stop_out_known":False,"unknown_stop_out_handling":"FAIL_CLOSED_AT_CAPTURED_150_PERCENT_MARGIN_CALL_GUARD","protected_forward_opened":False},
 "capital_policy":{"starting_equity_eur":200,"continuous_account":True,"weekly_reset":False,"monthly_reset":False,"sizing":"BROKER_MINIMUM_EXECUTABLE_VOLUME_BASELINE","same_symbol_overlap":False,"cross_symbol_concurrency":True,"deterministic_same_timestamp_entry_tiebreak":"priority_then_symbol_then_position_id","deposits_withdrawals":"ENGINE_SUPPORTED_NONE_IN_FROZEN_SCENARIO"},
 "cost_policy":"FULL_FROZEN_CONSERVATIVE_ROUNDTRIP_CHARGED_AT_ENTRY","financing":{"state":"ZERO_BY_PRE_ECONOMIC_ROLLOVER_PROOF","rollover_crossings":0},"base_path":ser(strip(base)),"adverse_bar_stress_path":ser(strip(stress)),"accounting_effect":{"new_v2_identity":False}}
 raw=json.dumps(result,sort_keys=True,separators=(",",":"),allow_nan=False).encode(); result["result_sha256"]=hashlib.sha256(raw).hexdigest(); return result
