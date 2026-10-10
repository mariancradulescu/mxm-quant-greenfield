"""One economic capacity calculation from accepted saved data, zero broker calls."""
import os,json,pathlib,tempfile,subprocess,hashlib,base64,csv,io,math
from datetime import datetime,timezone
from collections import Counter
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.executable_coverage_diagnostic_v1.runner_v1 import relay
from research_core_v4.native_economic_frontier_v2 import kernel_v2 as k
e=rt.e;P='research_core_v4/native_economic_frontier_v2/';PHASE='GATE'
def need(x,c):e.w.old.need(bool(x),c)
def stamp(s):return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp())
def inv(ref):return dict(x.split('\t',1)[::-1] for x in subprocess.check_output(['git','ls-tree','-r',ref],cwd=e.a.ROOT,text=True).splitlines())
def extensions(old):
    allbars={};summary=[]
    for source in old['archive_recovery']['sources']:
        raw=base64.b64decode(source['member_bytes_b64'],validate=True);need(hashlib.sha256(raw).hexdigest()==source['member_sha256'],'ACCEPTED_ARCHIVE_MEMBER_SHA')
        need(e.w.old.filehash(source['acceptance_path'])==source['acceptance_sha256'],'ACCEPTED_ARCHIVE_AUTHORITY_SHA')
        need(source['same_account_fingerprint_sha256']=='b8bd610d0fe4395264e04bad98284c716d4b9d32fb46ce3ae6a2a9a1fd619636','SAME_ACCOUNT_ARCHIVE')
        rs=list(csv.DictReader(io.StringIO(raw.decode())));need(all(stamp(r['time_utc'])<k.END for r in rs),'ARCHIVE_PROTECTED_BOUNDARY')
        times=[stamp(r['time_utc']) for r in rs];need(times==sorted(set(times)),'ACCEPTED_ARCHIVE_ORDER');sid=source['sid'];bars={stamp(r['time_utc']):r for r in rs};allbars[sid]=bars
        older=[t for t in times if t<k.START];calendar=[d+h*3600+900 for d in range((min(times)//86400)*86400,k.START,86400) if datetime.fromtimestamp(d,timezone.utc).weekday()<5 for h in (9,13)]
        valid=[t for t in calendar if all(t-600-i*300 in bars for i in range(12))];weeks=Counter(k.iso(t) for t in valid)
        summary.append({'sid':sid,'archive':source['archive'],'accepted_member_sha256':source['member_sha256'],'source_start_utc':rs[0]['time_utc'],'source_last_utc':rs[-1]['time_utc'],'source_rows':len(rs),'pre_current_development_rows':len(older),'older_fixed_clock_feature_valid':len(valid),'older_fixed_clock_feature_counts_by_ISO':dict(weeks),'older_complete_10clock_feature_weeks':sum(n==10 for n in weeks.values()),'older_exact_live_bidask_and_FX_boundaries':0,'older_NET_evaluable_episodes_from_this_saved300_boundary_set':0,'other_account_demo_ticks_are_not_substitutes':True,'previously_exposed_development_not_independent_confirmation':True})
    common_start=max(min(b) for b in allbars.values());calendar=[d+h*3600+900 for d in range((common_start//86400)*86400,k.START,86400) if datetime.fromtimestamp(d,timezone.utc).weekday()<5 for h in (9,13)]
    common=[t for t in calendar if all(t-600-i*300 in allbars[s] for s in k.SIDS for i in range(12))]
    return {'identities':summary,'shared_older_feature_valid_clocks':len(common),'shared_older_feature_clocks_by_ISO':dict(Counter(k.iso(t) for t in common)),'extension_type':'M5_ONLY_ACCEPTED_SAME_ACCOUNT_PREFIX;NO_NEW_ACQUISITION;NO_PAST_NET_OR_INDEPENDENT_CONFIRMATION_CERTIFICATION'}
def main():
    global PHASE
    os.umask(0o077);h=os.environ['GITHUB_SHA'];e.w.v2.runtime(h);a=json.loads((e.a.ROOT/(P+'EXECUTION_V2.json')).read_text())
    need(a['authority']=='EXPLICIT_OWNER_CAUSAL_ECONOMIC_CONTINUATION_20261010' and not any(a[x] for x in ('broker_requests','orders','protected_forward','cloud_deployment','closed_exact_replay')),'AUTHORITY_SCOPE')
    need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-native-economic-frontier-v2.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW')
    need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'EXPIRED');e.a.ancestor(a['base_head'],h)
    for p,s in a['bindings'].items():need(e.w.old.filehash(p)==s,'SOURCE_FREEZE')
    oldtree=inv(a['base_head']);newtree=inv(h);need(all(newtree.get(p)==v for p,v in oldtree.items()),'ALL_OLD_FILES_PRESERVED');e.w.old.verify_science()
    need(not e.w.v2.existing_ref(a['one_use_ref']),'CONSUMED');e.w.old.api('git/refs',{'ref':'refs/tags/'+a['one_use_ref'],'sha':h})
    with tempfile.TemporaryDirectory(prefix='mxm-economic-frontier-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'OWNER_KEY');PHASE='EXISTING_ACCEPTED_INPUTS'
        old,op=load_asset(key,fp,tmp,a['qualification_source']);cost,cp=load_asset(key,fp,tmp,a['cost_source'])
        need(old['summary']['decision']=='DATA_LIMITED','V1_PRESERVED');native=cost['current_native_evidence']['private_native_evidence'];assets={str(x['assetId']):x['name'] for x in native['assets']}
        for sid in k.SIDS:
            light=next(x for x in native['light'] if int(x['symbolId'])==sid);need(assets[str(light['quoteAssetId'])]=='USD','USD_QUOTED_UNIVERSE')
        PHASE='NUMERIC_ENTRY_COST_CAPACITY_AND_ACCEPTED_PREFIX';out=k.run(old,cost,extensions(old));need(all(x['scheduled_entries']==40 and not x['precision_gate']['pass'] for x in out['entry_universe']),'DIRECTIONAL_SUPPORT_STOP')
        out.update(source_head=h,input_provenance=[op,cp],design_sha256=e.w.old.filehash(P+'DESIGN_FREEZE_V2.json'),new_broker_requests=0,orders=0,protected_forward=False,cloud_deployment=False,V1_unchanged=True,scientific_replay=False)
        summary={n:v for n,v in out.items() if n not in ('private_entry_rows','private_capacity_rows')}
        PHASE='ENCRYPTED_OWNER_AND_SESSION_DELIVERY';rt.output(h,a,tmp,key,'nativeeconomicv2',{'summary':summary,'private_economic_details':out},summary);relay(h,a,tmp,summary)
if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
