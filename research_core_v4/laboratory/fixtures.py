"""Deterministic reception only. These values are NEVER market evidence."""
from copy import deepcopy
from .common import digest
from .programs import AUTHORITY
T=1736164800000 # Monday January 6 2025, exact completed-bar grid

def candidate(ident,programme):
    return {'id':ident,'mechanism':{'family':'SYNTHETIC_RECEPTION'},'rationale':'Exercise integration; no economic hypothesis or alpha claim',
      'universe':['SYNTHETIC'],'features':[],'lookbacks':[],'filters':[],'parameters':{},
      **{k:{'rule':'SYNTHETIC_DETERMINISTIC_RECEPTION_ONLY'} for k in ('data','causal_availability','normalization_training','timing','entry','exit','maximum_hold','execution_assumptions','capital_semantics','cloud_portability','position_admission_policy','stage_a_economic_unit')},
      'direction':{'rule':'FIXTURE_LONG'},'cost_state':{'state':'CONSERVATIVE_BOUND'},
      'no_rescue_rule':{'material_change_requires_new_identity':True},
      'provenance':{'programme':programme,'prospective_at_ms':T,'synthetic_reception':True}}

def trades(gain=2,cost=.1):
    return [{'decision_ms':T,'entry_ms':T+1000,'exit_ms':T+61000,'feature_available_ms':T,'partition':'DEVELOPMENT','source_sha256':digest('SYNTHETIC_SOURCE'),
      'execution_evidence_sha256':digest('SYNTHETIC_EXECUTION'),'execution_basis':'SYNTHETIC_RECEPTION','gross_eur':gain,
      'costs':dict.fromkeys(('spread','commission','slippage','funding','fx_conversion'),cost)}]

def economic_fixture():
    events=[]
    for kind,ts,price in [('ENTRY','2025-01-06T12:00:01Z',100),('MARK','2025-01-06T12:00:30Z',99.9),('EXIT','2025-01-06T12:01:01Z',102)]:
        r={'timestamp_utc':ts,'kind':kind,'candidate_id':'V2-C990001','symbol':'SYNTHETIC','position_id':'p1','causal_state':True,
           'price':price,'quote_to_eur_rate':1,'metadata':{'source_sha256':digest('SYNTHETIC_PRICE_PATH'),'available_at_ms':T,'cost_components_eur':dict.fromkeys(('spread','commission','slippage','funding','fx_conversion'),0.)},'transaction_cost_eur':0.}
        if kind=='ENTRY':r.update(direction='LONG',direction_feasibility='EUR200_MIN_VOLUME_FEASIBLE',volume_cents=100,min_volume_cents=100,step_volume_cents=100,max_volume_cents=10000,base_units=1,margin_eur=20)
        events.append(r)
    for r in events:
        r['metadata'].update(quote_available_at_ms=T,fx_available_at_ms=T,
            signal_provenance={'feature_available_ms':T,'decision_ms':T,
                'entry_ms':T+1000,'exit_ms':T+61000,'feature_set_sha256':digest('SYNTHETIC_PRICE_PATH')})
    spec={'starting_equity_eur':200,'deposit_count':1,'sizing_rule_frozen':True,'allocator_frozen':True,'price_cost_convention':'MID_PLUS_ALL_FRICTIONS',
      'account_type':'HEDGED','margin_type':'SUM','same_symbol_overlap_allowed':True,'evaluation_start':'2025-01-06T00:00:00Z','evaluation_end':'2025-01-20T00:00:00Z'}
    evidence={'screen_status':'DISCOVERY_SURVIVOR','cost_state':'CONSERVATIVE_BOUND','full_mark_path':True,'dated_broker_terms':True,'events':events}
    return spec,evidence

