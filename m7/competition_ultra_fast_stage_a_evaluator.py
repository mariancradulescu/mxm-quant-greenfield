from __future__ import annotations
import csv,hashlib,io,json,statistics,zipfile
from collections import Counter
from datetime import datetime,timezone,timedelta
from pathlib import Path
from discovery.canonical import compute_result_hash,verify_spec_hash
from discovery.schema import validate_result
VERSION='MXM_COMPETITION_ULTRA_FAST_STAGE_A_EVALUATOR_V1'
CAP='dd0736c3156abfa057303a9b2a31ef3db36b02d66afc5fa33ddccc7f416f5d3d';P='MXM_COMPETITION_ULTRA_FAST_STAGE_A_V6/'
IDS=('V2-C017','V2-C018','V2-C019','V2-C020','V2-C021','V2-C022');S=datetime(2026,6,15,tzinfo=timezone.utc);E=datetime(2026,9,14,tzinfo=timezone.utc);L4=datetime(2026,8,17,tzinfo=timezone.utc);M5=timedelta(minutes=5);N=1000.0
class WaveIntegrityError(ValueError):pass
def shab(b):return hashlib.sha256(b).hexdigest()
def shaf(p):return shab(Path(p).read_bytes())
def dt(s):return datetime.fromisoformat(s.replace('Z','+00:00')).astimezone(timezone.utc)
def openzip(p,a):
 if shaf(p)!=CAP or a['source']['zip_sha256']!=CAP:raise WaveIntegrityError('capture SHA mismatch')
 z=zipfile.ZipFile(p);bad=z.testzip()
 if bad:raise WaveIntegrityError('capture CRC failure')
 d={x.split('  ',1)[1]:x.split('  ',1)[0] for x in z.read(P+'CHECKSUMS.sha256').decode().splitlines() if x.strip()};q={}
 for n in z.namelist():
  if n.startswith(P) and not n.endswith('/') and not n.endswith('CHECKSUMS.sha256'):q[n[len(P):]]=shab(z.read(n))
 if d!=q:raise WaveIntegrityError('internal checksum mismatch')
 return z
def rows(z,s):
 q=[]
 for r in csv.DictReader(io.StringIO(z.read(P+f'stage_a_m5/{s}_M5.csv').decode())):q.append({'t':dt(r['time_utc']),'o':float(r['open']),'h':float(r['high']),'l':float(r['low']),'c':float(r['close'])})
 if not q or any(q[i]['t']>=q[i+1]['t'] for i in range(len(q)-1)):raise WaveIntegrityError(s+' chronology')
 return q
def cont(q,a,b):return a>=0 and b<len(q) and all(q[i+1]['t']-q[i]['t']==M5 for i in range(a,b))
def trade(cid,s,d,a,b,cost):return {'cid':cid,'s':s,'d':d,'e':a['t'],'x':b['t']+M5,'p':a['o'],'q':b['c'],'costf':cost}
def single(q,cid,mode,cost):
 look=15 if mode=='VOL' else 12;hold=6 if mode=='VOL' else 12;out=[];i=look
 while i+hold<len(q):
  ei=i+1;xi=ei+hold-1
  if not cont(q,i-look,xi):i+=1;continue
  d=None
  if mode in ('MOM','REV'):
   r=q[i]['c']/q[i-12]['c']-1
   if r:d='LONG' if ((r>0)==(mode=='MOM')) else 'SHORT'
  elif mode=='BRK':
   x=q[i-12:i];d='LONG' if q[i]['c']>max(v['h'] for v in x) else ('SHORT' if q[i]['c']<min(v['l'] for v in x) else None)
  else:
   r=q[i]['c']/q[i-3]['c']-1;m=statistics.median(abs(q[j]['c']/q[j-3]['c']-1) for j in range(i-12,i))
   if r and abs(r)>m:d='LONG' if r>0 else 'SHORT'
  if d:out.append(trade(cid,'',d,q[ei],q[xi],cost));i=xi+1
  else:i+=1
 return out
