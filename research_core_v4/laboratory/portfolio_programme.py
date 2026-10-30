"""Source-bound joint portfolio policy -> registered programme -> ONE C# EUR200.
All OHLC-derived execution prices/costs remain an explicit scenario, not ticks.
No closed model is called. No live connection, orders or protected data access.
"""
import base64
import datetime as dt
from decimal import Decimal as D
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from .common import need, digest, encoded
from .programs import Laboratory, AUTHORITY
from .budgets import TrialBook, historical_accounting

ROOT=Path(__file__).resolve().parents[2]
SPEC=ROOT/'research_core_v4/laboratory/PORTFOLIO_PROGRAMME_20261030.json'
POLICY_PROJECT=ROOT/'research_core_v4/laboratory/csharp/portfolio_policy/MxmPortfolioPolicy.csproj'
OUT=ROOT/'verification/portfolio-programme-20261030'
H=3600
START=1785715200 # 2026-08-03 UTC
END=1788134400 # 2026-08-31 UTC
ROSTER={5:'AUDUSD',111:'Copper',250:'SpotCrude'}

def iso(t):return dt.datetime.fromtimestamp(t,dt.timezone.utc).isoformat().replace('+00:00','Z')
def timestamp(s):return int(dt.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp())
def day_hours(hours):
    return [t for t in range(START,END,H) if dt.datetime.fromtimestamp(t,dt.timezone.utc).weekday()<5
            and dt.datetime.fromtimestamp(t,dt.timezone.utc).hour in hours]
def specification():
    p=json.loads(SPEC.read_bytes())
    need(p['id']=='V4-PORTFOLIO-RELATIVE-EFFICIENCY-20261030' and p['risk']['initial_eur']==200,
         'PORTFOLIO_SPEC')
    for name,sha in p['implementation_sha256'].items():
        need(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,'PORTFOLIO_IMPLEMENTATION_CHANGED')
    projection=json.loads((ROOT/'docs/economic-development/20261029/compression-decision/broker-minimum-volume-projection.json').read_bytes())
    for row in projection['existing_python_reference']:
        sid=row['symbol_id']
        if sid not in ROSTER:continue
        terms=p['cost_scenario']['instruments'][ROSTER[sid]]
        need(terms['units']==row['terms']['MinimumVolume']/100 and
             D(str(terms['margin_eur']))==max(D(row['margin']['BuyEur']),D(row['margin']['SellEur'])),
             'PORTFOLIO_CAPTURED_MINIMUM_TICKET')
    return p
def decode(value,sid):
    need(value['schema']=='mxm.wide.private.h1.v1' and value['same_native_account'] is True and
         value['identity']['sid']==sid,'PORTFOLIO_AUTHENTIC_SOURCE')
    bars={}
    for raw,row in value['bars'].items():
        t=int(raw)
        if START-13*H<=t<END:
            p=tuple(D(str(x)) for x in row[:4])
            need(t%H==0 and len(p)==4 and all(x.is_finite() and x>0 for x in p) and
                 p[2]<=min(p[0],p[3])<=max(p[0],p[3])<=p[1], 'PORTFOLIO_H1_QUALITY')
            bars[t]=p
    return bars
def support(corpus):
    # Price-blind full fixed exposure window, not future-filtered signal selection.
    scheduled=day_hours(range(7,18))
    missing=[(sid,t) for sid in (1,*ROSTER) for t in scheduled if t not in corpus[sid]]
    eligible=[]
    for t in day_hours(range(7,16)):
        if all(t-H in corpus[sid] and t-13*H in corpus[sid] and
               sum(t-j*H in corpus[sid] and t-(j+1)*H in corpus[sid] for j in range(1,13))>=9
               for sid in ROSTER):eligible.append(t)
    return {'classification':'SOURCE_ADMITTED' if not missing and len(eligible)>=40 else 'DATA_LIMITED_SOURCE_BEFORE_POLICY',
            'fixed_quote_hours':len(scheduled),'missing_quote_cells':len(missing),
            'joint_past_feature_times':len(eligible),'price_blind':True,'future_filtered_signals':False}
