"""One bounded fabricated campaign; original crypto and atomicity code is reused."""
import json,os,pathlib,resource,subprocess,sys,tempfile,time
from research_core_v4.diverse_mechanism_wave_v2 import authority_v2 as a,worker_v2 as w
from research_core_v4.diverse_mechanism_wave_v1.synthetic_v1 import fabricated_shard

def command(kd,*extra):return [sys.executable,'-m','research_core_v4.diverse_mechanism_wave_v2.worker_v2','--mode','synthetic','--key-dir',str(kd),*extra]
def parsed(output,field):return next(json.loads(x) for x in output.splitlines() if x.startswith('{') and field in json.loads(x))
def must_failure(kd,*args):
    p=subprocess.run(command(kd,*args),capture_output=True,text=True,timeout=180)
    a.need(p.returncode==2,'MANDATORY_FAILURE_MUST_EXIT_NONZERO');return p

def main():
    os.umask(0o077);head=os.environ['GITHUB_SHA'];w.v2.runtime(head);a.unavailable_acceptance_preflight()
    source=a.git('log','-1','--format=%H',head,'--',a.BINDINGS).decode().strip()
    arm=a.candidate(source,a.read(a.BINDINGS)['bindings'],'synthetic');a.validate_candidate(head,arm,'synthetic')
    launch=a.read(a.PREFIX+'SYNTHETIC_LAUNCH_V2.json')
    a.need(launch=={'schema':'mxm.diverse.wave.synthetic.launch.v2','mode':'FABRICATED_ONLY','source_head':source,'design_sha256':a.DESIGN_SHA,'binding_manifest_sha256':a.digest(a.BINDINGS),'fixture_packages':2,'family_comparisons':6,'attempts':1,'real_authorized':False},'SYNTHETIC_LAUNCH_DRIFT')
    tag='mxm-diverse-wave-v2-synthetic-launch-'+source
    a.need(not w.v2.existing_ref(tag),'SYNTHETIC_CAMPAIGN_ALREADY_CLAIMED')
    w.old.api('git/refs',{'ref':'refs/tags/'+tag,'sha':head})
    tests=subprocess.run([sys.executable,'-m','unittest','research_core_v4.diverse_mechanism_wave_v2.test_operational_v2','-v'],capture_output=True,text=True,timeout=300)
    print(tests.stdout,flush=True);print(tests.stderr,flush=True);a.need(tests.returncode==0,'MANDATORY_TARGETED_TEST_FAILURE')
    master,entries,digits,_=w.old.verify_science();original=int(os.environ['GITHUB_RUN_ID'])
    approval_sha=a.sha(a.enc({'mode':'fabricated-only','design':a.DESIGN_SHA,'run':os.environ['GITHUB_RUN_ID']}))
    w.install_identity_adapter()
    with tempfile.TemporaryDirectory(prefix='mxm-wave-v2-proof-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);kd=tmp/'key';kd.mkdir(mode=0o700)
        key,fp=w.old._private_key_from_secret(kd);a.need(fp==w.old.FP,'WAVE_KEY_FINGERPRINT');key.rename(kd/'private.pem');key=kd/'private.pem'
        public=kd/'public.pem';public.write_bytes((a.ROOT/w.old.PUBLIC_KEY).read_bytes());public.chmod(0o600)
        before=resource.getrusage(resource.RUSAGE_CHILDREN);ts=time.monotonic()
        first=subprocess.run(command(kd,'--stop-after','1'),capture_output=True,text=True,timeout=600)
        after=resource.getrusage(resource.RUSAGE_CHILDREN);firstwall=time.monotonic()-ts;firstcpu=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime
        print(first.stdout,flush=True);a.need(first.returncode==75,'ACTUAL_PROCESS_NOT_TERMINATED')
        pid1=parsed(first.stdout,'pid')['pid']
        store=w.Store(head,key,public,tmp,arm,approval_sha,fp);store.release=w.old.api('releases/tags/'+store.name)
        body=json.loads(store.release['body']);a.need(body['status']=='FAIL_CLOSED','DURABLE_PREFIX_NOT_TERMINATED')
        receipt=store.decode_named(body);prefix=store.restore(receipt['checkpoint']);w.verify_processed(prefix,'synthetic',master,digits,entries);a.need(prefix['next_shard']==1,'DURABLE_PREFIX_DRIFT')
        auth={'schema':'mxm.numeric.recovery.acceptance.v2','status':'AUTHORIZED_ONE_RECOVERY','mode':'synthetic','role':'FABRICATED_TEST_AUTHORITY','arm_sha256':a.sha(a.enc(arm)),'approval_sha256':approval_sha,'invocation_id':arm['invocation_id'],'previous_run_id':original,'checkpoint_receipt_sha256':body['encrypted_artifact_sha256'],'next_shard':1,'attempts':1,'automatic_retries':0,'explicit_acceptance':True,'previous_resource_ceiling':{'wall_seconds':max(firstwall+5,prefix['resources']['wall_seconds']+5),'cpu_seconds':max(firstcpu+5,prefix['resources']['cpu_seconds']+5)}}
        del prefix
        authpath=tmp/'fabricated-recovery.json';authpath.write_bytes(a.enc(auth));authpath.chmod(0o600)
        cold=command(kd,'--previous-run',str(original),'--recovery-authority',str(authpath))
        # Two contenders share only immutable authority and an ephemeral test key.
        one=subprocess.Popen(cold,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);two=subprocess.Popen(cold,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        out1,err1=one.communicate(timeout=900);out2,err2=two.communicate(timeout=900)
        print(out1,flush=True);print(out2,flush=True)
        a.need(sorted([one.returncode,two.returncode])==[0,2],'CONCURRENT_RECOVERY_NOT_ONE_WINNER')
        winner=out1 if one.returncode==0 else out2;loser=out2 if one.returncode==0 else out1
        resumed=parsed(winner,'cold_process_pid');done=parsed(winner,'processed_this_process')
        a.need(resumed['cold_process_pid']!=pid1 and resumed['resume_next_shard']==1 and resumed['replay_completed_shards'] is False and done['processed_this_process']==1 and done['resumed_from_shard']==1,'COLD_PROCESS_REPLAY_OR_IDENTITY')
        duplicate=must_failure(kd);repeat=must_failure(kd,'--previous-run',str(original),'--recovery-authority',str(authpath))
        verified=w.f.verify_complete(store);a.need(verified is not None,'MISSING_AUTHENTICATED_COMPLETION_REF')
        recovered,_=store.load_named(w.f.STATE);report,_=store.load_named(w.f.REPORT)
        reference=w.new(master)
        for idx,record in enumerate(report['source_bindings']['processed_sources']):
            raw,meta=fabricated_shard(idx,master,digits)
            # Source identities are verified separately; no encrypted scientific replay.
            fake=b'fabricated-reference';meta['ENCRYPTED_ASSET_SHA256']=a.sha(fake);w.consume(reference,raw,meta,master,digits,fake)
        reference_report=w.report(reference,reference['rows'],2,report['source_bindings']['processed_sources'],arm)
        a.need(a.enc(reference)==a.enc(recovered),'COLD_COMPLETE_SCIENTIFIC_BYTES_MISMATCH')
        a.need(a.enc(reference_report)==a.enc(report),'COLD_COMPLETE_REPORT_BYTES_MISMATCH')
        proof=store.encrypted({'schema':'mxm.diverse.wave.private.integration.proof.v2','fabricated_only':True,'source_head':source,'arm':arm,'recovery_acceptance':auth,'first_exit':75,'first_pid':pid1,'cold_pid':resumed['cold_process_pid'],'concurrent_loser_exit':2,'duplicate_original_exit':duplicate.returncode,'duplicate_recovery_exit':repeat.returncode,'reference_state_byte_equal':True,'reference_report_byte_equal':True,'diagnostics_included':True,'replay_completed_shards':False,'prefix_next_shard':1,'processed_this_process':1,'worker_sha256':a.digest(a.WORKER),'kernel_sha256':a.digest(a.KERNEL),'completion':verified,'resources':w.old.usage(),'tests_stdout':tests.stdout,'tests_stderr':tests.stderr,'worker_winner_stdout':winner,'worker_loser_stdout':loser},'targeted-operational-proof.mxmenc')
        w.old.budget();usage=w.old.usage()
        status=w.safe_status(head,'SYNTHETIC','PASS',run_id=original,encrypted_artifact_name=proof['name'],encrypted_artifact_sha256=proof['ciphertext_sha256'],resource_cpu_seconds=usage['cpu_seconds'],resource_wall_seconds=usage['wall_seconds'],resource_peak_ram_kib=usage['peak_kib'],failure_code='NONE')
        publication=store.publish_exact(status,w.PUB+'DIVERSE_WAVE_V2_INTEGRATION_PROOF_V1.json')
        print(json.dumps({'status':'PASS_TARGETED_OPERATIONAL_INTEGRATION_AND_TRUE_COLD_PROCESS','source_head':source,'launch_head':head,'published_head':publication['head'],'completion_ref':verified['completion_ref'],'completion_commit':verified['completion_commit'],'release_tag':store.name,'first_exit':75,'cold_exit':0,'concurrent_loser_exit':2,'distinct_processes':True,'reference_state_byte_equal':True,'reference_report_byte_equal':True,'resumed_from_shard':1,'processed_this_process':1,'completed_shard_replay':False,'worker_sha256':a.digest(a.WORKER),'kernel_sha256':a.digest(a.KERNEL),'resources':w.old.usage(),'historical_numeric_downloads':0,'real_execution_authorized':False}),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps({'status':'FAIL_CLOSED','code':str(e.args[0]) if isinstance(e,w.n.NumericalStop) and e.args else 'INTEGRITY_FAILURE','resources':w.old.usage()}),flush=True);raise SystemExit(2) from None