def programme(ident='RECEPTION_BRANCHING',suffix=1):
    cid=f'V2-C{990000+suffix}';c=candidate(cid,ident)
    manifest={'instrument':'SYNTHETIC','resolution':'M5','partition':'DEVELOPMENT','start_ms':T-300000,'end_ms':T,
      'source':'SYNTHETIC_RECEPTION','source_sha256':digest('fixture'),'available_at_ms':T,'session_semantics':'FIXTURE_ONLY','completeness':'CONFIRMED_COMPLETE','account_scope':'SYNTHETIC'}
    row={'t':T-300000,'available_at':T,'open':100.,'high':101.,'low':99.,'close':100.,'volume':10.}
    def node(op,x,deps=(),when=None,priority=100,units=0):return {'operator':op,'input':x,'dependencies':list(deps),'when':when or {},'priority':priority,'trial_units':units}
    ref=lambda k:{'result_of':k}
    spec,evidence=economic_fixture()
    comparisons={k:{'population_sha256':digest('same_fixture_population'),'policy_sha256':digest(k)} for k in ('baseline','cost_stress','earlier_fold','later_fold')}
    observed={k:{**d,'source_sha256':digest(k),'status':'COMPLETE','net_eur':1.} for k,d in comparisons.items()}
    tasks={
      'validate_data':node('catalogue',{'manifest':manifest,'rows':[row]},priority=1),
      'admit_candidate':node('freeze',{'candidate':c},['validate_data'],{'validate_data':['DATA_VALID']},units=0),
      'cheap_screen':node('screen',{'candidate':ref('admit_candidate'),'evidence':{'identity':'SYNTHETIC_RECEPTION','implementation_valid':True,'complete':True,'cost_state':'CONSERVATIVE_BOUND','trades':trades()}},['admit_candidate']),
      'deep_account':node('replay',{'spec':spec,'evidence':evidence},['cheap_screen'],{'cheap_screen':['DISCOVERY_SURVIVOR']}),
      'robustness':node('robustness',{'cashflows':trades(),'cost_multipliers':{'original':1.,'stress':2.},'chronological_folds':[{'id':'frozen_fold','start_ms':T,'end_ms':T+100000}]},['deep_account'],{'deep_account':['SUPPORTED_FOR_ROBUSTNESS']}),
      'classify':node('classify',{'result':ref('cheap_screen')},['cheap_screen']),
      'rejected_followup':node('report',{'purpose':'Investigate rejected case only'},['cheap_screen'],{'cheap_screen':['COARSE_NET_FAIL','GROSS_EDGE_FAIL']}),
      'programme_report':node('report',{'screen':ref('cheap_screen'),'replay':ref('deep_account'),'robustness':ref('robustness')},['classify','deep_account','robustness'])}
    return {'schema':'mxm.laboratory-program.v1','id':ident,'version':1,'authority':AUTHORITY,'partition':'DEVELOPMENT','orders':0,'mode':'SYNTHETIC_RECEPTION',
      'budget':{'steps':len(tasks),'broker_requests':0,'new_V2_identities':0},'prospective_at_ms':T,'provenance':'OWNER_FUNCTIONAL_RECEPTION_SYNTHETIC_ONLY',
      'source_sha256':digest('integration-reception-fixture-v1'),'tasks':tasks}

def native_path_fixture():
    """Manually known: long101 -> bid102, EUR1 gross, .20fees, .05funding."""
    intent={'decision_ms':T,'feature_available_ms':T,'entry_ms':T+1000,'exit_ms':T+61000,'direction':1,'symbol_id':9999}
    def quote(t,bid,ask):return {'symbol_id':9999,'boundary_ms':t,'sides':{side:{'state':'AUTHENTIC_CAUSAL_QUOTE','timestamp_ms':t,'price':price,'age_ms':0,'source_has_more':False} for side,price in [('bid',bid),('ask',ask)]},'fixture':'SYNTHETIC_RECEPTION_NOT_MARKET_EVIDENCE'}
    corpus={'all_identity_status':[{'sid':9999,'symbol':'SYNTHETIC','class':'SYNTHETIC_FOREX','base':'EUR','quote':'EUR','min_units':1,'reasons':[]}],
      'catalog':{'full':{'9999':{'commissionType':4,'preciseTradingCommissionRate':0,'lotSize':100,'preciseMinCommission':0,'minCommissionType':2,'pnlConversionFeeRate':0}}},
      'raw_quote_receipts':[quote(T+1000,100,101),quote(T+31000,100.5,101.5),quote(T+61000,102,103)]}
    costs={'spread':0.,'commission':.1,'slippage':0.,'funding':0.,'fx_conversion':0.}
    terms={'volume_cents':100,'min_volume_cents':100,'step_volume_cents':100,'max_volume_cents':10000,'margin_eur':20.,
      'entry_cost_components_eur':costs,'exit_cost_components_eur':costs,'financing_cashflows':[{'timestamp_ms':T+31000,'amount_eur':-.05,'source_sha256':'a'*64}],
      'source_sha256':'a'*64,'effective_start_ms':T,'effective_end_ms':T+100000}
    authority={'screen_status':'DISCOVERY_SURVIVOR','cost_state':'CONSERVATIVE_BOUND','prospectively_frozen':True,'source_sha256':'b'*64,
      'current_snapshot_is_historical':False,'by_intent':{digest(intent):terms},'mark_interval_ms':30000}
    coarse={'state':'CONSERVATIVE_BOUND','prospectively_frozen':True,'source_sha256':'b'*64,'current_snapshot_is_historical':False,
      'per_intent_costs_eur':{digest(intent):{'spread':0.,'commission':.2,'slippage':0.,'funding':.05,'fx_conversion':0.}}}
    spec,_=economic_fixture();spec['price_cost_convention']='BID_ASK_PLUS_NONSPREAD_COSTS'
    generated={'intents':[intent],'missing':[],'feature_asset_sha256':digest('synthetic-fixed-source')}
    return generated,corpus,authority,coarse,spec