def cross(a,b,cid,mode,cost):
 A={x['t']:x for x in a};B={x['t']:x for x in b};t=sorted(set(A)&set(B));v=[(x,A[x],B[x]) for x in t];out=[];i=12
 while i+12<len(v):
  ei=i+1;xi=ei+11
  if not all(v[j+1][0]-v[j][0]==M5 for j in range(i-12,xi)):i+=1;continue
  if mode=='LEAD':r=v[i][1]['c']/v[i-12][1]['c']-1;d='LONG_US2000' if r>0 else ('SHORT_US2000' if r<0 else None);s='US2000'
  else:r=(v[i][1]['c']/v[i-12][1]['c']-1)-(v[i][2]['c']/v[i-12][2]['c']-1);d='LONG_SPOTBRENT' if r>0 else ('SHORT_SPOTBRENT' if r<0 else None);s='SpotBrent'
  if d:out.append(trade(cid,s,d,v[ei][2],v[xi][2],cost));i=xi+1
  else:i+=1
 return out
def weeks():
 o=[];d=S
 while d<E:
  k=f'{d.isocalendar().year}-W{d.isocalendar().week:02d}'
  if k not in o:o.append(k)
  d+=timedelta(days=1)
 return o
def add(b,k,g,c,n):
 x=b.setdefault(k,{'event_count':0,'gross_pnl_eur':0.0,'transaction_cost_eur':0.0,'coarse_net_pnl_eur':0.0});x['event_count']+=1;x['gross_pnl_eur']+=g;x['transaction_cost_eur']+=c;x['coarse_net_pnl_eur']+=n
