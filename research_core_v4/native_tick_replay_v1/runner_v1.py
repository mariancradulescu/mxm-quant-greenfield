"""Technical historical replay only; no returns, trading, Cloud deployment or broker calls."""
import os,json,math,pathlib,tempfile,hashlib,gzip,base64,subprocess
from collections import Counter,defaultdict
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.secure_two_liquidity_readback_v1.runner_v1 import source_read
from m6.cost_evidence import decode_ctrader_tick_page
P='research_core_v4/native_tick_replay_v1/';e=rt.e
sha=lambda b:hashlib.sha256(b).hexdigest()
def need(x,c):e.w.old.need(bool(x),c)
class State:
 def __init__(self):self.events=self.changes=self.backwards=self.sameTime=self.resets=0;self.clear()
 def clear(self):self.b=self.a=0;self.bt=self.at=self.bc=self.ac=self.last=-1;self.ambiguous=False
 def reset(self):self.clear();self.resets+=1
 def push(self,side,t,raw):
  if self.last>t:self.backwards+=1;self.reset()
  if self.last==t:self.sameTime+=1
  self.last=t;self.events+=1
  if side=='bid':
   if self.bt==t and self.b!=raw:self.ambiguous=True
   if self.bt>=0 and self.b!=raw:self.bc=t;self.changes+=1
   self.b=raw;self.bt=t
  else:
   if self.at==t and self.a!=raw:self.ambiguous=True
   if self.at>=0 and self.a!=raw:self.ac=t;self.changes+=1
   self.a=raw;self.at=t
 def snapshot(self,now,gap):
  reason='PAGE_GAP_OR_ERROR' if gap else 'AMBIGUOUS_SAME_MS' if self.ambiguous else 'MISSING_SIDE' if self.bt<0 or self.at<0 else 'WARMUP_NO_CHANGED_SIDE' if self.bc<0 or self.ac<0 else 'FUTURE' if now<self.bt or now<self.at else 'STALE_CHANGED_SIDE' if now-self.bc>5000 or now-self.ac>5000 else 'INVALID_QUOTE' if not 0<self.b<self.a else 'VALID'
  return {'reason':reason,'mid':(self.b+self.a)/200000 if reason=='VALID' else 0,'spread':10000*math.log(self.a/self.b) if reason=='VALID' else 0,'events':self.events,'changes':self.changes,'backwards':self.backwards,'sameTime':self.sameTime,'resets':self.resets}