def policy_input(corpus):
    bars=[]
    for sid,name in ROSTER.items():
        bars.extend({'symbol':name,'end':iso(t+H),'available':iso(t+H),'close':str(p[3])}
                    for t,p in corpus[sid].items())
    # JSON decimal numbers, not strings, for the native decimal parser.
    for b in bars:b['close']=float(b['close'])
    return {'symbols':sorted(ROSTER.values()),'bars':sorted(bars,key=lambda b:(b['end'],b['symbol']))}
def reference(corpus):
    result={}
    times=sorted(set.intersection(*(set(corpus[sid]) for sid in ROSTER)))
    for bar_t in times:
        end=bar_t+H;date=dt.datetime.fromtimestamp(end,dt.timezone.utc)
        target=None;direction=0;scores={}
        if date.weekday()<5 and 7<=date.hour<=15:
            for sid,name in sorted(ROSTER.items(),key=lambda x:x[1]):
                bars=corpus[sid]
                if bar_t-12*H not in bars:break
                changes=[abs(bars[x][3]/bars[x-H][3]-1) for x in range(bar_t-11*H,bar_t+H,H)
                         if x in bars and x-H in bars]
                if len(changes)<9 or sum(changes)==0:break
                scores[name]=max(D(-1),min(D(1),(bars[bar_t][3]/bars[bar_t-12*H][3]-1)/sum(changes)))
            if len(scores)==3:
                values=sorted(scores.values());median=values[1]
                best=sorted(scores,key=lambda s:(-abs(scores[s]-median),s))[0]
                if values[-1]-values[0]>=D('.5') and abs(scores[best]-median)>=D('.25'):
                    target=best;direction=1 if scores[best]>median else -1
        result[end]=(target,direction)
    return result
def compile_targets(corpus,directory,observer=None):
    a=directory/'policy-input.json';b=directory/'policy-original.json'
    a.write_bytes(encoded(policy_input(corpus)))
    subprocess.run(['dotnet','run','--no-build','-c','Release','--project',str(POLICY_PROJECT),
                    '--',str(a),str(b)],check=True,capture_output=True,text=True,timeout=180)
    original=b.read_bytes()
    if observer is not None:observer({'phase':'POLICY_ORIGINAL_BEFORE_PARITY','original_base64':base64.b64encode(original).decode()})
    targets=json.loads(original);oracle=reference(corpus)
    need(len(targets)==len(oracle),'PORTFOLIO_ALL_JOINT_TIMES')
    need(all(oracle[timestamp(x['BoundaryUtc'])]==(x['Symbol'],x['Direction']) for x in targets),
         'PORTFOLIO_INDEPENDENT_CAUSAL_PARITY')
    return targets,original
