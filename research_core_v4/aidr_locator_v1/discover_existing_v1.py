"""Inspect completed encrypted outputs only. Never open original input shards."""
import argparse,json,os,pathlib,tempfile
from research_core_v4.diverse_mechanism_wave_v2 import authority_v2 as a,worker_v2 as w
from research_core_v4.numeric_development_v1.public_output_guard_v1 import validate_public_blob,ROOT as PUB
RUN=37950879700
ORIGINAL='793f198a24262d4b9ceb5b2820bb30e99619b34f'
BASE='0e63328b372f6af0c5fc25607498fd308b103a81'
COMPLETION='ffee8b68bedc0a0556b818aa11e47b644dc5ec2c'
ARM_SHA='9c91c7263bce5e7afd73616c56f10c437bb6d81e71a701b926489595863a238a'
APPROVAL_SHA='64bfb9c96f81250e251d2c944317429cae4882c38534abd5908fa9cfb34f2af5'
WORKFLOW='.github/workflows/mxm-aidr-existing-locator-discovery-v1.yml'
PATH='research_core_v4/aidr_locator_v1/discover_existing_v1.py'
STATUS=PUB+'AIDR_EXISTING_LOCATOR_DISCOVERY_V1.json'
EXPECTED=[{"name":"authentic-diverse-wave-readback.mxmenc","id":625362543,"size":6856,"digest":"sha256:d9e6a17e700804b34d91a46563fbd7dd5dbab43fdd8fd9a7e4223aff4170bc94"},{"name":"complete-development-result.mxmenc","id":625353029,"size":1588879,"digest":"sha256:7487d0efd880d56b48ee59299d06edc16d337493f46ca580dbbf5502e9d18e7d"},{"name":"complete-final-receipt.mxmenc","id":625353405,"size":2555,"digest":"sha256:1b1050b2acccfd27cfb097fda28ca78026f07787533f28447bab17350f5d1a4f"},{"name":"complete-scientific-state.mxmenc","id":625353244,"size":982807,"digest":"sha256:7df42f8e4e4d528030bb3203568f9c555a9aa841575300c808ab8dbe60a5a3a4"},{"name":"finalization-input.mxmenc","id":625352425,"size":2578577,"digest":"sha256:e1d5c88c23c9808d2252eddd4a0d5b26ffe98890f3e000e7741a462cef4613b9"},{"name":"prefix-025.mxmenc","id":625343882,"size":503886,"digest":"sha256:4753a71503eff5d5c3f02e8a1e46db1d6617affc00b4e62c7023174eb53ae45b"},{"name":"prefix-050.mxmenc","id":625346390,"size":776464,"digest":"sha256:fadd83d3315769f4a88f5d8d2a5724d637daf5606653576ceba07808a081fb37"},{"name":"prefix-075.mxmenc","id":625349269,"size":918493,"digest":"sha256:c3a4757a6b3332d4215f13dc86e661918255205762b2253201c84adad3e43836"},{"name":"prefix-100.mxmenc","id":625351876,"size":1059178,"digest":"sha256:d00d3dd0e58c1af80dc3284681aa280f86504128bd11ee966d921f6b51db2abd"},{"name":"receipt-025.mxmenc","id":625344014,"size":978,"digest":"sha256:85b74fafa7c8e7718e584eb491555d26d3e393335231dc6e45910a02758c3c00"},{"name":"receipt-050.mxmenc","id":625346497,"size":977,"digest":"sha256:bb15cd191cff0fec3e0eebe70071569ba06f23919da3f42d586373f770888197"},{"name":"receipt-075.mxmenc","id":625349401,"size":979,"digest":"sha256:96a8c9d14d2a0925e35ae0c782a7aea978ff23e117b4e49dd7685d02ddc0b059"},{"name":"receipt-100.mxmenc","id":625352007,"size":980,"digest":"sha256:fcb57b49e449a33b37f39fc65cdec91726730dbdf4dfdf5eddfbaced9d784d0d"},{"name":"verified-delivery-attestation.mxmenc","id":625353697,"size":1350,"digest":"sha256:4b24949e5b24c453f79acb0ab509249bd743100e5faec87660d3401be91784e0"}]

