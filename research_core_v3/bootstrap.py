from __future__ import annotations
import argparse,json
from pathlib import Path
from .engine import discover_series,execute_spec
from .inventory import build_inventory
from .migration import salvage_legacy_v2

DEFAULT_SPEC={
 "schema":"mxm.research-core-v3.frozen-experiment-spec.v1","role":"DEVELOPMENT_ONLY",
 "response_horizons_bars":[1,3,6,12],"primary_horizon_bars":6,
 "mechanisms":[
  {"name":"MEAN_REVERSION","parameter_grid":{"lookback":[12,24,48],"z":[1.0,1.5,2.0]},"rearm_bars":3},
  {"name":"TREND_MOMENTUM","parameter_grid":{"lookback":[12,24,48],"threshold":[0.0,0.002,0.005]},"rearm_bars":3},
  {"name":"BREAKOUT_VOLATILITY_EXPANSION","parameter_grid":{"lookback":[12,24,48],"range_ratio":[1.25,1.5,2.0]},"rearm_bars":3},
  {"name":"VOLATILITY_STATE","parameter_grid":{"lookback":[12,24],"reference":[120,240],"quantile":[0.7,0.85],"state":["HIGH","LOW"]},"rearm_bars":3},
  {"name":"SESSION_TIME_SEASONALITY","parameter_grid":{"hours":[[0,1,2,3],[7,8,9,10],[13,14,15,16],[19,20,21,22]],"direction":[1,-1]},"rearm_bars":1},
  {"name":"REGIME_CONTEXT_CONDITIONED","contexts":[{"kind":"VOLATILITY_QUANTILE","lookback":24,"reference_bars":500,"q_low":0.0,"q_high":0.3},{"kind":"VOLATILITY_QUANTILE","lookback":24,"reference_bars":500,"q_low":0.7,"q_high":1.0}],"parameter_grid":{"variant":[{"base":"TREND_MOMENTUM","base_params":{"lookback":24,"threshold":0.0}},{"base":"MEAN_REVERSION","base_params":{"lookback":24,"z":1.5}}]},"rearm_bars":3}
 ]}

def main(argv=None):
 ap=argparse.ArgumentParser(); ap.add_argument('--root',default='.'); ap.add_argument('--input',action='append',default=[]); ap.add_argument('--out',default='research_core_v3/state'); args=ap.parse_args(argv)
 root=Path(args.root).resolve(); out=root/args.out; out.mkdir(parents=True,exist_ok=True)
 inv=build_inventory(root); (out/'ACCEPTED_DATA_INVENTORY_V1.json').write_text(json.dumps(inv,indent=2,sort_keys=True,default=str)+"
")
 salv=salvage_legacy_v2(root); (out/'LEGACY_V2_SALVAGE_V1.json').write_text(json.dumps(salv,indent=2,sort_keys=True,default=str)+"
")
 (out/'FROZEN_EXPERIMENT_SPEC_V1.json').write_text(json.dumps(DEFAULT_SPEC,indent=2,sort_keys=True)+"
")
 roots=[Path(x).resolve() for x in args.input]+[root/'raw',root/'captures',root/'data/raw',root/'evidence/raw']
 series=discover_series(roots)
 surface=execute_spec(series,DEFAULT_SPEC); (out/'BROAD_MULTI_SYMBOL_MULTI_MECHANISM_DEVELOPMENT_RESPONSE_SURFACE_V1.json').write_text(json.dumps(surface,indent=2,sort_keys=True,default=str)+"
")
 status={"schema":"mxm.research-core-v3.state.v1","legacy_v2_read_only":True,"one_writer":True,"one_canonical_v3_state":True,"authoritative_frontier":1576,"repo_resident_raw_series":len(series),"development_surface_status":surface['status'],"v3_status":"DEVELOPMENT_RESPONSE_SURFACE_READY_FOR_INTERPRETATION" if series and len({c['mechanism'] for c in surface['cells']})>=2 else "AUTHENTIC_BROKER_DATA_MATERIALIZATION_REQUIRED_FOR_MULTI_MECHANISM_RESPONSE_SURFACE","next_action":"BATCH_AI_INTERPRETATION" if series else "ACQUIRE_OR_MATERIALIZE_OUTCOME_BLIND_PEPPERSTONE_M5_BYTES","epoch49_v2_ignored":True,"protected_forward_opened":False,"final_pnl_certification":False}
 (out/'V3_STATE.json').write_text(json.dumps(status,indent=2,sort_keys=True)+"
"); print(json.dumps(status,sort_keys=True))
if __name__=='__main__': main()