def evaluate(cid,spec,T,csha):
 if not T:raise WaveIntegrityError(cid+' no events')
 T=sorted(T,key=lambda x:(x['x'],x['s'],x['d'],x['e']));W={k:0 for k in weeks()};wd={k:0 for k in ('MON','TUE','WED','THU','FRI','SAT','SUN')};ss=Counter();sy={};di={};sub={};dates=set();holds=[];gross=cost=net=cum=peak=dd=0.0
 for t in T:
  sign=1 if t['d'].startswith('LONG') else -1;g=((t['q']-t['p'])/t['p'])*sign*N;c=t['costf']*N;n=g-c;gross+=g;cost+=c;net+=n;cum+=n;peak=max(peak,cum);dd=max(dd,peak-cum)
  z=t['e'].isocalendar();W[f'{z.year}-W{z.week:02d}']+=1;wd[('MON','TUE','WED','THU','FRI','SAT','SUN')[t['e'].weekday()]]+=1;h=(t['e'].hour//3)*3;ss[f'UTC_{h:02d}_{(h+3)%24:02d}']+=1;dates.add(t['e'].date());holds.append((t['x']-t['e']).total_seconds()/60);add(sy,t['s'],g,c,n);add(di,t['d'],g,c,n);add(sub,'LATEST_4W' if t['e']>=L4 else 'EARLY_9W',g,c,n)
 D=sorted(dates);gaps=[(D[0]-S.date()).days]+[(b-a).days-1 for a,b in zip(D,D[1:])]+[(E.date()-D[-1]).days];m={'event_count':len(T),'gross_pnl':gross,'coarse_net_pnl':net,'gross_return':gross/(len(T)*N),'coarse_net_return':net/(len(T)*N),'gross_per_event':gross/len(T),'net_per_event':net/len(T),'cost_burden':cost/(len(T)*N),'turnover':2*N*len(T),'weekly_events':W,'active_weeks':sum(x>0 for x in W.values()),'longest_inactive_gap':max(gaps),'weekday_distribution':wd,'session_distribution':dict(ss),'hold_duration':{'min_minutes':min(holds),'median_minutes':statistics.median(holds),'mean_minutes':statistics.mean(holds),'max_minutes':max(holds)},'exposure':sum(holds)/(((E-S).total_seconds()/60)*max(1,len(sy))),'drawdown':dd,'symbol_contribution':sy,'direction_contribution':di,'subperiod_contribution':sub,'regime_contribution':{'state':'NOT_APPLICABLE','reason':'No prospectively frozen regime taxonomy in Wave 01.'}}
 st='GROSS_EDGE_FAIL' if gross<=0 else ('COARSE_NET_FAIL' if net<=0 else 'DISCOVERY_SURVIVOR');r={'candidate_id':cid,'spec_hash':spec['spec_hash'],'stage':'A','status':st,'implementation_validity':{'state':'VALID','reason':'Frozen causal M5 evaluator and exact capture/cost gates passed.'},'metrics':m,'eur200_feasibility':{'state':'NOT_EVALUATED','reason':'Stage A fixed EUR1000 analytic normalization; exact shared EUR200 replay requires survivor Stage-B volume lattice and causal margin.'},'cost_confidence':{'state':'CONSERVATIVE_BOUND','reason':'Outcome-blind p75 across sampled-window p95 effective roundtrip friction fractions.'},'data_completeness':{'state':'SUFFICIENT','reason':'Accepted V6 13-week M5 capture with explicit pagination exhaustion and checksum binding.'},'provenance':{'data_evidence':{'identity':'MXM_COMPETITION_ULTRA_FAST_STAGE_A_V6','binding':{'type':'DATASET_SHA256','sha256':CAP}},'cost_evidence':{'identity':'COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1','state':'CONSERVATIVE_BOUND','sha256':csha},'evaluator':{'version':VERSION,'sha256':shaf(__file__)}}};validate_result(r);r['result_hash']=compute_result_hash(r);validate_result(r);return r
def execute_wave(root,zp):
 root=Path(root);a=json.loads((root/'data/COMPETITION_ULTRA_FAST_STAGE_A_V6_ACCEPTANCE_V1.json').read_text());c=json.loads((root/'evidence/COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1.json').read_text());w=json.loads((root/'discovery/COMPETITION_ULTRA_FAST_ECONOMIC_WAVE_01_V1.json').read_text());z=openzip(Path(zp),a);cs=shaf(root/'evidence/COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1.json');sp={}
 for cid in IDS:
  q=json.loads((root/'discovery/candidates'/f'{cid}.json').read_text());verify_spec_hash(q)
  if q['spec_hash']!=w['candidate_spec_hashes'][cid]:raise WaveIntegrityError('wave spec mismatch')
  sp[cid]=q
 R={s:rows(z,s) for s in a['selected_markets']};C={k:v['roundtrip_cost_fraction'] for k,v in c['symbols'].items()};T={i:[] for i in IDS}
 for s,q in R.items():
  for cid,mode in (('V2-C017','MOM'),('V2-C018','REV'),('V2-C019','BRK'),('V2-C020','VOL')):
   x=single(q,cid,mode,C[s]);T[cid]+=[dict(t,s=s) for t in x]
 T['V2-C021']=cross(R['US500'],R['US2000'],'V2-C021','LEAD',C['US2000']);T['V2-C022']=cross(R['SpotCrude'],R['SpotBrent'],'V2-C022','REL',C['SpotBrent']);res={i:evaluate(i,sp[i],T[i],cs) for i in IDS};keys={}
 for cid,x in T.items():
  for t in x:keys.setdefault((t['e'].isoformat(),t['s']),[]).append((cid,t['d']))
 uw={k:0 for k in weeks()}
 for ts,s in keys:
  d=dt(ts);uw[f'{d.isocalendar().year}-W{d.isocalendar().week:02d}']+=1
 ov=[v for v in keys.values() if len(v)>1];summ={'schema':'mxm.greenfield.v2.competition-ultra-fast-economic-wave-01-stage-a-summary.v1','capture_sha256':CAP,'results':{i:{'status':r['status'],'event_count':r['metrics']['event_count'],'gross_pnl':r['metrics']['gross_pnl'],'coarse_net_pnl':r['metrics']['coarse_net_pnl'],'net_per_event':r['metrics']['net_per_event'],'drawdown':r['metrics']['drawdown'],'active_weeks':r['metrics']['active_weeks'],'latest_4w':r['metrics']['subperiod_contribution'].get('LATEST_4W',{}),'weekly_events':r['metrics']['weekly_events'],'result_hash':r['result_hash']} for i,r in res.items()},'natural_hard21':{'distinct_symbol_time_opportunities':len(keys),'candidate_overlap_symbol_times':len(ov),'same_direction_overlap_symbol_times':sum(len({1 if d.startswith('LONG') else -1 for _,d in v})==1 for v in ov),'opposite_direction_conflict_symbol_times':sum(len({1 if d.startswith('LONG') else -1 for _,d in v})>1 for v in ov),'unique_opportunities_by_week':uw,'weeks_ge_21':sum(v>=21 for v in uw.values()),'weeks_lt_21':sum(v<21 for v in uw.values()),'worst_deficit':max(0,21-min(uw.values()))},'shared_eur200':{'state':'NOT_EVALUATED','reason':'Stage-A capture lacks exact broker volume lattice/contract-size and causal margin path; no synthetic executable sizing is invented.'},'stage_b_extension_candidates':[i for i,r in res.items() if r['status']=='DISCOVERY_SURVIVOR'],'protected_evidence_opened':False};return res,summ
