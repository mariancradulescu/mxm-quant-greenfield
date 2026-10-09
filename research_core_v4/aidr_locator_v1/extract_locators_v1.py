"""Default-deny locator extraction candidate. No response, return, PnL or cost calculation."""
import os,pathlib,tempfile,math,re,json
from research_core_v4.aidr_locator_v1 import discover_existing_v1 as d
from research_core_v4.diverse_mechanism_wave_v2 import authority_v2 as a,worker_v2 as w
from research_core_v4.numeric_development_v1.public_output_guard_v1 import validate_public_blob,ROOT as PUB
PREFIX='research_core_v4/aidr_locator_v1/'
ARM=PREFIX+'EXACT_EXTRACTION_PREARM_V1.json'
APPROVAL=PREFIX+'INDEPENDENT_EXTRACTION_ACCEPTANCE_V1.json'
WORKFLOW='.github/workflows/mxm-aidr-locator-extraction-v1.yml'
ENTRY=PREFIX+'extract_locators_v1.py'
MECHANISM='ACTIVITY_IMPACT_DECELERATION_REVERSAL'
STATUS=PUB+'AIDR_LOCATOR_EXTRACTION_V1.json'
SCOPE={'mechanism':MECHANISM,'lag_seconds':0,'start_utc':'2026-08-20T00:00:00Z','end_exclusive_utc':'2026-09-17T00:00:00Z','original_emitted':4205,'original_supported':3321,'original_label_gap':884,'source_rule':'ONLY_SHARD_GROUPS_AND_SEGMENTS_NEEDED_FOR_ORIGINAL_NONZERO_EMITTED_IDENTITY_WEEKS_PLUS_PREVIOUS_SEGMENT_FEATURE_PREFIX','maximum_input_shards':100,'attempts':1,'automatic_retries':0,'broker_requests':0,'returns_recomputed':False,'economic_selection':False,'protected_forward':False,'orders':False}
BUDGET={'wall_seconds':1800,'cpu_seconds':900,'ram_kib':2097152}

