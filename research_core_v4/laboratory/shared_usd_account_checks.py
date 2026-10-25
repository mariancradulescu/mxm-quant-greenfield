"""Independent Decimal verification of the artificial funded C# account fixture, not market performance."""
from decimal import Decimal as D,localcontext
import json
from pathlib import Path

def need(ok,why):
    if not ok:raise ValueError('SHARED_USD_ACCOUNT_'+why)
def verify(value):
    need(value['schema']=='mxm.shared-usd-account.artificial.v1' and value['checks']>=40,'ACTUAL_COMPILED_FIXTURE')
    need(len(value['proofs'])==4,'LONG_SHORT_GAIN_LOSS')
    need({(x['direction'],x['pnl_sign']) for x in value['proofs']}=={(a,b) for a in (1,-1) for b in (1,-1)},'ALL_FOUR_CASES')
    with localcontext() as ctx:
        ctx.prec=65
        for x in value['proofs']:
            direction=x['direction'];entry=D(str(x['entry_price']));units=D(str(x['units']));cash=D(str(x['cash_eur']))
            usd=((D(str(x['mark_bid']))-entry) if direction>0 else (entry-D(str(x['mark_ask']))))*units
            need(usd*x['pnl_sign']>0 and cash==D('199.9') and x['entries']==1 and x['exits']==0 and D(str(x['margin_eur']))==50,'ONE_ACCOUNT_ONE_FEE_NO_FX_ORDER')
            equity=cash+usd/D(str(x['fx_ask'] if usd>=0 else x['fx_bid']))
            final=cash+usd/D(str(x['final_fx_ask'] if usd>=0 else x['final_fx_bid']))
            need(abs(equity-D(str(x['equity_eur'])))<D('1e-24') and
                 D(str(x['restored_equity_eur']))==D(str(x['equity_eur'])) and
                 abs(final-D(str(x['final_equity_eur'])))<D('1e-24'),'SIGNED_CONVERSION_AND_RECOVERY_ARITHMETIC')
    f=value['fee_case']
    with localcontext() as ctx:
        ctx.prec=65
        expected=D(str(f['units']))*D(str(f['execution_price']))*D(str(f['usd_per_million']))/D(1000000)/D(str(f['fx_bid']))
        need(abs(expected-D(str(f['commission_eur'])))<D('1e-24') and abs(D(str(f['cash_eur']))-(D(200)-expected))<D('1e-24'),'ADMITTED_FX_BID_FOR_CAPTURED_USD_FEE')
    need(value['broker_orders']==0 and all(value[k] is False for k in ('native_ctrader_runtime_reception','economic_edge_proven','hard21_proven')),'NO_NATIVE_OR_ECONOMIC_PROMOTION')
    return {'artificial_funded_cases':4,'compiled_checks':value['checks'],'signed_fx_and_cold_recovery_independently_checked':True,
            'broker_orders':0,'economic_edge_proven':False,'hard21_proven':False,'native_ctrader_runtime_reception':False}
if __name__=='__main__':
    import sys
    need(len(sys.argv)==2,'PROOF_ARGUMENT');value=json.loads(Path(sys.argv[1]).read_bytes(),parse_float=D)
    print(json.dumps(verify(value),sort_keys=True))
