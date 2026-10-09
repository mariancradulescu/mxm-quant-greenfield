"""Operational V3: unchanged V2 reducer, crash-consistent V3 final delivery."""
import argparse
import json
import os
import pathlib
import subprocess
import tempfile
from research_core_v4.numeric_development_v1 import numeric_machine_entrypoint_v1 as old
from research_core_v4.numeric_development_v1 import numeric_streaming_executor_v1 as n
from research_core_v4.numeric_development_v2.machine_v2 import runtime, existing_ref, claim_name, fabricated_shard, source_record, verify_processed, complete_report
from research_core_v4.numeric_development_v3 import authority_v3 as a
from research_core_v4.numeric_development_v3.finalization_v3 import Store, finish
ROOT=old.ROOT

def run(args):
    os.umask(0o077);head=os.environ["GITHUB_SHA"];runtime(head)
    mode=args.mode
    master,entries,digits,manifest=old.verify_science()
    if mode=="real":
        a.real_event_gate()
        a.need(args.fabricated_authority is None and args.key_dir is None and args.stop_after is None,
               "REAL_TEST_SWITCH_DENIED")
        arm=a.real_gate(head);approval_sha=a.digest(a.APPROVAL)
        # Avoidable inventory checks happen BEFORE key opening and invocation claim.
        assets=a.preflight_inventory(manifest,entries)
        if args.previous_run is not None:a.stopped_original_preflight(arm,args.previous_run)
    else:
        a.need(args.fabricated_authority is not None,"FABRICATED_AUTHORITY_REQUIRED")
        f=json.loads(pathlib.Path(args.fabricated_authority).read_text())
        arm=f["arm"];approval=f["approval"]
        a.validate(arm,approval,head,"synthetic",a.enc(arm),artifacts=False)
        approval_sha=a.sha(a.enc(approval));assets={}
    if args.previous_run is None:
        a.need(not existing_ref(claim_name(arm)),"CONSUMED_ARM")
    with tempfile.TemporaryDirectory(prefix="mxm-v2-",dir=os.environ.get("RUNNER_TEMP","/tmp")) as td:
        tmp=pathlib.Path(td);tmp.chmod(0o700)
        if mode=="real":
            a.need(bool(os.environ.get("MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM")),"EXISTING_KEY_ABSENT")
            key,fp=old._private_key_from_secret(tmp);public=ROOT/old.PUBLIC_KEY
            a.need(fp==old.FP,"PRIVATE_KEY_FINGERPRINT")
        else:
            kd=pathlib.Path(args.key_dir);a.need(kd.stat().st_mode&0o077==0,"FABRICATED_KEY_MODE")
            key=kd/"private.pem";public=kd/"public.pem"
            a.need(key.stat().st_mode&0o077==0,"FABRICATED_PRIVATE_MODE")
            der=subprocess.check_output(["openssl","pkey","-pubin","-in",str(public),"-outform","DER"],stderr=subprocess.DEVNULL)
            fp=a.sha(der)
        store=Store(head,key,public,tmp,arm,approval_sha,fp)
        engine=None;processed=[];rows=0;prior={"cpu_seconds":0,"wall_seconds":0}
        if args.previous_run is None:
            store.claim();engine=n.new(master)
        else:
            if mode=="real":
                a.need(args.recovery_authority is None and (ROOT/a.RECOVERY).is_file(),"RECOVERY_AUTHORITY_REQUIRED")
                auth=a.read(a.RECOVERY)
                rc=a.git("log","-1","--format=%H",head,"--",a.RECOVERY).decode().strip()
                a.need(a.git("diff-tree","--no-commit-id","--name-only","-r",rc).decode().splitlines()==[a.RECOVERY],
                       "RECOVERY_APPROVAL_SEPARATION")
            else:auth=json.loads(pathlib.Path(args.recovery_authority).read_text())
            original=old.api("releases/tags/"+__import__("research_core_v4.numeric_development_v2.machine_v2",fromlist=["release_name"]).release_name(arm,args.previous_run))
            if json.loads(original["body"])["phase"]=="FINAL":
                journal=store.finalization_recovery(auth,args.previous_run)
                result=finish(store,journal)
                print(json.dumps({**result,"processed_this_process":0,"resources":old.usage()}),flush=True)
                return
            prefix=store.recovery(auth,args.previous_run)
            verify_processed(prefix,mode,master,digits,entries)
            engine=prefix["engine"];rows=prefix["expected_rows"];processed=prefix["processed_sources"]
            prior=auth["previous_resource_ceiling"];store.prior=prior
            print(json.dumps({"cold_process_pid":os.getpid(),"resume_next_shard":engine["next_shard"],
               "remote_prefix_sha256":a.sha(a.enc(prefix)),"replay_completed_shards":False}),flush=True)
        start=engine["next_shard"]
        try:
            for idx in range(start,100):
                old.budget(maxwall=a.BUDGET["wall_seconds"]-prior["wall_seconds"],
                           maxcpu=a.BUDGET["cpu_seconds"]-prior["cpu_seconds"])
                seg=idx//25+1;k=idx%25
                if mode=="synthetic":
                    raw,meta=fabricated_shard(seg,k,master,digits)
                    file=tmp/"fabricated-input.mxmenc"
                    old.encrypt_shard(raw,public_key=public,output=file)
                    blob=file.read_bytes();meta["ENCRYPTED_ASSET_SHA256"]=a.sha(blob)
                    raw=old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp)
                    file.unlink()
                else:
                    meta=entries[idx];asset=assets[meta["ENCRYPTED_ASSET_NAME"]]
                    blob=old.download(asset["browser_download_url"],asset["size"])
                    a.need(len(blob)==asset["size"] and a.sha(blob)==meta["ENCRYPTED_ASSET_SHA256"],"INPUT_CIPHERTEXT_DRIFT")
                    raw=old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp)
                n.consume_shard(engine,raw,meta,master,digits,ciphertext=blob)
                rows+=meta["ROW_COUNT"];processed.append(source_record(idx,meta));del raw,blob
                if k==24:
                    mark=store.checkpoint(engine,rows,processed)
                    print(json.dumps({"pid":os.getpid(),"next_shard":engine["next_shard"],
                      "encrypted_checkpoint_readback":"PASS","ciphertext_sha256":mark["ciphertext_sha256"]}),flush=True)
                    if args.stop_after==engine["next_shard"]:
                        # Genuine process death: no inline restore or finally-based handoff.
                        store.body({**store.last,"status":"FAIL_CLOSED","failure_code":"UNSUPPORTED"})
                        print(json.dumps({"status":"PLANNED_FABRICATED_PROCESS_TERMINATION","exit":75,
                          "pid":os.getpid(),"durable_next_shard":engine["next_shard"]}),flush=True)
                        os._exit(75)
            if mode=="real":a.need(rows==n.EXPECTED_ROWS,"HISTORICAL_ROW_COUNT_DRIFT")
            report=complete_report(engine,rows,arm,processed)
            journal=store.prepare(report,engine,start)
            old.budget(maxwall=a.BUDGET["wall_seconds"]-prior["wall_seconds"],
                       maxcpu=a.BUDGET["cpu_seconds"]-prior["cpu_seconds"])
            result=finish(store,journal)
            print(json.dumps({**result,"pid":os.getpid(),"resumed_from_shard":start,
              "processed_this_process":100-start,"resources":old.usage()}),flush=True)
        except Exception:
            if store.last and store.last["phase"]!="FINAL":
                try:store.body({**store.last,"status":"FAIL_CLOSED","failure_code":"INTEGRITY_FAILURE"})
                except Exception:pass
            raise

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=("real","synthetic"),required=True)
    parser.add_argument("--fabricated-authority")
    parser.add_argument("--key-dir")
    parser.add_argument("--stop-after",type=int,choices=(25,50,75))
    parser.add_argument("--previous-run",type=int)
    parser.add_argument("--recovery-authority")
    args=parser.parse_args()
    try:run(args)
    except Exception as e:
        code=str(e.args[0]) if isinstance(e,n.NumericalStop) and e.args else "FAIL_CLOSED"
        print(json.dumps({"status":"FAIL_CLOSED","code":code,"resources":old.usage()}),flush=True)
        raise SystemExit(2) from None

if __name__=="__main__":main()
