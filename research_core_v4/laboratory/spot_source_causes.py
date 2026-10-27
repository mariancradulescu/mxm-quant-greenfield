"""Independent descriptive cause reference. No source policy/response/model change."""
import hashlib,json,subprocess,tempfile
from collections import Counter
from pathlib import Path
from .common import need,encoded,bytes_digest
from .spot_observation_profile import SpotProfile
ROOT=Path(__file__).resolve().parents[2]
PROJECT='research_core_v4/laboratory/csharp/spot_source/MxmSpotSource.csproj'
KEYS={'symbol','sequence','arrival_ns','received_ms','server_ms','bid','ask'}
def shape(bid,ask):
    if bid is None or ask is None:return 'MISSING'
    if min(bid,ask)<=0:return 'INVALID'
    return 'LOCKED' if bid==ask else 'CROSSED' if bid>ask else 'POSITIVE'
def reference(events):
    old=SpotProfile([1,2,250]);books={s:{'sides':{},'first':True,'last_server':None,'last_arrival':None,
      'last_healthy':False,'shapes':Counter(),'fields':Counter(),'same':Counter(),'server_failures':0,
      'gaps':0,'healthy_gaps':0,'locked_both':0,'crossed_both':0} for s in (1,2,250)}
    h=hashlib.sha256();count=0
    for e in events:
        need(set(e)==KEYS,'SPOT_CAUSE_EXACT_FIELDS');old.observe(**e);count+=1
        b=books[e['symbol']];initial=b['first'];b['first']=False
        present=[s for s in ('bid','ask') if e[s] is not None]
        field='both' if len(present)==2 else present[0]+'_only' if present else 'neither';b['fields'][field]+=1
        server=e['server_ms'];ns=e['arrival_ns'];t=e['received_ms']
        server_ok=server is not None and 0<=t-server<=5000 and (b['last_server'] is None or server>=b['last_server'])
        b['server_failures']+=not server_ok
        if server is not None:b['last_server']=server if b['last_server'] is None else max(server,b['last_server'])
        for side in present:
            previous=b['sides'].get(side)
            b['same'][side]+=previous is not None and previous[0]==e[side]
            b['sides'][side]=(e[side],ns,server if server_ok and not initial else None)
        current=shape(*(b['sides'][s][0] if s in b['sides'] else None for s in ('bid','ask')))
        b['shapes'][current]+=1
        b['locked_both']+=current=='LOCKED' and field=='both';b['crossed_both']+=current=='CROSSED' and field=='both'
        gap=b['last_arrival'] is not None and ns-b['last_arrival']>5000000000;b['gaps']+=gap
        healthy=(not initial and bool(present) and server_ok and current=='POSITIVE' and
          len(b['sides'])==2 and all(v[2] is not None and 0<=t-v[2]<=5000 and 0<=ns-v[1]<=5000000000 for v in b['sides'].values()))
        b['healthy_gaps']+=healthy and b['last_healthy'] and gap;b['last_healthy']=healthy;b['last_arrival']=ns
        h.update(encoded([e['symbol'],e['sequence'],current,healthy,initial,gap,field])+b'\n')
    causes={str(s):{'book_shapes':dict(sorted(b['shapes'].items())),'field_patterns':dict(sorted(b['fields'].items())),
      'explicit_same_price_bid_updates':b['same']['bid'],'explicit_same_price_ask_updates':b['same']['ask'],
      'server_clock_failures':b['server_failures'],'gaps_over_5s':b['gaps'],'healthy_to_healthy_gap_breaks':b['healthy_gaps'],
      'locked_with_both_fields':b['locked_both'],'crossed_with_both_fields':b['crossed_both']} for s,b in books.items()}
    return {'schema':'mxm.csharp.spot-source-cause-classification.v1','events':count,'profile':old.result(),'causes':causes,
      'event_disposition_sha256':h.hexdigest(),'fixed_age_ms':5000,'fixed_observed_span_ms':300000,
      'source_authenticated_in_program':False,'original_consumer_policy_changed':False,'economic_model_executed':False,
      'broker_orders':0,'economic_edge_proven':False,'hard21_proven':False}
def rows(path):
    need(Path(path).stat().st_size<=5000000,'SPOT_CAUSE_INPUT_CAP')
    with Path(path).open('rb') as f:
        for line in f:
            need(len(line)<=512,'SPOT_CAUSE_ROW_CAP');yield json.loads(line)
def reconcile(path,report):
    need(report['input_sha256']==bytes_digest(Path(path).read_bytes()),'SPOT_CAUSE_EXACT_INPUT')
    need(report['result']==reference(rows(path)),'SPOT_CAUSE_EVERY_DISPOSITION_AND_COUNT')
    return True
def run(events):
    with tempfile.TemporaryDirectory() as tmp:
        src=Path(tmp)/'source';dst=Path(tmp)/'report'
        src.write_bytes(b''.join(encoded(e)+b'\n' for e in events))
        subprocess.run(['dotnet','run','--project',str(ROOT/PROJECT),'-c','Release','--no-build','--',str(src),str(dst)],check=True,capture_output=True)
        report=json.loads(dst.read_bytes());reconcile(src,report);return report['result']
