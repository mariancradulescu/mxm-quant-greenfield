"""Saved-result support reduction only. No model, signal, label or PnL replay."""
import os,json,pathlib,tempfile,hashlib,gzip,base64,bisect,math
from collections import Counter,defaultdict
from datetime import datetime,timezone
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.activity_clock_cost_v1.runner_v1 import point
e=rt.e;P='research_core_v4/executable_coverage_diagnostic_v1/';PHASE='GATE'
BASE='828d2c130a4ce632815be31e94067e0e7f4384bc'
START=1787184000;END=START+28*86400
FULL_WEEKS=('2026-W35','2026-W36','2026-W37')
def need(x,c):e.w.old.need(bool(x),c)
def sha(x):return hashlib.sha256(x).hexdigest()
def iso(t):
    d=datetime.fromtimestamp(t,timezone.utc).isocalendar();return f'{d.year}-W{d.week:02d}'
def summarize(values):
    a=sorted(v for v in values if isinstance(v,(float,int)) and math.isfinite(v))
    return {'n':len(a),'min':a[0] if a else None,'median':a[len(a)//2] if a else None,'max':a[-1] if a else None}
def gate():
    h=os.environ['GITHUB_SHA'];e.w.v2.runtime(h)
    a=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text())
    need(a['authority']=='EXPLICIT_OWNER_EXISTING_PRIVATE_DIAGNOSTIC_NO_REPLAY_20261010','AUTHORITY')
    need(not any(a[k] for k in ('orders','protected_forward','cloud_deployment','scientific_replay','broker_requests')),'SCOPE')
    need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-executable-coverage-diagnostic-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW_SCOPE')
    need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'EXPIRED');e.a.ancestor(BASE,h)
    for p,s in a['bindings'].items():need(e.w.old.filehash(p)==s,'FROZEN_SOURCE_DRIFT')
    import subprocess
    inventory=lambda ref:dict(line.split('\t',1)[::-1] for line in subprocess.check_output(['git','ls-tree','-r',ref],cwd=e.a.ROOT,text=True).splitlines())
    old=inventory(BASE);new=inventory(h);need(len(old)==3840 and all(new.get(p)==s for p,s in old.items()),'PRESERVED_BASE')
    need(not e.w.v2.existing_ref(a['one_use_ref']),'CONSUMED');e.w.old.api('git/refs',{'ref':'refs/tags/'+a['one_use_ref'],'sha':h})
    return h,a
def counts(rows):
    out={'calendar':len(rows),'economic_pass':0,'feature_valid':0,'predictions_already_saved':0,'label_supported_already_saved':0,'economic_and_feature_valid':0,'reasons':Counter(),'economic_reasons':Counter()}
    for r in rows:
        ep=r['economics']['research_pass'];fv=r['phi'] is not None
        out['economic_pass']+=int(ep);out['feature_valid']+=int(fv);out['economic_and_feature_valid']+=int(ep and fv)
        out['predictions_already_saved']+=int(r['model'] is not None)
        out['label_supported_already_saved']+=int(r['model'] is not None and r['label']=='SUPPORTED')
        out['reasons'][r['reason']]+=1;out['economic_reasons'][r['economics']['reason']]+=1
    return out
def partition(rows):
    return {'global':counts(rows),'blocks':[counts([r for r in rows if r['block']==b]) for b in range(4)],
      'weeks':{w:counts([r for r in rows if r['iso']==w]) for w in ('2026-W34',)+FULL_WEEKS+('2026-W38',)}}
def boundary_quality(q):
    if point(q):return 'VALID_BOTH_FRESH_UNPAGED'
    s=q.get('sides',{})
    if any(s.get(k,{}).get('state')=='PROVIDER_ERROR' for k in ('bid','ask')):return 'PROVIDER_ERROR'
    if any(s.get(k,{}).get('state')!='AUTHENTIC_CAUSAL_QUOTE' for k in ('bid','ask')):return 'MISSING_BID_OR_ASK_IN_FIXED_60S'
    if any(s[k].get('source_has_more',False) for k in ('bid','ask')):return 'PAGED_RESPONSE_EXCLUDED'
    if any(s[k]['age_ms']>60000 for k in ('bid','ask')):return 'STALE_RESPONSE_EXCLUDED'
    return 'INVALID_CROSSED_OR_NONPOSITIVE_PRICE'