def build_feed(corpus,targets,policy_hash,spec,synthetic=False):
    target_map={timestamp(x['BoundaryUtc']):x for x in targets}
    events=[];seq={s:0 for s in ROSTER.values()};previous=None
    for t in day_hours(range(7,18)):
        hour=dt.datetime.fromtimestamp(t,dt.timezone.utc).hour
        if hour==7:previous=None # prior day was explicitly flat at 17 UTC
        ordered=sorted(ROSTER.items(),key=lambda pair:(pair[1]==(previous or {}).get('Symbol'),pair[1]))
        fx=corpus[1][t][0];need(fx>D('.0003'),'PORTFOLIO_FX_POSITIVE')
        def quotes(offset,which):
            for sid,symbol in ordered:
                terms=spec['cost_scenario']['instruments'][symbol];bar=corpus[sid][t]
                side=(previous or {}).get('Direction',0) if (previous or {}).get('Symbol')==symbol else 0
                column=0 if which=='open' else 3 if which=='close' else (1 if side<0 else 2) if which=='adverse' else (2 if side<0 else 1)
                mark=bar[column];spread=D(str(terms['spread']));stamp=iso(t+offset)
                events.append({'$feed':'quote','Utc':stamp,'Symbol':symbol,'Bid':float(mark-spread/2),
                  'Ask':float(mark+spread/2),'QuoteToEur':float(1/(fx+D('.0003'))),
                  'QuoteLossToEur':float(1/(fx-D('.0003'))),'ExecutableUnits':terms['units'],
                  'InitialMarginEur':terms['margin_eur'],'CommissionPerSideEur':terms['fee_eur'],
                  'SlipPerSideQuote':terms['slippage'],'EstimatedStopRiskEur':float(D(str(terms['stop']))*terms['units']/(fx-D('.0003'))),
                  'StopDistanceQuote':terms['stop'],'BidSourceUtc':stamp,'AskSourceUtc':stamp,
                  'NativeSizingScenarioSha256':policy_hash,'BrokerVolumeMinUnits':terms['units'],
                  'BrokerVolumeMaxUnits':terms['units'],'BrokerVolumeStepUnits':terms['units']})
        # Exits/unchosen marks precede the selected target's quote, by the PRIOR
        # known target, never by the next hour's prices or eventual profitability.
        quotes(0,'open')
        current=None
        if hour<=16:
            current=target_map.get(t) if hour<=15 else None
            for name in sorted(ROSTER.values()):
                seq[name]+=1;side=current['Direction'] if current and current['Symbol']==name else 0
                events.append({'$feed':'explicit-decision','Utc':iso(t),'Symbol':name,'Sequence':seq[name],
                  'Desired':side,'ValidFromUtc':iso(t+H),'ExpiresUtc':iso(t+H+1),'PolicySha256':policy_hash})
        quotes(1,'adverse');quotes(1800,'other');quotes(3599,'close')
        previous=current
    return {'schema':'mxm.funded-programme-feed.v1','partition':'DEVELOPMENT','orders':0,'cloud':False,
      'synthetic':synthetic,'policy_sha256':policy_hash,'events':events,'events_sha256':digest(events),
      'source_sha256':digest(spec['source']),'symbols':sorted(ROSTER.values()),'execution_chunk_size':1000,
      'preserve_chunk_originals':True,
      'parameters':{'Strategy':0,'MaxMarginFraction':.4,'MaxPositions':1,'MinimumFreeMarginReserveEur':120,
       'MaxEstimatedStopRiskFraction':.01,'RoundTripRiskReserveEur':.4,'MaxQuoteAgeSeconds':3601,
       'ExplicitPolicySha256':policy_hash,'NativeSizingScenarioSha256':policy_hash},
      'price_basis':'OHLC_AND_FIXED_FRICTION_SCENARIO_NOT_OBSERVED_BID_ASK',
      'historical_total_costs_proven':False,'intrabar_order_observed':False,'historical_fills':False}
def programme(spec):
    def task(op,inp,deps):return {'operator':op,'input':inp,'dependencies':deps,'when':{},'priority':1,'trial_units':1 if op=='freeze_portfolio_policy' else 0}
    return {'schema':'mxm.laboratory-program.v1','id':spec['programme'],'version':1,'authority':AUTHORITY,
      'partition':'DEVELOPMENT','orders':0,'mode':'DEVELOPMENT_RESEARCH','provenance':'OWNER_B_E_REDESIGN',
      'prospective_at_ms':spec['prospective_at_ms'],'source_sha256':digest(spec['implementation_sha256']),
      'budget':{'steps':3,'broker_requests':0,'new_V2_identities':0,'new_v4_policies':1},
      'tasks':{'register':task('freeze_portfolio_policy',{'policy':spec},[]),
       'account':task('funded_csharp',{'candidate':{'result_of':'register'},'feed':{'bound_authenticated_csharp_feed':True}},['register']),
       'report':task('report',{'account':{'result_of':'account'}},['account'])}}
