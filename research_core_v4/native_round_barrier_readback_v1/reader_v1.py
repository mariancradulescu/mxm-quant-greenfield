"""Authenticate ONLY the newly completed nominal-level result; no broker access or new experiment."""
import os,json,pathlib,tempfile,hashlib,gzip,base64,subprocess
from collections import Counter,defaultdict
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding,rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.secure_two_liquidity_readback_v1.runner_v1 import source_read
from research_core_v4.native_round_barrier_v1.runner_v1 import aggregate,clocks,quote_return
from research_core_v4.native_round_barrier_v1.kernel_v1 import feature,allocate,changed_point
e=rt.e;P='research_core_v4/native_round_barrier_readback_v1/';PHASE='GATE'
def need(x,c):e.w.old.need(bool(x),c)
def sha(x):return hashlib.sha256(x).hexdigest()
def cash_supplement(rows,chosen,quotes,summary):
 contracts={int(x['symbol_id']):x for x in summary['selected_current_contracts']};fxid=summary['EUR_conversion_native_symbol_id'];cashrows=[];samples=[]
 for row in rows:
  if row['reason']!='SUPPORTED':continue
  ent,_=changed_point(quotes.get((row['sid'],row['action'])));ex,_=changed_point(quotes.get((row['sid'],row['exit'])));fx,_=changed_point(quotes.get((fxid,row['exit'])));need(ent and ex and fx,'CASH_AUTHENTIC_ENDPOINTS')
  common={'quantity':row['economics']['volume_units'],'entry_bid':ent['bid'],'entry_ask':ent['ask'],'exit_bid':ex['bid'],'exit_ask':ex['ask'],'fx_bid':fx['bid'],'fx_ask':fx['ask'],'fee_bps':row['current_fee_scenario_bps'],'quote':contracts[row['sid']]['quote_currency']}
  outputs=[]
  for direction in (row['feature']['direction'],row['baseline_direction']):
   x={**common,'direction':direction};gross=x['quantity']*((ex['bid']-ent['ask']) if direction>0 else (ent['bid']-ex['ask']));value=gross-x['quantity']*ent['mid']*x['fee_bps']/10000
   corrected=value/((fx['ask'] if value>=0 else fx['bid']) if x['quote']=='USD' else 1.)
   outputs.append(corrected);samples.append({'input':x,'python':corrected})
  cashrows.append({'sid':row['sid'],'action':row['action'],'block':row['block'],'iso':row['iso'],'model_cash_EUR':outputs[0],'baseline_cash_EUR':outputs[1],'old_model_cash_EUR':row['cash_EUR_current_fee_quote_scenario']})
 parity={'status':'NO_AUTHENTIC_CASH_INPUT','samples':0}
 if samples:
  proc=subprocess.run(['dotnet',str(e.a.ROOT/(P+'csharp/bin/Release/net8.0/CashParity.dll'))],input=''.join(json.dumps(x['input'])+'\n' for x in samples).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90);need(proc.returncode==0,'CASH_CSHARP_PROCESS');lines=proc.stdout.decode().splitlines();need(len(lines)==len(samples),'CASH_SAMPLE_COUNT');err=0.
  for x,line in zip(samples,lines):
   cs=json.loads(line)['cash_EUR'];delta=abs(cs-x['python']);need(delta<=1e-9*max(1,abs(x['python'])),'CASH_CSHARP_PARITY');err=max(err,delta)
  parity={'status':'PASS_AUTHENTIC_IDENTICAL_CASH_INPUTS','samples':len(samples),'max_absolute_difference':err}
 chosenkeys={(x['sid'],x['action']) for x in chosen}
 def reduce_cash(values,one_clock=False):
  n=len(values);equity=peak=200.;dd=0.
  for x in sorted(values,key=lambda x:(x['action'],x['sid'])):equity+=x['model_cash_EUR'];peak=max(peak,equity);dd=max(dd,peak-equity)
  model=sum(x['model_cash_EUR'] for x in values);baseline=sum(x['baseline_cash_EUR'] for x in values)
  return {'supported':n,'model_cash_EUR_sum':model,'baseline_cash_EUR_sum':baseline,'paired_increment_cash_EUR_sum':model-baseline,'model_cash_EUR_mean':model/n if n else None,'correction_from_old_model_cash_EUR_sum':sum(x['model_cash_EUR']-x['old_model_cash_EUR'] for x in values),'indicative_known_markout_drawdown_EUR':dd if one_clock else None,'scope':'CURRENT_FEE_PRICE_EQUIVALENT_SCENARIO;SIGN_APPROPRIATE_NATIVE_FX;NOT_ACTUAL_CHARGES_FILLS_OR_COMPLETE_EQUITY;MISSING_SELECTED_QUOTES_NOT_ZERO'}
 selected=[x for x in cashrows if (x['sid'],x['action']) in chosenkeys]
 return {'original_cash_convention':'PRESERVED_IN_IMMUTABLE_ORIGINAL_RESULT;UNIFORM_BID_OVERSTATES_USD_GAINS','pre_numeric_read_correction_record':'native_round_barrier_v1/PRE_NUMERIC_READ_INTEGRITY_V1.json','CSharp_cash_parity':parity,'all_panel_rows':reduce_cash(cashrows),'single_clock_allocation':reduce_cash(selected,True),'single_clock_original_blocks':[{'block':b,**reduce_cash([x for x in selected if x['block']==b],True)} for b in range(4)],'single_clock_ISO_weeks':[{'week':w,'complete':w in ('2026-W35','2026-W36','2026-W37'),**reduce_cash([x for x in selected if x['iso']==w],True)} for w in ('2026-W34','2026-W35','2026-W36','2026-W37','2026-W38')],'changes_frozen_alpha_gates':False,'new_broker_requests':0,'fills':0,'robust_NET_certified':False}