def reduce_saved(old,full,cost):
    trials=old['private_all_trials'];screens=old['private_all_identity_cost_screens']
    need(len(trials)==171024 and len(screens)==1018,'SAVED_COUNTS')
    need(old['summary']['source_head']=='98e0421317a16726d54f31ff9a0a9f98563fa85f','SAVED_SOURCE')
    byid=defaultdict(list)
    for r in trials:byid[r['sid']].append(r)
    measured=counts(trials)
    need(measured['economic_pass']==668 and measured['predictions_already_saved']==281 and measured['label_supported_already_saved']==262,'SAVED_SUPPORT_CONSERVATION')
    need(len(byid)==1018 and all(len(v)==168 for v in byid.values()),'SAVED_IDENTITY_SUPPORT')
    metadata={int(r['symbol_id']):r for r in cost['metadata_rows']}
    raw=full['private_boundary_receipts'];qm={(q['symbol_id'],q['boundary_ms']//1000):q for q in raw}
    need(len(qm)==len(raw)==8307,'QUOTE_COUNTS');valid={k:point(q) for k,q in qm.items() if point(q)}
    need(len(valid)==5730,'SAVED_QUOTE_VALIDITY_CONSERVATION')
    qid=defaultdict(list)
    for (sid,t),q in qm.items():qid[sid].append((t,q))
    horizon=defaultdict(Counter);old_event_horizons=Counter()
    for rec in full['private_event_coverage']:
        ev=rec['event'];old_event_horizons[ev['exit_reference_boundary']-ev['entry_reference_boundary']]+=1
    for sid,t in valid:
        for hours in (1,4):
            if (sid,t+hours*3600) in valid:
                horizon[sid][str(hours)+'h']+=1
                horizon[sid][str(hours)+'h/'+iso(t)]+=1
                if START<=t<END:horizon[sid][str(hours)+'h/block'+str((t-START)//604800)]+=1
    outids=[];passedids=[];eligible=[]
    costkeys=('min_volume_cents','step_volume_cents','lot_size','max_volume_cents','buy_margin_eur','sell_margin_eur','base_asset','quote_asset','commission_rate_normalized','commission_rate_unit','min_commission_normalized','min_commission_type','min_commission_asset','pnl_conversion_fee_pct','swap_long','swap_short','swap_calculation_type','swap_period','swap_time','swap_rollover_3_days','schedule_time_zone','source')
    quote_matches=Counter();needed_clock=Counter();predicted_clock=Counter()
    for r in trials:
        for name,t in [('entry',r['action']),('exit',r['exit'])]:
            needed_clock[name+'/'+str(t%3600)]+=1
            if r['model'] is not None:
                predicted_clock[name+'/'+str(t%3600)]+=1
                quote_matches[name+'_receipt']+=int((r['sid'],t) in qm)
                quote_matches[name+'_valid']+=int((r['sid'],t) in valid)
    for screen in screens:
        sid=screen['sid'];rr=byid[sid];p=partition(rr);qs=qid[sid];r=metadata[sid]
        ec=[t['economics'] for t in rr if t['economics']['research_pass']]
        item={'sid':sid,'symbol':screen['symbol'],'class':screen['class'],'saved_hourly_screen':screen,'support':p,
          'existing_boundary_quality':dict(Counter(boundary_quality(q) for _,q in qs)),
          'existing_valid_quote_horizons':dict(horizon[sid])}
        if screen['economic_pass_hourly']:
            item['current_contract']={k:r.get(k) for k in costkeys}
            item['saved_passing_costs']={k:summarize(v.get(k) for v in ec) for k in ('fee_bps','fee_eur','prior_spread_bps','causal_H1_range_bps','range_plus_cost_exposure_eur','causal_reference_notional_eur','minimum_units','captured_worst_min_margin_eur','cost_fraction_of_H1_range','current_pnl_conversion_fraction')}
            passedids.append(item)
        # Gate is explicitly feature/data/economics only. Never reads model sign, y or returns.
        good=all(z['economic_and_feature_valid']>=16 for z in p['blocks']) and all(p['weeks'][w]['economic_and_feature_valid']>=16 for w in FULL_WEEKS)
        item['sufficient_saved_cross_period_economic_feature_support']=good
        if good:eligible.append(sid)
        outids.append(item)
    # Acquisition priority uses support before future outcomes, then fee, margin and ID.
    candidates=[]
    for item in passedids:
        s=item['support'];mini=min(s['weeks'][w]['economic_and_feature_valid'] for w in FULL_WEEKS)
        minblock=min(z['economic_and_feature_valid'] for z in s['blocks'])
        if mini<2 or minblock<2:continue
        fee=item['saved_passing_costs']['fee_bps']['median'];margin=item['saved_passing_costs']['captured_worst_min_margin_eur']['median']
        candidates.append(((-mini,-minblock,fee,margin,item['sid']),item))
    candidates.sort(key=lambda z:z[0]);priority=[v for _,v in candidates[:3]];episodes=[]
    for item in priority:
        for w in FULL_WEEKS:
            available=sorted([r for r in byid[item['sid']] if r['iso']==w and r['phi'] is not None and r['economics']['research_pass']],key=lambda r:r['action'])
            for r in available[:2]:
                episodes.append({'sid':item['sid'],'symbol':item['symbol'],'week':w,'entry':r['action'],'exits':{'1h':r['action']+3600,'4h':r['action']+14400},'saved_causal_economics':r['economics']})
    summary={'schema':'mxm.private.executable.coverage.saved.diagnostic.v1','closed_source_head':old['summary']['source_head'],
      'original_result_unchanged':True,'signal_model_label_return_or_PnL_recalculated':False,'broker_requests':0,'orders':0,'protected_forward':False,
      'saved_summary_exclusion_counts':old['summary']['economic_screen_hourly_reasons'],'saved_1018_identity_evaluation_support':partition(trials),
      'quote_quality':dict(Counter(boundary_quality(q) for q in raw)),'quote_boundaries_by_second_within_hour':dict(Counter(str(t%3600) for _,t in qm)),
      'quote_boundaries_by_second_within_4h':dict(Counter(str(t%14400) for _,t in qm)),
      'predicted_entry_exit_exact_receipt_matches':dict(quote_matches),'predicted_clock_seconds_within_hour':dict(predicted_clock),
      'original_quote_source_event_horizon_seconds':dict(old_event_horizons),
      'sufficient_cross_period_economic_feature_identities':eligible,'identities_passing_saved_hourly_economic_screen':passedids,
      'diagnostic_acquisition_priority':[{'sid':v['sid'],'symbol':v['symbol'],'support':v['support'],'costs':v['saved_passing_costs'],'contract':v['current_contract']} for v in priority],
      'frozen_outcome_blind_probe_plan':episodes,'probe_max_new_tick_requests':len(episodes)*6,
      'all_identity_compact_support':[{'sid':v['sid'],'symbol':v['symbol'],'class':v['class'],'source_rows':v['saved_hourly_screen']['source_rows'],'hourly_economic_passes':v['saved_hourly_screen']['economic_pass_hourly'],'global_support':v['support']['global'],'block_economic_feature_support':[z['economic_and_feature_valid'] for z in v['support']['blocks']],'full_week_economic_feature_support':{w:v['support']['weeks'][w]['economic_and_feature_valid'] for w in FULL_WEEKS}} for v in outids],
      'granularity_limit':'SAVED_ECONOMIC_REFERENCE_OR_RANGE_UNAVAILABLE_AND_FEATURE_GAP_DO_NOT_SEPARATELY_IDENTIFY_MISSING_M5_VS_SESSION_CLOSURE_VS_BASELINE_INPUT;NO_CLOSED_CORPUS_REPLAY_TO_INFER_CAUSE',
      'historical_costs_and_fills':'CURRENT_CONTRACT_SCENARIO_ONLY;DATED_FEES_FUNDING_SWAP_ROLLOVER_SLIPPAGE_AND_FILLS_UNKNOWN',
      'selection':'NO_PRICE_DIRECTION_LABEL_VALUE_MODEL_SIGN_RETURN_OR_PNL_USED_FOR_UNIVERSE_OR_ACQUISITION_PRIORITY',
      'new_directional_experiment_authorized_here':False,'native_runtime':'NO_CHANGE;NO_CLOUD_PROBE_OR_DEPLOYMENT','robust_NET':False,'HARD21':False}
    detail={'summary':summary,'all_identity_full_diagnostics':outids,
      'all_valid_quote_horizon_support':[{'sid':sid,'support':dict(v)} for sid,v in sorted(horizon.items())],
      'boundary_receipt_index':[{'sid':sid,'timestamp':t,'quality':boundary_quality(q),'spread_bps':valid[sid,t]['spread_bps'] if (sid,t) in valid else None} for (sid,t),q in sorted(qm.items())]}
    return detail,summary
def relay(head,auth,tmp,summary):
    recipient=(e.a.ROOT/auth['recipient_path']).read_bytes();need(sha(recipient)==auth['recipient_public_key_sha256'],'RECIPIENT')
    pub=serialization.load_pem_public_key(recipient);need(pub.key_size>=3072,'KEY_STRENGTH')
    packed=gzip.compress(e.a.enc(summary),mtime=0);key=os.urandom(32);nonce=os.urandom(12);b64=lambda x:base64.b64encode(x).decode()
    wrapped=pub.encrypt(key,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
    body=e.a.enc({'version':'MXM_PRIVATE_EXECUTABLE_DIAGNOSTIC_V1','head':head,'recipient_pub_sha256':sha(recipient),'nonce_b64':b64(nonce),'wrapped_key_b64':b64(wrapped),'ciphertext_b64':b64(AESGCM(key).encrypt(nonce,packed,head.encode())),'compressed_plain_sha256':sha(packed)}).decode()
    if len(body)<=160000:
        rel=e.w.old.api('releases',{'tag_name':'mxm-executable-diagnostic-relay-'+auth['invocation_id']+'-'+os.environ['GITHUB_RUN_ID'],'target_commitish':head,'name':'MXM encrypted saved economic support diagnostics','body':body,'prerelease':True})
        need(e.w.old.api('releases/'+str(rel['id']))['body']==body,'RELAY_READBACK')
        print(json.dumps({'status':'PASS','run_id':int(os.environ['GITHUB_RUN_ID']),'head':head,'release_id':rel['id'],'envelope_sha256':sha(body.encode()),'numeric_outcomes_public':False}),flush=True)
    else:raise RuntimeError('ENCRYPTED_RELAY_SIZE_BUDGET')
def main():
    global PHASE
    os.umask(0o077);h,a=gate()
    with tempfile.TemporaryDirectory(prefix='mxm-saved-diagnostic-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'OWNER_KEY')
        PHASE='READ_EXISTING_ENCRYPTED_RESULTS';old,op=load_asset(key,fp,tmp,a['activity_source']);full,qp=load_asset(key,fp,tmp,a['quote_source']);cost,cp=load_asset(key,fp,tmp,a['cost_source'])
        PHASE='REDUCE_SAVED_SUPPORT_ONLY';detail,summary=reduce_saved(old,full,cost);summary['input_provenance']=[op,qp,cp]
        PHASE='OWNER_ENCRYPTED_DELIVERY';rt.output(h,a,tmp,key,'executablecoverage',detail,summary)
        PHASE='ENCRYPTED_SESSION_RELAY';relay(h,a,tmp,summary)
if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