def account_checks(result):
    account=result['account'];cash=D(200);open_symbols=set();fees=D(0);gross=D(0)
    for row in account['Ledger']:
        s=row['Symbol'];need(s in ROSTER.values(),'PORTFOLIO_LEDGER_ROSTER')
        if row['Kind']=='ENTRY':
            need(not open_symbols,'PORTFOLIO_SHARED_POSITION_LIMIT');open_symbols.add(s)
        else:
            need(row['Kind']=='EXIT' and s in open_symbols,'PORTFOLIO_MATCHED_EXIT');open_symbols.remove(s)
        fees+=D(str(row['CommissionEur']));gross+=D(str(row['GrossEur']));cash+=D(str(row['GrossEur']))-D(str(row['CommissionEur']))
        need(abs(cash-D(str(row['CashEur'])))<D('.00000001'),'PORTFOLIO_INDEPENDENT_CASH')
    need(not open_symbols and account['OpenPositions']==0 and account['InitialCapitalEur']==200 and
         abs(cash-D(str(account['FinalCashEur'])))<D('.00000001'),'PORTFOLIO_FINAL_FLAT_200')
    return {'initial_eur':200,'final_equity_eur':account['MarkedEquityEur'],'net_eur':float(cash-200),
      'gross_price_pnl_eur':float(gross),'commissions_eur':float(fees),'entries':account['AcceptedEntries'],
      'max_drawdown_eur':account['MaxDrawdownEur'],'entries_by_week':account['EntriesByIsoWeek'],
      'classification':'NET_FAIL_FUNDED_PORTFOLIO_SCENARIO' if cash<=200 else 'POSITIVE_DEVELOPMENT_SCENARIO_UNCONFIRMED',
      'robust_edge_proven':False,'historical_fills':False,'hard21_certified':False}

