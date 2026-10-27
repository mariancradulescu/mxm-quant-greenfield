"""Exact public receipt terms -> reused CSharp price-free commission floor. No FX guess."""
import json,subprocess,tempfile
from decimal import Decimal as D
from pathlib import Path
from .common import need
from .current_margin_evidence import ROOT,PROJECT
from .verify_current_margin_result import verify,FOLDER

def reference(panel):
    out=[]
    for p in panel:
        t=p['terms'];sid=p['symbol_id']
        if t is None:out.append(dict(symbol_id=sid,status='COST_UNRESOLVED'));continue
        kind=t['Kind'];minimum=D(t['Minimum']);rate=D(t['Rate'])
        base=D(t['MinimumVolume'])/D(t['LotSize'])*rate if kind in (2,4) else None
        asset='USD' if kind==2 else t['QuoteAsset'] if kind==4 else None
        unresolved=set()
        if minimum:unresolved.add('MISSING_COST_FX_'+t['MinimumAsset'])
        if base:unresolved.add('MISSING_COST_FX_'+asset)
        if kind not in (2,4) and rate:unresolved.add('PRICE_DEPENDENT_BASE_FEE')
        out.append(dict(symbol_id=sid,status='DECLARED_COMPONENTS_NOT_ACTUAL_CHARGES',declared_base_per_fill=base,
          declared_base_asset=asset,declared_minimum_per_fill=minimum,declared_minimum_asset=t['MinimumAsset'],
          no_fx_no_price_floor=dict(KnownPerFillFloorEur=D(0),CompleteFeeKnownWithoutPrice=not unresolved,Unresolved=sorted(unresolved)),
          source_authenticated_in_program=False,full_entry_admission=False,total_trading_cost_proven=False))
    return out

def main():
    verify();panel=json.loads((FOLDER/'receipt.json').read_bytes())['panel']
    with tempfile.TemporaryDirectory() as d:
        out=Path(d)/'components.json'
        subprocess.run(['dotnet','run','--project',str(ROOT/PROJECT),'-c','Release','--framework','net8.0','--no-build','--','--commission-components',str(FOLDER/'receipt.json'),str(out)],capture_output=True,check=True)
        actual=json.loads(out.read_bytes(),parse_float=D)
    need(actual==reference(panel),'CURRENT_MARGIN_PUBLIC_ALL_COMPONENTS_RECONCILED')
    return dict(schema='mxm.public-current-margin-components.v1',original_run=40483982559,components=actual,
      original_receipt_verified=True,new_broker_requests=0,orders=0,economic_edge_proven=False)
if __name__=='__main__':print('MXM_CURRENT_MARGIN_PUBLIC_COMPONENTS '+json.dumps(main(),default=str,sort_keys=True))
