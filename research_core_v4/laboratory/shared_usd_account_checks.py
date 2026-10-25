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
def original(folder=None):
    import base64,hashlib,io,zipfile
    root=Path(__file__).resolve().parents[2]
    folder=Path(folder) if folder is not None else root/'docs/economic-development/20261025/shared-usd-account-40203167634'
    sha=lambda b:hashlib.sha256(b).hexdigest()
    manifest=(folder/'MANIFEST.json').read_bytes()
    need(sha(manifest)=='cb5f345343ac5cb0c6d1cb1a9d32eb3062949eb94ece0f924e2b431b1fe1ceaa','ORIGINAL_MANIFEST')
    m=json.loads(manifest);encoded=(folder/'artifact.zip.b64').read_bytes();need(len(encoded)<4096,'BOUNDED_ORIGINAL')
    archive=base64.b64decode(encoded.strip(),validate=True)
    need(len(archive)==584 and sha(archive)=='6da980c49e7ae6fdc67e64d5c80fa8f3b87ab0381da988116297442be646f5af','ORIGINAL_ARCHIVE')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        need(z.namelist()==['proof.json'] and z.infolist()[0].file_size==1839,'ORIGINAL_MEMBERS')
        raw=z.read('proof.json')
    need(sha(raw)==m['proof_sha256'] and (folder/'proof.json').read_bytes()==raw,'ORIGINAL_PROOF_COPY')
    need(m['run_id']==40203167634 and m['job_id']==121198452760 and m['artifact_id']==12602118833 and
         m['source_head']=='8dd9c71dcfecfcef5bc04c4b1a0e25919abed8dd' and
         m['test_merge']=='16c970f60770efc9a00935c0ce259715f1747a89','ORIGINAL_NATIVE_PROVENANCE')
    result=verify(json.loads(raw,parse_float=D))
    changed=[p for p,h in m['implementation_sha256'].items() if not (root/p).is_file() or sha((root/p).read_bytes())!=h]
    result.update(original_archive_verified=True,source_run=40203167634,current_csharp_matches_original=not changed,changed_implementation_paths=changed)
    return result
if __name__=='__main__':
    import sys
    if sys.argv[1:]==['--original']:print(json.dumps(original(),sort_keys=True))
    else:
        need(len(sys.argv)==2,'PROOF_ARGUMENT');value=json.loads(Path(sys.argv[1]).read_bytes(),parse_float=D)
        print(json.dumps(verify(value),sort_keys=True))
