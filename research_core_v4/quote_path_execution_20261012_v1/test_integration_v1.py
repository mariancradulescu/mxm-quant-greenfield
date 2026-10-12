"""Synthetic integration checks using byte-pinned native pure functions."""
import ast,math,pathlib,types,unittest,typing
from collections import Counter,defaultdict,deque,namedtuple
from datetime import datetime,timezone
try:
    from research_core_v4.quote_path_order_20261012_v1 import kernel_v1 as kernel
except ModuleNotFoundError:
    from quote_path_order import kernel_v1 as kernel
HERE=pathlib.Path(__file__).resolve()
ROOT=HERE.parents[1] if (HERE.parents[1]/'quote_path_order').is_dir() else HERE.parents[2]

def functions(path,names,scope):
    tree=ast.parse(path.read_text())
    selected=[node for node in tree.body if isinstance(node,ast.FunctionDef) and (names is None or node.name in names)]
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(path),'exec'),scope)

def fixture():
    native={'math':math,'Counter':Counter,'defaultdict':defaultdict,'deque':deque}
    account_path=ROOT/'research_core_v4/cost_frequency_discovery_v1/accounts_v1.py'
    if not account_path.is_file():account_path=ROOT/'quote_path_execution/native_accounts_source.py'
    functions(account_path,None,native)
    account=types.SimpleNamespace(**{k:v for k,v in native.items() if callable(v)})
    decode={'Sequence':typing.Sequence,'Mapping':typing.Mapping,'Any':typing.Any,
            'DecodedTick':namedtuple('DecodedTick','timestamp_ms raw_tick'),'CaptureContractError':ValueError}
    decoder_path=ROOT/'m6/cost_evidence.py'
    if not decoder_path.is_file():decoder_path=ROOT/'current_inputs/m6/cost_evidence.py'
    functions(decoder_path,{'decode_ctrader_tick_page'},decode)
    def need(check,code):
        if not check:raise ValueError(code)
    scope={'a':account,'k':kernel,'decode_ctrader_tick_page':decode['decode_ctrader_tick_page'],
           'need':need,'Counter':Counter,'datetime':datetime,'timezone':timezone,'math':math}
    runner_path=ROOT/'research_core_v4/quote_path_execution_20261012_v1/runner_v1.py'
    if not runner_path.is_file():runner_path=ROOT/'quote_path_execution/runner_v1.py'
    functions(runner_path,{'schema_and_accounting','pilot','aggregate'},scope)
    t=1736164800
    row={'sid':1,'class':'Forex','base':'USD','quote':'EUR','min_units':.01,'reasons':[]}
    contract={'commissionType':3,'preciseTradingCommissionRate':100,'lotSize':100000,
              'preciseMinCommission':0,'minCommissionType':2,'pnlConversionFeeRate':0}
    def quote(boundary,extra=0):
        sides={};pages=[]
        for side in ('bid','ask'):
            decoded=[]
            for sec in range(-60,1):
                x,y=(0.,0.) if sec<-35 else (2.,0.) if sec<-25 else (2.,2.) if sec<-15 else (2.2,2.2)
                mid=100*math.exp((x+extra)/10000);ratio=math.exp((2+y)/10000)
                b=2*mid/(1+ratio);a=ratio*b
                decoded.append(((boundary+sec)*1000,round((b if side=='bid' else a)*100000)))
            backwards=list(reversed(decoded));encoded=[{'timestamp':backwards[0][0],'tick':backwards[0][1]}]
            encoded.extend({'timestamp':backwards[i][0]-backwards[i-1][0],'tick':backwards[i][1]-backwards[i-1][1]} for i in range(1,len(backwards)))
            sides[side]={'state':'AUTHENTIC_CAUSAL_QUOTE','timestamp_ms':backwards[0][0],'price':backwards[0][1]/100000,'age_ms':0,'source_has_more':False}
            pages.append({'side':side,'encoded':encoded,'hasMore':False})
        return {'symbol_id':1,'boundary_ms':boundary*1000,'sides':sides,'pages':pages}
    raw=[quote(t),quote(t+900,1.)];quotes={(1,t):raw[0],(1,t+900):raw[1]};graph=account.graph([row])
    event={'sid':1,'t':t,'h':15,'entry':{'state':'ELIGIBLE_CURRENT_PROXY','eligible':True,'margin_eur':20.,'risk_eur':.5,'cost_eur':.01},
           'prediction':'DO_NOT_CALL_OLD_PREDICTOR','accounts':{'S2_F010_DAY':[account.account(d,row,contract,t,t+900,.25,quotes,graph,2,.10,False) for d in (1,-1)]}}
    full={'summary':{'source_head':'fixedsource','orders':0,'fills':0,'protected_forward':False,'weeks':['2025-W02']},
          'catalog':{'full':{'1':contract}},'all_identity_status':[row],'raw_quote_receipts':raw,'events':[event,event.copy()]}
    return scope,full

class Integration(unittest.TestCase):
    def test_effective_schema_and_native_accounting_parity(self):
        scope,full=fixture();unique,rows,quotes,graph,checks=scope['schema_and_accounting'](full,'fixedsource')
        self.assertEqual(len(unique),1);self.assertEqual(checks['side_account_checks'],2)
        _,summary=scope['pilot'](full,unique,rows,quotes,graph)
        self.assertEqual(summary['unique_candidate_boundaries'],1)
        self.assertEqual(summary['calculable_features'],1)
        self.assertEqual(summary['portfolio']['halt'],'END')
        self.assertEqual(summary['accounting']['model']['evaluable'],1)
        self.assertEqual(summary['broker_requests'],0)
    def test_saved_accounting_mismatch_stops_before_pilot(self):
        scope,full=fixture();full['events'][0]['accounts']['S2_F010_DAY'][0]['net_eur']+=1
        with self.assertRaisesRegex(ValueError,'ACCOUNT_VALUE_PARITY'):
            scope['schema_and_accounting'](full,'fixedsource')
    def test_decode_reference_conflict_stops_before_pilot(self):
        scope,full=fixture();full['raw_quote_receipts'][0]['sides']['bid']['price']+=1
        with self.assertRaisesRegex(ValueError,'DECODER_LAST_SIDE_PARITY'):
            scope['schema_and_accounting'](full,'fixedsource')

if __name__=='__main__':unittest.main()