def preflight():
    head=os.environ['GITHUB_SHA'];w.v2.runtime(head);a.ancestor(BASE,head)
    a.need(os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_WORKFLOW_REF')==w.old.REPO+'/'+WORKFLOW+'@refs/heads/'+w.old.BRANCH,'DISCOVERY_EVENT')
    arm=a.real_gate(head)
    a.need(a.digest(a.ARM)==ARM_SHA and a.digest(a.APPROVAL)==APPROVAL_SHA,'DISCOVERY_ORIGINAL_AUTHORITY')
    run=w.old.api('actions/runs/'+str(RUN))
    a.need(run['head_sha']==ORIGINAL and run['conclusion']=='success' and run['run_attempt']==1,'DISCOVERY_ORIGINAL_RUN')
    refs=w.v2.existing_ref(w.v2.claim_name(arm));a.need(len(refs)==1 and refs[0]['object']['sha']==ORIGINAL,'DISCOVERY_ORIGINAL_CLAIM')
    refs=w.v2.existing_ref('mxm-numeric-v3-complete-real-'+arm['invocation_id'])
    a.need(len(refs)==1 and refs[0]['object']['sha']==COMPLETION,'DISCOVERY_COMPLETION')
    a.ancestor(COMPLETION,head)
    rel=w.old.api('releases/408041914')
    a.need(rel['target_commitish']==ORIGINAL and rel['tag_name']==w.v2.release_name(arm,RUN),'DISCOVERY_RELEASE')
    got=[{k:x[k] for k in ('name','id','size','digest')} for x in w.old.api('releases/408041914/assets?per_page=100')]
    a.need(sorted(got,key=lambda x:x['name'])==sorted(EXPECTED,key=lambda x:x['name']),'DISCOVERY_INVENTORY_DRIFT')
    return head,arm,rel

def inspect(value):
    """Record shapes only; a bar timestamp alone is never an event locator."""
    shapes=set();candidate_rows=0;stack=[value]
    while stack:
        x=stack.pop()
        if isinstance(x,dict):
            keys=set(x)
            # Avoid collecting dynamic timestamp, symbol or ordinal key names.
            shapes.add(tuple(sorted(k for k in keys if not k.isdigit())))
            identity=bool(keys & {'symbol_id','SYMBOL_ID','ordinal','identity'})
            clock=bool(keys & {'t','timestamp','decision_timestamp','decision_utc','entry_timestamp','entry_utc'})
            direction=bool(keys & {'direction','signal_direction','d','side'})
            support=bool(keys & {'support','response_support','reason','maturity_support','support_status'})
            if identity and clock and direction and support:candidate_rows+=1
            stack.extend(x.values())
        elif isinstance(x,list):stack.extend(x)
    return {'object_shapes':[list(s) for s in sorted(shapes)],'possible_event_rows':candidate_rows}

def main():
    os.umask(0o077);head,arm,rel=preflight();w.install_identity_adapter()
    with tempfile.TemporaryDirectory(prefix='mxm-existing-locators-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);tmp.chmod(0o700);key,fp=w.old._private_key_from_secret(tmp)
        a.need(fp==w.old.FP,'DISCOVERY_KEY')
        store=w.Store(head,key,a.ROOT/w.old.PUBLIC_KEY,tmp,arm,APPROVAL_SHA,fp)
        store.original_run=RUN;store.name=rel['tag_name'];store.release=rel
        # Restrict every ciphertext GET to the exact completed-output inventory.
        original_download=w.old.download
        urls={x['browser_download_url']:x['size'] for x in w.old.api('releases/408041914/assets?per_page=100')}
        def output_download(url,size):
            a.need(url in urls and size==urls[url],'DISCOVERY_INPUT_DOWNLOAD_DENIED')
            return original_download(url,size)
        w.old.download=output_download
        completion=w.f.verify_complete(store);a.need(completion is not None,'DISCOVERY_COMPLETE_BYTES')
        journal,jmeta=store.load_named(w.f.JOURNAL);w.validate_journal(store,journal)
        r=journal['report'];mech='ACTIVITY_IMPACT_DECELERATION_REVERSAL';summary=r['full_frontier']['0'][mech]
        a.need(summary['emitted_before_maturity']==4205 and summary['supported']==3321 and summary['reasons']['LABEL_GAP']==884,'DISCOVERY_ORIGINAL_POPULATIONS')
        a.need(all(summary['reasons'][k]==0 for k in ('LABEL_RECEIPT','DOMAIN_CENSOR')),'DISCOVERY_UNSUPPORTED_REASONS')
        inventory=[]
        for expected in EXPECTED:
            value,meta=store.load_named(expected['name'],expected['digest'][7:])
            shape=inspect(value)
            inventory.append({'ciphertext':meta,'schema':value.get('schema') if isinstance(value,dict) else None,**shape})
            w.old.budget(maxwall=500,maxcpu=500,maxkib=1048576)
        found=any(x['possible_event_rows'] for x in inventory)
        report={'schema':'mxm.aidr.existing.locator.discovery.v1','reader_head':head,'original_completion':completion,
            'original_journal':jmeta,'inventory':inventory,'complete_locator_ledger_found':found,
            'original_counts':{'emitted':4205,'supported':3321,'label_gap':884},
            'original_fixed_weeks':[week['0'][mech] if '0' in week else week[mech] for week in r['four_weeks']['0']],
            'no_input_shards_opened':True,'kernel_calls':0,'broker_requests':0,
            'match_count':'NOT_IDENTIFIABLE_WITHOUT_COMPLETE_LOCATORS',
            'result':'CANDIDATE_RECORDS_REQUIRE_REVIEW' if found else 'COMPLETE_LOCATORS_ABSENT_IN_ALL_ORIGINAL_OUTPUT_ASSETS'}
        # Original release is read-only. New evidence uses a separate release.
        a.need(w.f.verify_complete(store) is not None,'DISCOVERY_ORIGINAL_PRESERVED')
        w.old.download=original_download
        out=w.old.GitHubStore(head,key,a.ROOT/w.old.PUBLIC_KEY,tmp,'real')
        tag='mxm-aidr-locator-discovery-'+head[:12]+'-'+os.environ['GITHUB_RUN_ID']
        status={'schema':w.SCHEMA,'source_head':head,'phase':'PUBLICATION','status':'PASS','failure_code':'NONE'}
        body=validate_public_blob(STATUS,status).decode()
        out.release=w.old.api('releases',{'tag_name':tag,'target_commitish':head,'name':'MXM encrypted existing locator discovery','prerelease':True,'body':body})
        meta=out.encrypted(report,'existing-locator-discovery.mxmenc')
        status.update(encrypted_artifact_name=meta['name'],encrypted_artifact_sha256=meta['ciphertext_sha256'])
        # This existing guard is applied to every actual public Git blob.
        out.publish(status,STATUS)
        preflight_original=w.old.api('releases/408041914/assets?per_page=100')
        a.need(sorted([{k:x[k] for k in ('name','id','size','digest')} for x in preflight_original],key=lambda x:x['name'])==sorted(EXPECTED,key=lambda x:x['name']),'DISCOVERY_ORIGINAL_MUTATED')
        print(validate_public_blob(STATUS,status).decode().strip(),flush=True)
        print('EXISTING_LOCATOR_CANDIDATES_REQUIRE_REVIEW' if found else 'COMPLETE_EVENT_LOCATORS_ABSENT_IN_AUTHENTICATED_ORIGINAL_OUTPUTS',flush=True)

if __name__=='__main__':
    try:
        if os.sys.argv[1:]==['--preflight']:preflight();print('PASS_OUTPUT_ONLY_PREFLIGHT')
        elif not os.sys.argv[1:]:main()
        else:raise RuntimeError()
    except Exception:
        print('FAIL_CLOSED_EXISTING_OUTPUT_DISCOVERY',flush=True)
        raise SystemExit(2) from None