def main():
 global PHASE
 os.umask(0o077);head=os.environ['GITHUB_SHA'];e.w.v2.runtime(head);a=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text())
 need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_RUN_ATTEMPT']=='1' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-native-round-barrier-readback-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW_SCOPE')
 need(not any(a[k] for k in ('orders','demo_orders','cloud_deployment','protected_forward','new_broker_requests','new_experiment')),'SCOPE');e.a.ancestor(a['base_head'],head)
 for p,h in a['bindings'].items():need(e.w.old.filehash(p)==h,'BINDING')
 old=json.loads((e.a.ROOT/'research_core_v4/native_round_barrier_v1/EXECUTION_V1.json').read_text())
 for p,h in old['bindings'].items():need(e.w.old.filehash(p)==h,'ORIGINAL_NEW_FREEZE')
 tag='mxm-native-round-readback-'+a['invocation_id'];need(not e.w.v2.existing_ref(tag),'ONE_USE');e.w.old.api('git/refs',{'ref':'refs/tags/'+tag,'sha':head})
 pubbytes=(e.a.ROOT/(P+'RECIPIENT_PUBLIC_KEY.pem')).read_bytes();need(sha(pubbytes)==a['recipient_public_key_sha256'],'RECIPIENT');pub=serialization.load_pem_public_key(pubbytes);need(isinstance(pub,rsa.RSAPublicKey) and pub.key_size>=3072,'KEY_STRENGTH')
 with tempfile.TemporaryDirectory(prefix='mxm-round-readback-',dir=os.environ['RUNNER_TEMP']) as td:
  tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'OWNER_KEY');PHASE='NEW_PRIMARY_ATTESTATION_ONLY';full,proof=source_read(key,fp,tmp,a['source']);s=full['summary'];need(s['schema']=='mxm.private.native.nominal.round.barrier.reflection.v1','NEW_EXACT')
  need(s['orders']==s['demo_orders']==0 and not s['cloud_deployment'] and not s['protected_forward'],'NO_FORBIDDEN_ACTION')
  rows=full['private_new_events'];chosen=full['private_single_clock_selection'];samples=full['private_authentic_parity_samples'];raw=full['private_native_quote_pages'];need(len(rows)==160*len(s['selected_current_contracts']),'DENOMINATOR')
  need(allocate(rows,[t for _,t in clocks()])==chosen,'CAUSAL_ALLOCATION_NO_FUTURE_REPLACEMENT');need(aggregate(rows,chosen)==s['numeric'],'ALL_ORIGINAL_REDUCERS')
  need(len(samples)==s['CSharp_Python_parity']['samples'],'PARITY_INPUT_COUNT')
  for x in samples:need(feature(x['bid'],x['ask'],x['digits'])==x['python'],'AUTHENTIC_INPUT_KERNEL_RECORD')
  quotes={(x['symbol_id'],x['boundary']):x for x in raw}
  for row in rows:
   if row['reason']!='SUPPORTED':continue
   ent,er=changed_point(quotes.get((row['sid'],row['action'])));ex,xr=changed_point(quotes.get((row['sid'],row['exit'])));past,pr=changed_point(quotes.get((row['sid'],row['action']-3600)))
   need(ent is not None and ex is not None and past is not None,'QUOTE_SUPPORT');need(ent['age_ms']==row['entry_age_ms'] and ex['age_ms']==row['exit_age_ms'],'AUTHENTIC_QUOTE_AGE')
   baseline=(ent['mid']>past['mid'])-(ent['mid']<past['mid']);need(baseline==row['baseline_direction'],'BASELINE_DIRECTION')
   need(abs(quote_return(row['feature']['direction'],ent,ex)-row['model_bps'])<=1e-10 and abs(quote_return(baseline,ent,ex)-row['baseline_bps'])<=1e-10,'MATCHED_QUOTE_MARKOUTS')
  diagnostics=defaultdict(Counter)
  for q in raw:
   pt,reason=changed_point(q);phase='QUALIFICATION' if q['boundary']<1787184000 else 'DEVELOPMENT'
   diagnostics[str(q['symbol_id'])+'|'+phase][reason]+=1
  cash=cash_supplement(rows,chosen,quotes,s)
  safe={'native_boundary_diagnostics':{k:dict(v) for k,v in diagnostics.items()},'direct_EUR_unnecessary_FX_gate_static_finding':True,'cash_integrity_supplement':cash,'schema':'mxm.owner.new.round.authenticated.readback.v1','original_provenance':proof,'summary':s,'authenticated_events':len(rows),'authenticated_boundaries':len(raw),'authenticated_parity_inputs':len(samples),'integrity':'PRIMARY_ATTESTATION_QUOTES_BASELINE_ALLOCATION_AND_REDUCERS_PASS','broker_requests':0,'new_experiments':0,'orders':0,'Cloud_deployment':False,'independent_external_replication_claimed':False}
  packed=gzip.compress(e.a.enc(safe),mtime=0);aes=os.urandom(32);nonce=os.urandom(12);b64=lambda x:base64.b64encode(x).decode();wrapped=pub.encrypt(aes,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None));env={'version':'MXM_NATIVE_ROUND_VERIFIED_V1','head':head,'recipient_pub_sha256':sha(pubbytes),'wrapped_key_b64':b64(wrapped),'nonce_b64':b64(nonce),'ciphertext_b64':b64(AESGCM(aes).encrypt(nonce,packed,head.encode())),'compressed_plain_sha256':sha(packed),'original_cipher_sha256':proof['cipher_sha256']};body=e.a.enc(env).decode();need(len(body)<160000,'PRIVATE_RELAY_BUDGET')
  rel=e.w.old.api('releases',{'tag_name':'mxm-native-round-verified-aggregate-'+a['invocation_id']+'-'+os.environ['GITHUB_RUN_ID'],'target_commitish':head,'name':'MXM encrypted authenticated NEW native nominal-level aggregates','body':body,'prerelease':True});need(e.w.old.api('releases/'+str(rel['id']))['body']==body,'REMOTE_ENVELOPE')
  print(json.dumps({'schema':'mxm.owner.new.native.round.readback.public.v1','status':'PASS','head':head,'run':int(os.environ['GITHUB_RUN_ID']),'release':rel['id'],'envelope_sha256':sha(body.encode()),'broker_requests':0,'new_experiments':0,'orders':0,'private_numeric_outcomes_public':False}),flush=True)
if __name__=='__main__':
 try:main()
 except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