def gate():
    # This gate runs before key access or output/source ciphertext downloads.
    head=os.environ['GITHUB_SHA'];w.v2.runtime(head);a.ancestor(d.BASE,head)
    a.need(os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_WORKFLOW_REF')==w.old.REPO+'/'+WORKFLOW+'@refs/heads/'+w.old.BRANCH,'EXTRACTION_EVENT')
    a.need((a.ROOT/ARM).is_file() and (a.ROOT/APPROVAL).is_file(),'EXTRACTION_NOT_AUTHORIZED')
    arm=a.read(ARM);approval=a.read(APPROVAL)
    a.need((a.ROOT/ARM).read_bytes()==a.enc(arm),'EXTRACTION_ARM_BYTES')
    a.need(arm['schema']=='mxm.aidr.locator.extraction.prearm.v1' and arm['status']=='CANDIDATE_NOT_AUTHORIZED' and arm['scope']==SCOPE and arm['budget']==BUDGET,'EXTRACTION_ARM_SCOPE')
    a.need(arm['original_arm_sha256']==d.ARM_SHA and arm['original_completion_commit']==d.COMPLETION and arm['design_sha256']==a.DESIGN_SHA and arm['input_manifest_sha256']==w.n.MANIFEST_SHA,'EXTRACTION_ORIGINAL_BINDING')
    a.need(set(approval)=={'schema','status','role','arm_sha256','source_head','arm_commit','explicit_acceptance'},'EXTRACTION_APPROVAL_FIELDS')
    a.need(approval['schema']=='mxm.aidr.locator.extraction.acceptance.v1' and approval['status']=='AUTHORIZED_ONE_EXTRACTION' and approval['role']=='INDEPENDENT_AUDITOR' and approval['explicit_acceptance'] is True,'EXTRACTION_INDEPENDENT_AUTHORITY')
    a.need(approval['arm_sha256']==a.digest(ARM) and approval['source_head']==arm['source_head'],'EXTRACTION_APPROVAL_BINDING')
    a.ancestor(arm['source_head'],approval['arm_commit']);a.ancestor(approval['arm_commit'],head)
    a.need(a.sha(a.git('show',approval['arm_commit']+':'+ARM))==a.digest(ARM),'EXTRACTION_ARM_COMMIT')
    pc=a.git('log','-1','--format=%H',head,'--',APPROVAL).decode().strip()
    a.ancestor(approval['arm_commit'],pc)
    a.need(pc!=approval['arm_commit'] and a.git('diff-tree','--no-commit-id','--name-only','-r',pc).decode().splitlines()==[APPROVAL] and a.git('rev-list','--parents','-n','1',pc).decode().count(' ')==1,'EXTRACTION_APPROVAL_SEPARATION')
    original=a.real_gate(head)
    a.need(a.digest(a.ARM)==d.ARM_SHA and a.digest(a.APPROVAL)==d.APPROVAL_SHA,'EXTRACTION_ORIGINAL_AUTHORITY')
    a.need(set(original['bindings']).issubset(arm['bindings']) and {ENTRY,WORKFLOW,PREFIX+'discover_existing_v1.py'}.issubset(arm['bindings']),'EXTRACTION_BINDING_COMPLETENESS')
    for p,h in arm['bindings'].items():
        a.need(re.fullmatch('[0-9a-f]{64}',h) and a.digest(p)==h and a.sha(a.git('show',arm['source_head']+':'+p))==h,'EXTRACTION_SOURCE_DRIFT')
    from datetime import datetime,timezone
    a.need(datetime.now(timezone.utc)<=datetime.strptime(arm['expires_utc'],'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc),'EXTRACTION_EXPIRED')
    a.need(arm['invocation_id']==a.sha(a.enc({'purpose':'AIDR_LAG0_LOCATORS_ONLY','source_head':arm['source_head'],'scope':SCOPE,'completion':d.COMPLETION})),'EXTRACTION_INVOCATION')
    a.need(not w.v2.existing_ref('mxm-aidr-locator-extraction-claim-'+arm['invocation_id']),'EXTRACTION_CONSUMED')
    run=w.old.api('actions/runs/'+str(d.RUN))
    a.need(run['head_sha']==d.ORIGINAL and run['conclusion']=='success' and run['run_attempt']==1,'EXTRACTION_ORIGINAL_RUN')
    refs=w.v2.existing_ref(w.v2.claim_name(original))
    a.need(len(refs)==1 and refs[0]['object']['sha']==d.ORIGINAL,'EXTRACTION_ORIGINAL_CLAIM')
    refs=w.v2.existing_ref('mxm-numeric-v3-complete-real-'+original['invocation_id'])
    a.need(len(refs)==1 and refs[0]['object']['sha']==d.COMPLETION,'EXTRACTION_ORIGINAL_COMPLETION')
    master,entries,digits,manifest=w.old.verify_science();a.olda.preflight_inventory(manifest,entries)
    a.need(arm['discovery_evidence']['status_path']==d.STATUS,'EXTRACTION_DISCOVERY_PATH')
    proof=a.read(d.STATUS)
    a.need(proof['status']=='PASS' and proof['encrypted_artifact_sha256']==arm['discovery_evidence']['ciphertext_sha256'],'EXTRACTION_DISCOVERY_BINDING')
    return head,arm,original,master,entries,digits,manifest

def label_support(buffer,t):
    # Exact frozen support geometry; never call response() or take future-price ratios.
    if t+3600>w.n.END:return 'DOMAIN_CENSOR'
    timestamps=range(t-300,t+3600,300)
    if any(ts not in buffer for ts in timestamps):return 'LABEL_GAP'
    if any(not w.n.frozen.valid_bar(ts,buffer[ts],t+3600) for ts in timestamps):return 'LABEL_RECEIPT'
    return 'SUPPORTED'

def source_plan(report):
    # Only emitted counts, never gross signs, PnL, cost or winner rankings.
    active={};needed=set()
    for identity in report['identity_results']:
        weeks=[week['0'][MECHANISM]['emitted_before_maturity'] for week in identity['four_weeks']]
        targets=[i for i,n in enumerate(weeks) if n>0]
        if not targets:continue
        ordinal=identity['ordinal'];group=(ordinal-1)//64
        active[ordinal]=targets
        for week in targets:
            needed.add((week+1,group))
            if week>0:needed.add((week,group))
    return active,sorted(needed,key=lambda p:(p[1],p[0]))

def reconcile(events,report):
    seen=set();counts={}
    for event in events:
        key=(event['ordinal'],event['decision_timestamp'])
        a.need(key not in seen,'EXTRACTION_DUPLICATE');seen.add(key)
        a.need(event['direction'] in (-1,1) and event['response_support_status'] in ('SUPPORTED','LABEL_GAP','LABEL_RECEIPT','DOMAIN_CENSOR'),'EXTRACTION_EVENT_FIELDS')
        index=(event['decision_timestamp']-w.n.START)//3600
        a.need(0<=index<672 and event['decision_timestamp']==w.n.START+index*3600 and event['fixed_week']==index//168,'EXTRACTION_CLOCK')
        c=counts.setdefault((event['ordinal'],index//168),{'emitted':0,'SUPPORTED':0,'LABEL_GAP':0,'LABEL_RECEIPT':0,'DOMAIN_CENSOR':0})
        c['emitted']+=1;c[event['response_support_status']]+=1
    for identity in report['identity_results']:
        for week in range(4):
            expected=identity['four_weeks'][week]['0'][MECHANISM]
            c=counts.get((identity['ordinal'],week),{'emitted':0,'SUPPORTED':0,'LABEL_GAP':0,'LABEL_RECEIPT':0,'DOMAIN_CENSOR':0})
            a.need(c['emitted']==expected['emitted_before_maturity'] and c['SUPPORTED']==expected['supported'] and all(c[k]==expected['reasons'][k] for k in ('SUPPORTED','LABEL_GAP','LABEL_RECEIPT','DOMAIN_CENSOR')),'EXTRACTION_IDENTITY_WEEK_COUNTS')
    a.need(len(events)==4205 and sum(e['response_support_status']=='SUPPORTED' for e in events)==3321 and sum(e['response_support_status']=='LABEL_GAP' for e in events)==884,'EXTRACTION_GLOBAL_COUNTS')

def main():
    os.umask(0o077);head,arm,original,master,entries,digits,manifest=gate()
    # Separate one-use metadata-extraction claim; original invocation never touched.
    w.old.api('git/refs',{'ref':'refs/tags/mxm-aidr-locator-extraction-claim-'+arm['invocation_id'],'sha':head})
    w.install_identity_adapter()
    with tempfile.TemporaryDirectory(prefix='mxm-aidr-locators-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);tmp.chmod(0o700);key,fp=w.old._private_key_from_secret(tmp);a.need(fp==w.old.FP,'EXTRACTION_KEY')
        store=w.Store(head,key,a.ROOT/w.old.PUBLIC_KEY,tmp,original,d.APPROVAL_SHA,fp)
        store.original_run=d.RUN;store.name=w.v2.release_name(original,d.RUN);store.release=w.old.api('releases/408041914')
        a.need(store.release['target_commitish']==d.ORIGINAL,'EXTRACTION_RELEASE')
        completion=w.f.verify_complete(store);a.need(completion is not None,'EXTRACTION_ORIGINAL_COMPLETE_BYTES')
        journal,jmeta=store.load_named(w.f.JOURNAL);w.validate_journal(store,journal);report=journal['report']
        proofstore=w.Store(head,key,a.ROOT/w.old.PUBLIC_KEY,tmp,original,d.APPROVAL_SHA,fp)
        proofstore.release=w.old.api('releases/'+str(arm['discovery_evidence']['release_id']))
        proof,proofmeta=proofstore.load_named('existing-locator-discovery.mxmenc',arm['discovery_evidence']['ciphertext_sha256'])
        a.need(proof['reader_head']==arm['discovery_evidence']['source_head'],'EXTRACTION_DISCOVERY_SOURCE')
        a.need(proof['complete_locator_ledger_found'] is False and len(proof['inventory'])==len(d.EXPECTED) and all(x['possible_event_rows']==0 for x in proof['inventory']),'EXTRACTION_DISCOVERY_LOCATORS_FOUND')
        active,plan=source_plan(report)
        release=w.old.api('releases/tags/'+manifest['DURABLE_RELEASE_IDENTITY'])
        assets={x['name']:x for x in w.old.api('releases/'+str(release['id'])+'/assets?per_page=100')}
        events=[];provenance=[];group=None;buffers={}
        def collect(g):
            for ordinal,buffer in buffers.items():
                for week in active[ordinal]:
                    for index in range(week*168,(week+1)*168):
                        t=w.n.START+index*3600;directions,_=w.k.directions(buffer,t,0);direction,_=directions[MECHANISM]
                        if direction is None:continue
                        events.append({'ordinal':ordinal,'symbol_id':master[ordinal-1]['symbol_id'],'decision_timestamp':t,
                            'entry_reference_boundary':t,'exit_reference_boundary':t+3600,'direction':direction,
                            'fixed_week':week,'response_support_status':label_support(buffer,t),
                            'receipt_semantics':'ORIGINAL_CONDITIONAL_BAR_END_AVAILABILITY_NOT_AUTHENTIC_RECEIPTS'})
        for segment,g in plan:
            if group is not None and group!=g:collect(group);buffers={}
            group=g
            for ordinal in active:
                if (ordinal-1)//64==g:buffers.setdefault(ordinal,{})
            entry=entries[(segment-1)*25+g];asset=assets[entry['ENCRYPTED_ASSET_NAME']]
            a.need(asset['name']==entry['ENCRYPTED_ASSET_NAME'] and asset['digest']=='sha256:'+entry['ENCRYPTED_ASSET_SHA256'],'EXTRACTION_INPUT_METADATA')
            blob=w.old.download(asset['browser_download_url'],asset['size']);a.need(len(blob)==asset['size'] and a.sha(blob)==entry['ENCRYPTED_ASSET_SHA256'],'EXTRACTION_CIPHERTEXT')
            raw=w.old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp)
            a.need(a.sha(raw)==entry['PLAINTEXT_CANONICAL_SHA256'],'EXTRACTION_PLAINTEXT')
            obj=w.n.canonical.strict_json(raw);a.need(w.n.canonical.canonical(obj)==raw and set(obj)==w.n.canonical.PACKAGE_KEYS and obj['segment_index']==segment and obj['shard_index']==g and obj['identity_range']==entry['IDENTITY_RANGE'],'EXTRACTION_PACKAGE')
            lo,hi=entry['IDENTITY_RANGE'];a.need(len(obj['items'])==hi-lo+1 and sum(len(item['rows']) for item in obj['items'])==entry['ROW_COUNT'],'EXTRACTION_SOURCE_ROWS')
            for ordinal,item in zip(range(lo,hi+1),obj['items']):
                a.need(item['ordinal']==ordinal and item['symbol_id']==master[ordinal-1]['symbol_id'] and item['failure'] is None,'EXTRACTION_ITEM')
                if ordinal not in buffers:continue
                for row in item['rows']:
                    ts,bar=w.n._bar(row,digits[item['symbol_id']])
                    a.need((ts-w.n.START)//(7*86400)==segment-1 and ts not in buffers[ordinal],'EXTRACTION_ROW_ORDER_OR_SEGMENT')
                    # Retain only feature/label ranges for requested original weeks.
                    if any(w.n.START+week*7*86400-7200<=ts<w.n.START+(week+1)*7*86400 for week in active[ordinal]):
                        buffers[ordinal][ts]=bar
            provenance.append({'segment':segment,'shard':g,'ciphertext_sha256':entry['ENCRYPTED_ASSET_SHA256'],'plaintext_sha256':entry['PLAINTEXT_CANONICAL_SHA256']})
            w.old.budget(**{'maxwall':BUDGET['wall_seconds'],'maxcpu':BUDGET['cpu_seconds'],'maxkib':BUDGET['ram_kib']})
        if group is not None:collect(group)
        events.sort(key=lambda e:(e['ordinal'],e['decision_timestamp']));reconcile(events,report)
        a.need(w.f.verify_complete(store) is not None,'EXTRACTION_ORIGINAL_PRESERVED')
        document={'schema':'mxm.aidr.private.event.locators.v1','scope':SCOPE,'source_head':head,'prearm_sha256':a.digest(ARM),
            'original_completion':completion,'original_journal':jmeta,'input_source_provenance':provenance,'events':events,
            'all_original_identity_fixed_week_counts_reconciled':True,'returns_recomputed':False,'net_edge_claimed':False}
        out=w.old.GitHubStore(head,key,a.ROOT/w.old.PUBLIC_KEY,tmp,'real')
        status={'schema':w.SCHEMA,'source_head':head,'phase':'PUBLICATION','status':'PASS','failure_code':'NONE'}
        out.release=w.old.api('releases',{'tag_name':'mxm-aidr-locators-'+arm['invocation_id'][:12]+'-'+os.environ['GITHUB_RUN_ID'],'target_commitish':head,'name':'MXM encrypted AIDR event locators','prerelease':True,'body':validate_public_blob(STATUS,status).decode()})
        meta=out.encrypted(document,'aidr-event-locators.mxmenc')
        status.update(encrypted_artifact_name=meta['name'],encrypted_artifact_sha256=meta['ciphertext_sha256'])
        out.publish(status,STATUS);print(validate_public_blob(STATUS,status).decode().strip(),flush=True)

if __name__=='__main__':
    try:
        if os.sys.argv[1:]==['--preflight']:gate();print('PASS_EXACT_EXTRACTION_AUTHORITY')
        elif not os.sys.argv[1:]:main()
        else:raise RuntimeError()
    except Exception:
        print('FAIL_CLOSED_AIDR_LOCATOR_EXTRACTION',flush=True);raise SystemExit(2) from None