def admit_once():
    repo='repos/mariancradulescu/mxm-quant-greenfield/'
    def get(path):return json.loads(subprocess.check_output(['gh','api',repo+path],text=True))
    need(os.environ['GITHUB_REPOSITORY']=='mariancradulescu/mxm-quant-greenfield' and
         os.environ['GITHUB_REF']=='refs/heads/mxm-remediation-p0-p4-20261015-v1' and
         os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_RUN_ATTEMPT']=='1','PORTFOLIO_FIRST_RUN_SCOPE')
    need(get('git/ref/heads/mxm-remediation-p0-p4-20261015-v1')['object']['sha']==os.environ['GITHUB_SHA'],
         'PORTFOLIO_OFFICIAL_HEAD')
    need(get('git/ref/heads/mxm-o04-accepted-owner-1807-v1')['object']['sha']=='a830c132521bd4348454653f713e04f6107484fe',
         'PORTFOLIO_OWNER_ANCHOR')
    history=get('actions/workflows/mxm-portfolio-programme-20261030.yml/runs?per_page=100')
    need(history['total_count']==len(history['workflow_runs']) and history['total_count']<=100,'PORTFOLIO_BOUNDED_HISTORY')
    pushes=[r for r in history['workflow_runs'] if r['event']=='push']
    need(len(pushes)==1 and pushes[0]['id']==int(os.environ['GITHUB_RUN_ID']) and
         pushes[0]['head_sha']==os.environ['GITHUB_SHA'] and pushes[0]['run_attempt']==1,'PORTFOLIO_NO_SECOND_OUTCOME')
    parents=get('commits/'+os.environ['GITHUB_SHA'])['parents'];need(len(parents)==2,'PORTFOLIO_REVIEWED_MERGE')
    runs=get('actions/runs?event=pull_request&per_page=100')['workflow_runs']
    passed={r['name'] for r in runs if r['head_sha']==parents[1]['sha'] and r['conclusion']=='success'}
    need({'MXM R3 protected technical installation CI','MXM CSharp Pepperstone protected gateway CI'}<=passed,
         'PORTFOLIO_REQUIRED_CI')
    specification();print('PORTFOLIO_SINGLE_FIRST_OUTCOME_ADMITTED')

def run():
    need(os.environ.get('GITHUB_REPOSITORY')=='mariancradulescu/mxm-quant-greenfield' and
         os.environ.get('GITHUB_REF')=='refs/heads/mxm-remediation-p0-p4-20261015-v1' and
         os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1',
         'PORTFOLIO_EXECUTION_SCOPE')
    spec=specification();history=historical_accounting(ROOT)
    need(history['reconciled'] and history['V2']['used']==21,'PORTFOLIO_PRESERVE_LEGACY_BUDGET')
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.successor_c_20261018.readback import FP
    from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
    public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
    need(public_spki_sha256(public)==FP,'PORTFOLIO_CUSTODY_RECIPIENT')
    OUT.mkdir(parents=True,exist_ok=True)
    need(not (OUT/'receipt.json').exists() and not (OUT/'private.mxmenc').exists(),'PORTFOLIO_EXISTING_OUTCOME')
    with tempfile.TemporaryDirectory() as directory:
        tmp=Path(directory);key,fp=_private_key_from_secret(tmp);need(fp==FP,'PORTFOLIO_CUSTODY_KEY')
        journals=[]
        def preserve(value):
            payload=encoded(value);path=OUT/f'journal-{len(journals):03d}.mxmenc'
            need(not path.exists(),'PORTFOLIO_JOURNAL_OVERWRITE')
            encrypt_shard(gzip.compress(payload,mtime=0),public_key=public,output=path)
            journals.append({'path':path.name,'plain_sha256':hashlib.sha256(payload).hexdigest(),
                             'cipher_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            (OUT/'journal-manifest.json').write_bytes(encoded(journals))
        corpus={};proofs={}
        for raw,item in spec['source']['assets'].items():
            sid=int(raw);value,proof=load_asset(key,fp,tmp,{'release_id':409747426,
              'asset_id':item['asset_id'],'ciphertext_sha256':item['sha256']})
            corpus[sid]=decode(value,sid);proofs[raw]=proof
        admission=support(corpus)
        original={'spec':spec,'source_proofs':proofs,'source_admission':admission,
          'run_id':int(os.environ['GITHUB_RUN_ID']),'head':os.environ['GITHUB_SHA'],'economic_outcomes':0}
        outcome=admission['classification'];processes=0
        preserve({'phase':'SOURCE_ADMISSION_BEFORE_POLICY','spec':spec,'proofs':proofs,'admission':admission})
        if outcome=='SOURCE_ADMITTED':
            lab=Laboratory(programme(spec),history,TrialBook({'V4':1,'V2':history['V2']['limit']},
              {'V4':0,'V2':history['V2']['used']}))
            lab.execute('register') # Reserve before observing a policy outcome.
            checkpoint=lab.checkpoint();lab=Laboratory.restore(json.loads(encoded(checkpoint)),history)
            targets,policy_bytes=compile_targets(corpus,tmp,preserve)
            candidate=lab.state['results']['register']['value']
            feed=build_feed(corpus,targets,candidate['spec_hash'],spec)
            lab.authenticated_csharp_feed=feed
            lab.funded_observer=preserve
            lab.execute('account');lab.execute('report');need(lab.next() is None,'PORTFOLIO_FINITE_STOP')
            result=lab.state['results']['account']['value'];metrics=account_checks(result)
            outcome=metrics['classification'];processes=result['process_count']
            original.update({'economic_outcomes':1,'policy_original_base64':base64.b64encode(policy_bytes).decode(),
              'policy_original_sha256':hashlib.sha256(policy_bytes).hexdigest(),'feed':feed,
              'programme_checkpoint':lab.checkpoint(),'metrics':metrics})
        raw=encoded(original);encrypt_shard(gzip.compress(raw,mtime=0),public_key=public,output=OUT/'private.mxmenc')
        receipt={'schema':'mxm.integrated-portfolio-first-result.v1','run_id':int(os.environ['GITHUB_RUN_ID']),
          'head':os.environ['GITHUB_SHA'],'spec_sha256':hashlib.sha256(SPEC.read_bytes()).hexdigest(),
          'source_admission':admission,'outcome':outcome,'economic_outcomes':original['economic_outcomes'],
          'account_processes':processes,'initial_eur':200,'reset_count':0,'orders':0,'cloud':False,
          'broker_requests':0,'protected_opened':False,'closed_models_rerun':0,'historical_costs_proven':False,
          'hard21_certified':False,'robust_edge_proven':False,'private_plain_sha256':hashlib.sha256(raw).hexdigest(),
          'private_cipher_sha256':hashlib.sha256((OUT/'private.mxmenc').read_bytes()).hexdigest(),'journals':journals}
        (OUT/'receipt.json').write_bytes(encoded(receipt));print(json.dumps(receipt,sort_keys=True))

def cold():
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.remediation_p0_p4_20261015 import owner
    from research_core_v4.remediation_p0_p4_20261015.safety import unpack
    receipt=json.loads((OUT/'receipt.json').read_bytes());cipher=(OUT/'private.mxmenc').read_bytes()
    need(hashlib.sha256(cipher).hexdigest()==receipt['private_cipher_sha256'],'PORTFOLIO_COLD_CIPHER')
    with tempfile.TemporaryDirectory() as directory:
        from research_core_v4.successor_c_20261018.readback import FP
        tmp=Path(directory);key,fp=_private_key_from_secret(tmp);need(fp==FP,'PORTFOLIO_COLD_RECIPIENT')
        raw=unpack(owner.bounded_decrypt(cipher,key,tmp))
        for row in receipt['journals']:
            blob=(OUT/row['path']).read_bytes()
            need(hashlib.sha256(blob).hexdigest()==row['cipher_sha256'] and
                 hashlib.sha256(unpack(owner.bounded_decrypt(blob,key,tmp))).hexdigest()==row['plain_sha256'],
                 'PORTFOLIO_COLD_JOURNAL')
    need(hashlib.sha256(raw).hexdigest()==receipt['private_plain_sha256'],'PORTFOLIO_COLD_PLAIN')
    original=json.loads(raw)
    if original['economic_outcomes']:
        p=base64.b64decode(original['policy_original_base64']);need(hashlib.sha256(p).hexdigest()==original['policy_original_sha256'],'PORTFOLIO_COLD_POLICY')
        result=original['programme_checkpoint']['progress']['results']['account']['value']
        for chunk in result['chunks']:
            need(hashlib.sha256(base64.b64decode(chunk['original_result_base64'])).hexdigest()==chunk['result_sha256'] and
                 hashlib.sha256(base64.b64decode(chunk['original_capsule_base64'])).hexdigest()==chunk['capsule_sha256'],
                 'PORTFOLIO_COLD_ORIGINAL_CHUNKS')
        need(account_checks(result)==original['metrics'],'PORTFOLIO_COLD_LEDGER_RECONCILIATION')
    proof={'schema':'mxm.integrated-portfolio-cold-readback.v1','run_id':receipt['run_id'],
      'private_cipher_sha256':receipt['private_cipher_sha256'],'originals_verified':True,
      'models_rerun':0,'source_reopened':False,'orders':0}
    (OUT/'cold.json').write_bytes(encoded(proof));print(json.dumps(proof,sort_keys=True))

if __name__=='__main__':
    import sys
    need(len(sys.argv)==2 and sys.argv[1] in ('admit','run','cold'),'PORTFOLIO_COMMAND')
    {'admit':admit_once,'run':run,'cold':cold}[sys.argv[1]]()
