"""One bounded fabricated Actions campaign, terminated worker and cold successor.

The reference is a deterministic in-memory calculation, not a second remote
invocation. Keys/engine/results stay private. Evidence itself is encrypted.
"""
import copy
import json
import os
import pathlib
import resource
import subprocess
import sys
import tempfile
import time
from research_core_v4.numeric_development_v2 import authority_v2 as a, machine_v2 as m
from research_core_v4.numeric_development_v1 import numeric_machine_entrypoint_v1 as old
from research_core_v4.numeric_development_v1 import numeric_streaming_executor_v1 as n

def worker(authority,kd,*extra):
    return [sys.executable,"-m","research_core_v4.numeric_development_v2.machine_v2",
      "--mode","synthetic","--fabricated-authority",str(authority),"--key-dir",str(kd),*extra]
def write(path,x):path.write_bytes(a.enc(x));path.chmod(0o600)
def main():
    os.umask(0o077);started=time.monotonic();head=os.environ["GITHUB_SHA"]
    m.runtime(head);master,entries,digits,manifest=old.verify_science()
    bindings=a.read(a.BINDINGS)["bindings"]
    arm=a.candidate(head,bindings);arm["mode"]="synthetic"
    approval={"schema":"mxm.numeric.independent.acceptance.v2","status":"INDEPENDENT_ACCEPTANCE_PASS",
      "mode":"synthetic","role":"FABRICATED_TEST_AUTHORITY","arm_sha256":a.sha(a.enc(arm)),
      "source_head":head,"arm_commit":head,"audit_receipt_sha256":a.sha(b"FABRICATED_ONLY_EXPLICIT_TEST_AUTHORITY"),
      "explicit_acceptance":True}
    a.validate(arm,approval,head,"synthetic",a.enc(arm),artifacts=False)
    with tempfile.TemporaryDirectory(prefix="mxm-cold-proof-",dir=os.environ.get("RUNNER_TEMP","/tmp")) as td:
        tmp=pathlib.Path(td);tmp.chmod(0o700);kd=tmp/"key";kd.mkdir(mode=0o700)
        # Standing access permits existing-key readiness. Payloads remain purely
        # fabricated; no authentic numeric ciphertext is downloaded or decrypted.
        key,fp=old._private_key_from_secret(kd)
        a.need(fp==old.FP,"EXISTING_KEY_CURRENT_FINGERPRINT")
        named=kd/"private.pem";key.rename(named);key=named
        public=kd/"public.pem";public.write_bytes((old.ROOT/old.PUBLIC_KEY).read_bytes());public.chmod(0o600)
        a.preflight_inventory(manifest,entries)
        print("PASS_CURRENT_EXISTING_KEY_AND_EXACT100_METADATA_NO_AUTHENTIC_NUMERIC_ROWS",flush=True)
        authfile=tmp/"fabricated-authority.json";write(authfile,{"arm":arm,"approval":approval})
        command=worker(authfile,kd,"--stop-after","50")
        before=resource.getrusage(resource.RUSAGE_CHILDREN)
        firststart=time.monotonic()
        first=subprocess.run(command,capture_output=True,text=True,timeout=1200)
        firstwall=time.monotonic()-firststart
        after=resource.getrusage(resource.RUSAGE_CHILDREN)
        firstcpu=(after.ru_utime+after.ru_stime)-(before.ru_utime+before.ru_stime)
        print(first.stdout,flush=True)
        a.need(first.returncode==75,"FIRST_PROCESS_DID_NOT_TERMINATE_AT_CHECKPOINT")
        pid1=json.loads(first.stdout.splitlines()[-1])["pid"]
        store=m.Store(head,key,public,tmp,arm,a.sha(a.enc(approval)),fp)
        store.release=old.api("releases/tags/"+store.name)
        checkpoint=json.loads(store.release["body"]);store.last=checkpoint
        a.need(checkpoint["status"]=="FAIL_CLOSED","INTERRUPTION_EVIDENCE_NOT_DURABLE")
        # Verify remote checkpoint authentically; no private state is passed to workers.
        receipt=store.decode_named(checkpoint);prefix=store.restore(receipt["checkpoint"])
        a.need(prefix["next_shard"]==50,"PREFIX_ORDINAL")
        prefix_resource=prefix["resources"];del prefix
        original=int(os.environ["GITHUB_RUN_ID"])
        recovery={"schema":"mxm.numeric.recovery.acceptance.v2","status":"AUTHORIZED_ONE_RECOVERY",
          "mode":"synthetic","role":"FABRICATED_TEST_AUTHORITY","arm_sha256":a.sha(a.enc(arm)),
          "approval_sha256":a.sha(a.enc(approval)),"invocation_id":arm["invocation_id"],
          "previous_run_id":original,"checkpoint_receipt_sha256":checkpoint["encrypted_artifact_sha256"],
          "next_shard":50,"attempts":1,"automatic_retries":0,"explicit_acceptance":True,
          "previous_resource_ceiling":{"wall_seconds":max(firstwall+5,prefix_resource["wall_seconds"]+5),
                                       "cpu_seconds":max(firstcpu+5,prefix_resource["cpu_seconds"]+5)}}
        recoveryfile=tmp/"fabricated-recovery.json";write(recoveryfile,recovery)
        cold=worker(authfile,kd,"--previous-run",str(original),"--recovery-authority",str(recoveryfile))
        # Concurrent equal attempts: atomic durable claim must elect exactly one.
        p1=subprocess.Popen(cold,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        p2=subprocess.Popen(cold,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        out1,err1=p1.communicate(timeout=1500);out2,err2=p2.communicate(timeout=1500)
        print(out1,flush=True);print(out2,flush=True)
        a.need(sorted([p1.returncode,p2.returncode])==[0,2],"CONCURRENT_RECOVERY_NOT_EXACTLY_ONE_WINNER")
        winner=out1 if p1.returncode==0 else out2
        loser=out2 if p1.returncode==0 else out1
        startline=next(json.loads(l) for l in winner.splitlines() if "cold_process_pid" in l)
        a.need(startline["cold_process_pid"]!=pid1 and startline["resume_next_shard"]==50 and
               startline["replay_completed_shards"] is False,"COLD_PROCESS_NOT_PROVED")
        endline=json.loads(winner.splitlines()[-1]);a.need(endline["processed_this_process"]==50,"DURABLE_PREFIX_REPLAYED")
        duplicate=subprocess.run(worker(authfile,kd),capture_output=True,text=True,timeout=120)
        a.need(duplicate.returncode==2 and "CONSUMED_ARM" in duplicate.stdout,"DUPLICATE_ORIGINAL_NOT_DENIED")
        repeat=subprocess.run(cold,capture_output=True,text=True,timeout=120)
        a.need(repeat.returncode==2,"DUPLICATE_COMPLETED_RECOVERY_NOT_DENIED")
        store.release=old.api("releases/tags/"+store.name)
        finalbody=json.loads(store.release["body"]);a.need(finalbody["status"]=="PASS","FINAL_RECEIPT_NOT_PERSISTED")
        finalreceipt=store.decode_named(finalbody)
        report=store.restore(finalreceipt["report"])
        states=[x for x in finalreceipt["assets"] if x["name"]=="complete-scientific-state.mxmenc"]
        a.need(len(states)==1,"FINAL_STATE_RECEIPT")
        recovered=store.restore(states[0])
        reference=n.new(master);expected_rows=0
        for idx in range(100):
            raw,meta=m.fabricated_shard(idx//25+1,idx%25,master,digits)
            expected_rows+=meta["ROW_COUNT"];n.consume_shard(reference,raw,meta,master,digits)
        reference_report=m.complete_report(reference,expected_rows,arm,report["source_bindings"]["processed_sources"])
        a.need(a.enc(reference)==a.enc(recovered),"COLD_SCIENTIFIC_STATE_PARITY")
        a.need(a.enc(reference_report)==a.enc(report),"COLD_COMPLETE_REPORT_PARITY")
        # Initial and final identities/bindings/denominators/reasons/all outputs match
        # byte for byte; only bools and operational measurements may be public.
        evidence={"schema":"mxm.numeric.cold.process.proof.private.v2","fabricated_only":True,
          "source_head":head,"bindings":bindings,"arm":arm,"approval":approval,"recovery":recovery,
          "first_process":{"pid":pid1,"exit":first.returncode,"stdout":first.stdout},
          "cold_process":{"pid":startline["cold_process_pid"],"exit":0,"stdout":winner},
          "concurrent_loser":{"exit":2,"stdout":loser},"duplicate_original_exit":duplicate.returncode,
          "duplicate_completed_recovery_exit":repeat.returncode,"checkpoint_receipt":checkpoint,
          "interruption_preserved":True,"report_reference_exact_bytes_equal":True,
          "scientific_state_reference_exact_bytes_equal":True,"no_completed_shard_replay":True,
          "expected_rows":expected_rows,"identities":1576,"lags_seconds":[0,300,900],
          "existing_key_current_fingerprint":"PASS","accepted100_metadata_preflight":"PASS",
          "final_encrypted_receipt":finalreceipt,"resources":old.usage(),
          "local_environment_test_setup_failure":{"errors":4,"reason":"missing_GITHUB_RUN_ID_in_local_test_environment",
            "fixed_without_scientific_source_changes":True},"old_full_synthetic_replayed":False}
        proof=store.encrypted(evidence,"cross-process-proof.mxmenc")
        old.budget()
        usage=old.usage()
        public=m.safe_status(head,"SYNTHETIC","PASS",run_id=original,
          encrypted_artifact_name=proof["name"],encrypted_artifact_sha256=proof["ciphertext_sha256"],
          resource_cpu_seconds=usage["cpu_seconds"],resource_wall_seconds=time.monotonic()-started,
          resource_peak_ram_kib=usage["peak_kib"],failure_code="NONE")
        publication=store.publish(public,m.PROOF_STATUS)
        print(json.dumps({"status":"PASS_TRUE_COLD_PROCESS_REFERENCE_AND_REMOTE_READBACK",
          "source_head":head,"published_head":publication["head"],"public_sha256":publication["public_sha256"],
          "proof_ciphertext_sha256":proof["ciphertext_sha256"],"first_exit":75,"cold_exit":0,
          "concurrent_loser_exit":2,"distinct_processes":True,"resumed_from_shard":50,
          "completed_shard_replay":False,"fabricated_rows":expected_rows,"resources":old.usage(),
          "old_full_synthetic_replayed":False}),flush=True)

if __name__=="__main__":
    try:main()
    except Exception as e:
        code=str(e.args[0]) if isinstance(e,n.NumericalStop) and e.args else "FAIL_CLOSED"
        print(json.dumps({"status":"FAIL_CLOSED","code":code,"resources":old.usage()}),flush=True)
        raise SystemExit(2) from None