def main():
 os.umask(0o077);head=os.environ['GITHUB_SHA'];a=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text());e.a.ancestor(a['base_head'],head)
 need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_RUN_ATTEMPT']=='1','RUN_SCOPE')
 need(os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-native-tick-replay-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW')
 for p,h in a['bindings'].items():need(e.w.old.filehash(p)==h,'BINDING')
 pubbytes=(e.a.ROOT/(P+'RECIPIENT_PUBLIC_KEY.pem')).read_bytes();pub=serialization.load_pem_public_key(pubbytes)
 tag='mxm-technical-native-replay-'+a['invocation_id'];need(not e.w.v2.existing_ref(tag),'ONE_USE');e.w.old.api('git/refs',{'ref':'refs/tags/'+tag,'sha':head})
 with tempfile.TemporaryDirectory(dir=os.environ['RUNNER_TEMP']) as td:
  tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'OWNER_KEY');full,proof=source_read(key,fp,tmp,a['source']);raw=full['private_native_quote_pages'];need(bool(raw),'NO_AUTHENTIC_INPUT')
  commands=[];expected=[];cohort=[];counts=Counter();bySymbol=defaultdict(Counter);modes=['CHRONOLOGICAL','RELOAD_SIMULATED','RESTART_SIMULATED','MISSING_ASK_SIMULATED','DELAY_6S_SIMULATED','BACKWARD_DELIVERY_SIMULATED'];authEvents=0
  for q in raw:
   ticks=[];gap=False
   for page in q['raw_pages']:
    if page.get('hasMore') or 'error_code' in page:gap=True
    if 'encoded' not in page:continue
    decoded=list(decode_ctrader_tick_page(page['encoded']));need(all(int(x.timestamp_ms)<=q['boundary']*1000 for x in decoded),'CAUSAL_SOURCE_FUTURE')
    ticks.extend((int(x.timestamp_ms),page['side'],int(x.raw_tick),i) for i,x in enumerate(decoded))
   ticks.sort(key=lambda x:(x[0],x[1],x[3]));authEvents+=len(ticks);sid=str(q['symbol_id']);counts['source_boundaries']+=1;counts['source_gap_boundaries']+=gap;bySymbol[sid]['source_boundaries']+=1
   for mode in modes:
    commands.append({'op':'new'});s=State();selected=[x for x in ticks if not(mode=='MISSING_ASK_SIMULATED' and x[1]=='ask')]
    for i,(t,side,rawprice,_) in enumerate(selected):
     if mode in ('RELOAD_SIMULATED','RESTART_SIMULATED') and i==len(selected)//2:
      if mode=='RELOAD_SIMULATED':s.reset();commands.append({'op':'reset'})
      else:s=State();commands.append({'op':'new'})
     s.push(side,t,rawprice);commands.append({'op':'tick','side':side,'time':t,'raw':rawprice})
     if i in (0,len(selected)//2,len(selected)-1):
      commands.append({'op':'snapshot','now':t,'gap':gap});expected.append(s.snapshot(t,gap));cohort.append((sid,mode,'EVENT_CHECKPOINT'))
    if mode=='BACKWARD_DELIVERY_SIMULATED' and len(selected)>1:
     t,side,price,_=selected[0];s.push(side,t,price);commands.append({'op':'tick','side':side,'time':t,'raw':price})
    now=q['boundary']*1000+(6000 if mode=='DELAY_6S_SIMULATED' else 0);commands.append({'op':'snapshot','now':now,'gap':gap});expected.append(s.snapshot(now,gap));cohort.append((sid,mode,'BOUNDARY'))
  payload=''.join(json.dumps(x,separators=(',',':'))+'\n' for x in commands).encode();need(len(payload)<300_000_000,'BOUNDED_REPLAY_SIZE');inputfile=tmp/'input';inputfile.write_bytes(payload);outputfile=tmp/'output'
  with inputfile.open('rb') as inp,outputfile.open('wb') as out:
   proc=subprocess.run(['dotnet',str(e.a.ROOT/(P+'csharp/bin/Release/net8.0/Replay.dll'))],stdin=inp,stdout=out,stderr=subprocess.PIPE,timeout=240)
  need(proc.returncode==0,'CSHARP_PROCESS');lines=outputfile.read_text().splitlines();need(len(lines)==len(expected),'PARITY_DENOMINATOR');maxdiff=0.;reasons=defaultdict(Counter)
  for py,line,group in zip(expected,lines,cohort):
   cs=json.loads(line)
   for k in ('reason','events','changes','backwards','sameTime','resets'):need(cs[k]==py[k],'EXACT_STATE_PARITY')
   for k in ('mid','spread'):
    diff=abs(cs[k]-py[k]);need(diff<=1e-10*max(1,abs(py[k])),'FLOAT_PARITY');maxdiff=max(maxdiff,diff)
   sid,mode,clock=group;reasons[mode+'|'+clock][py['reason']]+=1;bySymbol[sid][mode+'|'+clock+'|'+py['reason']]+=1
  result={'schema':'mxm.private.authentic.native.technical.replay.v1','head':head,'run':int(os.environ['GITHUB_RUN_ID']),'source_provenance':proof,'source_boundaries':len(raw),'decoded_authentic_side_records':authEvents,'comparison_snapshots':len(expected),'input_operations':len(commands),'input_sha256':sha(payload),'CSharp_Python_parity':'PASS_AUTHENTIC_PRICES_WITH_EXPLICIT_SIMULATED_CONTROL_EVENTS','max_absolute_feature_difference':maxdiff,'counts':dict(counts),'mode_reason_counts':{k:dict(v) for k,v in reasons.items()},'symbol_diagnostics':{k:dict(v) for k,v in bySymbol.items()},'modes':modes,'method':'Each original 70-second boundary independently reset; chronological side-page merge by broker timestamp with deterministic tie order; original encoded records retained; no artificial price data. Restarts/reloads/dropped ask/delay/backward delivery are explicitly simulated controls, not observed broker incidents. Checkpoints at authentic source event times and original boundary. Seed does not create change; unknown side and side gap abstain. No time-continuous history claimed.','runtime_limits':['OpenAPI side timestamps do not prove native combined Tick event ordering, receipts, wall clock delay or delivery','Native-compatible library compile is not actual Cloud execution','Not a replay of the audited Cloud binary; Cloud package untouched','Not a rerun or rescue of Nominal Round Barrier alpha; no directional features, returns, baseline or cost expectancy calculated'],'orders':0,'broker_requests':0,'cloud_deployment':False,'actual_Cloud_delivery':'NOT_VERIFIED','robust_NET':False,'HARD21':False}
  packed=gzip.compress(e.a.enc(result),mtime=0);aes=os.urandom(32);nonce=os.urandom(12);b64=lambda b:base64.b64encode(b).decode();wrapped=pub.encrypt(aes,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None));env={'schema':'mxm.technical.replay.encrypted.v1','head':head,'wrapped_key_b64':b64(wrapped),'nonce_b64':b64(nonce),'ciphertext_b64':b64(AESGCM(aes).encrypt(nonce,packed,head.encode())),'compressed_plain_sha256':sha(packed)};body=e.a.enc(env).decode()
  rel=e.w.old.api('releases',{'tag_name':tag+'-'+os.environ['GITHUB_RUN_ID'],'target_commitish':head,'name':'MXM encrypted technical historical replay only','body':body,'prerelease':True});need(e.w.old.api('releases/'+str(rel['id']))['body']==body,'REMOTE_CIPHER_READBACK');print(json.dumps({'status':'PASS','release':rel['id'],'envelope_sha256':sha(body.encode()),'orders':0,'Cloud':False,'private_numeric_public':False}),flush=True)
if __name__=='__main__':
 try:main()
 except Exception as exc:rt.fail(exc,'TECHNICAL_REPLAY');raise SystemExit(2) from None
