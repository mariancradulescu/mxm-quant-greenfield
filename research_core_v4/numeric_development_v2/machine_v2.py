"""Exact operational successor; real mode is denied without independent artifacts.

No private results or checkpoints are written to Git. All release bodies and
public Git blobs pass the existing V1 allowlist at the actual API callsites.
The cold worker has no local-state input and fetches its state only remotely.
"""
import argparse
import copy
import json
import os
import pathlib
import subprocess
import tempfile
from research_core_v4.numeric_development_v1 import numeric_machine_entrypoint_v1 as old
from research_core_v4.numeric_development_v1 import numeric_streaming_executor_v1 as n
from research_core_v4.numeric_development_v1.public_output_guard_v1 import validate_public_blob, SCHEMA, ROOT as PUB
from research_core_v4.numeric_development_v2 import authority_v2 as a

ROOT=old.ROOT
ENTRY="research_core_v4/numeric_development_v2/machine_v2.py"
PROOF_STATUS=PUB+"SYNTHETIC_SUCCESSOR_INTEGRATION_RESULT_V1.json"
CHECK_STATUS=PUB+"CROSS_PROCESS_CHECKPOINT_RECOVERY_V1.json"

def safe_status(head,phase,status,**extra):
    return {"schema":SCHEMA,"source_head":head,"phase":phase,"status":status,
      "worker_sha256":old.filehash(old.WORKER_PATH),"scientific_design_sha256":n.DESIGN_SHA,
      "input_manifest_sha256":n.MANIFEST_SHA,"identity_count":1576,"input_shard_count":100,**extra}
def runtime(head):
    a.need(os.environ.get("GITHUB_REPOSITORY")==old.REPO and
      os.environ.get("GITHUB_REF")=="refs/heads/"+old.BRANCH and
      os.environ.get("GITHUB_RUN_ATTEMPT")=="1","EVENT_OR_RETRY_DENIED")
    a.need(head==a.git("rev-parse","HEAD").decode().strip(),"CHECKOUT_SOURCE_DRIFT")
    a.need(old.api("git/ref/heads/"+old.BRANCH)["object"]["sha"]==head,"LIVE_BRANCH_DRIFT")
def claim_name(arm):return "mxm-numeric-v2-claim-"+arm["mode"]+"-"+arm["invocation_id"]
def release_name(arm,run):return "mxm-numeric-v2-"+arm["mode"]+"-"+arm["invocation_id"][:12]+"-"+str(run)
def existing_ref(name):
    refs=old.api("git/matching-refs/tags/"+name)
    return [r for r in refs if r["ref"]=="refs/tags/"+name]

class Store(old.GitHubStore):
    def __init__(self,head,key,public,tmp,arm,approval_sha,fp):
        super().__init__(head,key,public,tmp,arm["mode"])
        self.arm=arm;self.approval_sha=approval_sha;self.synthetic_fp=fp
        self.original_run=int(os.environ["GITHUB_RUN_ID"])
        self.name=release_name(arm,self.original_run)
        self.last=None;self.claimed=False;self.prior={"cpu_seconds":0,"wall_seconds":0}
    def body(self,document):
        raw=validate_public_blob(CHECK_STATUS,document)
        old.api("releases/"+str(self.release["id"]),{"body":raw.decode()},method="PATCH")
        got=old.api("releases/"+str(self.release["id"]))
        a.need(got["body"].encode()==raw,"DURABLE_RECEIPT_READBACK")
        self.last=document
    def claim(self):
        runtime(self.head)
        a.need(not existing_ref(claim_name(self.arm)),"CONSUMED_ARM")
        # Git ref creation is atomic. A competing claimant cannot overwrite it.
        old.api("git/refs",{"ref":"refs/tags/"+claim_name(self.arm),"sha":self.head})
        self.claimed=True
        document=safe_status(self.head,"NUMERIC_DEVELOPMENT","NOT_PERSISTED",
             run_id=self.original_run,failure_code="NONE")
        raw=validate_public_blob(CHECK_STATUS,document)
        self.release=old.api("releases",{"tag_name":self.name,"target_commitish":self.head,
          "name":"MXM encrypted numeric V2 "+self.mode,"draft":False,"prerelease":True,"body":raw.decode()})
        a.need(old.api("releases/"+str(self.release["id"]))["body"].encode()==raw,"CLAIM_RELEASE_READBACK")
        self.last=document
    def envelope(self,engine,expected_rows,processed,resources):
        return {"schema":"mxm.numeric.prefix.v2","arm_sha256":a.sha(a.enc(self.arm)),
          "approval_sha256":self.approval_sha,"source_head":self.arm["source_head"],
          "bindings":self.arm["bindings"],"invocation_id":self.arm["invocation_id"],
          "original_run_id":self.original_run,"next_shard":engine["next_shard"],
          "expected_rows":expected_rows,"processed_sources":processed,"resources":resources,
          "engine":engine}
    def checkpoint(self,engine,expected_rows,processed):
        idx=engine["next_shard"]
        resources=old.usage()
        for k in self.prior:resources[k]+=self.prior[k]
        meta=self.encrypted(self.envelope(engine,expected_rows,processed,resources),
                            f"prefix-{idx:03d}.mxmenc")
        receipt=self.encrypted({"schema":"mxm.numeric.encrypted.receipt.v2","checkpoint":meta},
                               f"receipt-{idx:03d}.mxmenc")
        self.body(safe_status(self.head,"NUMERIC_DEVELOPMENT","NOT_PERSISTED",
          run_id=self.original_run,encrypted_artifact_name=receipt["name"],
          encrypted_artifact_sha256=receipt["ciphertext_sha256"],failure_code="NONE"))
        return meta
    def decode_named(self,document):
        # The exact receipt hash is anchored in the durable guarded release body.
        assets=old.api("releases/"+str(self.release["id"])+"/assets?per_page=100")
        matches=[x for x in assets if x["name"]==document["encrypted_artifact_name"]]
        a.need(len(matches)==1,"RECOVERY_RECEIPT_ASSET")
        asset=matches[0]
        a.need(asset["digest"]=="sha256:"+document["encrypted_artifact_sha256"],"RECOVERY_RECEIPT_DIGEST")
        blob=old.download(asset["browser_download_url"],asset["size"])
        a.need(len(blob)==asset["size"] and a.sha(blob)==document["encrypted_artifact_sha256"],"RECOVERY_RECEIPT_BYTES")
        packed=old.crypto.decrypt_package(blob,private_key=self.key,
          expected_public_spki_sha256=old.FP if self.mode=="real" else self.synthetic_fp,temp_parent=self.tmp)
        import gzip
        raw=gzip.decompress(packed);doc=old.crypto.strict_json(raw)
        a.need(a.enc(doc)==raw,"RECOVERY_RECEIPT_CANONICAL")
        return doc
    def recovery(self,auth,previous):
        self.original_run=previous;self.name=release_name(self.arm,previous)
        refs=existing_ref(claim_name(self.arm))
        a.need(len(refs)==1,"ORIGINAL_INVOCATION_NOT_CLAIMED")
        original_head=refs[0]["object"]["sha"]
        a.ancestor(self.arm["source_head"],original_head);a.ancestor(original_head,self.head)
        self.release=old.api("releases/tags/"+self.name)
        body=json.loads(self.release["body"])
        validate_public_blob(CHECK_STATUS,body)
        a.need(body["source_head"]==original_head and body["run_id"]==previous and
          body["status"] in ("NOT_PERSISTED","FAIL_CLOSED") and
          body["phase"]=="NUMERIC_DEVELOPMENT","RECOVERY_ORIGINAL_IDENTITY")
        a.recovery_gate(auth,self.arm,self.approval_sha,previous,body)
        a.need(self.release["tag_name"]==self.name and self.release["target_commitish"]==original_head,
               "RECOVERY_RELEASE_BINDING")
        receipt=self.decode_named(body)
        a.need(set(receipt)=={"schema","checkpoint"} and receipt["schema"]=="mxm.numeric.encrypted.receipt.v2",
               "RECOVERY_RECEIPT_SCHEMA")
        prefix=self.restore(receipt["checkpoint"])
        a.need(prefix["schema"]=="mxm.numeric.prefix.v2" and
          prefix["arm_sha256"]==a.sha(a.enc(self.arm)) and prefix["approval_sha256"]==self.approval_sha and
          prefix["source_head"]==self.arm["source_head"] and prefix["bindings"]==self.arm["bindings"] and
          prefix["invocation_id"]==self.arm["invocation_id"] and prefix["original_run_id"]==previous and
          prefix["next_shard"]==auth["next_shard"]==prefix["engine"]["next_shard"],"RECOVERY_PREFIX_BINDING")
        a.need(len(prefix["engine"]["states"])==1576 and len(prefix["processed_sources"])==prefix["next_shard"]
          and prefix["expected_rows"]==prefix["engine"]["rows"],"RECOVERY_ENGINE_BINDING")
        a.need(all(auth["previous_resource_ceiling"][k]>=prefix["resources"][k]
                   for k in auth["previous_resource_ceiling"]),"RECOVERY_RESOURCE_UNDERSTATEMENT")
        tag="mxm-numeric-v2-recovery-"+self.arm["mode"]+"-"+body["encrypted_artifact_sha256"]
        a.need(not existing_ref(tag),"CONSUMED_RECOVERY")
        old.api("git/refs",{"ref":"refs/tags/"+tag,"sha":self.head})
        self.claimed=True;self.last=body
        return prefix

def fabricated_shard(seg,k,master,digits):
    """Smaller new boundary fixture: 56 bars/identity/segment, not old104."""
    raw,meta=old.fabricated_shard(seg,k,master,digits)
    obj=json.loads(raw)
    start=n.START+(seg-1)*n.SEGMENT_BARS*300
    indices=set(range(28))|set(range(n.SEGMENT_BARS-28,n.SEGMENT_BARS))
    for item in obj["items"]:
        item["rows"]=[r for r in item["rows"] if (old.crypto.timestamp(r["time_utc"])-start)//300 in indices]
    raw=old.crypto.canonical(obj);meta["PLAINTEXT_CANONICAL_SHA256"]=a.sha(raw)
    meta["ROW_COUNT"]=sum(len(i["rows"]) for i in obj["items"])
    return raw,meta

def source_record(idx,meta):
    return {"ordinal":idx,"segment":meta["SEGMENT_INDEX"],"shard":meta["SHARD_INDEX"],
      "plaintext_sha256":meta["PLAINTEXT_CANONICAL_SHA256"],"rows":meta["ROW_COUNT"],
      "ciphertext_sha256":meta["ENCRYPTED_ASSET_SHA256"]}
def verify_processed(prefix,mode,master,digits,entries):
    for idx,record in enumerate(prefix["processed_sources"]):
        if mode=="real":expected=source_record(idx,entries[idx])
        else:
            _,meta=fabricated_shard(idx//25+1,idx%25,master,digits)
            expected={**source_record(idx,{**meta,"ENCRYPTED_ASSET_SHA256":record["ciphertext_sha256"]})}
        a.need(record==expected,"RECOVERY_COMPLETED_SOURCE_DRIFT")
    a.need(sum(x["rows"] for x in prefix["processed_sources"])==prefix["expected_rows"],"RECOVERY_ROW_PREFIX")
    for i,s in enumerate(prefix["engine"]["states"]):
        a.need(s["ordinal"]==i+1 and s["symbol_id"]==master[i]["symbol_id"] and
          s["context"]==master[i].get("asset_class","UNKNOWN") and
          set(s["lag"])==set(map(str,n.LAGS)) and len(s["weekly"])==4 and
          0<=s["next_clock"]<=672 and len(s["buffer"])<=96,"RECOVERY_CAUSAL_STATE")

def complete_report(engine,rows,arm,processed):
    report=n.finish(engine,rows)
    report["source_bindings"]={"source_head":arm["source_head"],"files":arm["bindings"],
       "manifest_sha256":n.MANIFEST_SHA,"design_sha256":n.DESIGN_SHA,"kernel_sha256":n.KERNEL_SHA,
       "timestamp_mask_canonical_sha256":a.read("research_core_v4/historical_access_v1/TIMESTAMP_CHECKPOINT_100_V1.json")["encrypted_checkpoint"]["canonical_mask_sha256"],
       "processed_sources":processed,"scope":arm["scope"]}
    # Calendar-vector covariance is descriptive across672 clocks, never iid inference.
    cov={}
    for lag in map(str,n.LAGS):
        vectors=report["hourly_calendar_vectors"][lag]
        a.need(len(vectors)==672 and all(len(v)==3 for v in vectors),"REPORT_CLOCK_VECTOR")
        means=[sum(v[k] for v in vectors)/672 for k in range(3)]
        cov[lag]=[[sum((v[i]-means[i])*(v[j]-means[j]) for v in vectors)/671
                    for j in range(3)] for i in range(3)]
    report["hourly_calendar_descriptive_covariance"]=cov
    a.need(len(report["identity_results"])==1576 and set(report["full_frontier"])=={"0","300","900"}
      and len(processed)==100 and rows==sum(x["rows"] for x in processed),"REPORT_COMPLETENESS")
    return report

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
            final=store.encrypted(report,"complete-development-result.mxmenc")
            # A private finished engine lets the harness compare every accumulator,
            # pending buffer, denominator and reason against a deterministic reference.
            store.encrypted(engine,"complete-scientific-state.mxmenc")
            receipt=store.encrypted({"schema":"mxm.numeric.final.receipt.v2","report":final,
              "assets":store.uploaded,"resources":old.usage(),"original_run":store.original_run,
              "resumed_from_shard":start},"complete-final-receipt.mxmenc")
            old.budget(maxwall=a.BUDGET["wall_seconds"]-prior["wall_seconds"],
                       maxcpu=a.BUDGET["cpu_seconds"]-prior["cpu_seconds"])
            store.body(safe_status(head,"FINAL","PASS",run_id=int(os.environ["GITHUB_RUN_ID"]),
              encrypted_artifact_name=receipt["name"],encrypted_artifact_sha256=receipt["ciphertext_sha256"],failure_code="NONE"))
            if mode=="real":store.publish(safe_status(head,"FINAL","PASS",run_id=int(os.environ["GITHUB_RUN_ID"]),
              encrypted_artifact_name=final["name"],encrypted_artifact_sha256=final["ciphertext_sha256"],failure_code="NONE"),
              PUB+"REAL_DEVELOPMENT_RESULT_V1.json")
            print(json.dumps({"status":"PASS_ENCRYPTED_REMOTE_READBACK","pid":os.getpid(),
              "resumed_from_shard":start,"processed_this_process":100-start,"resources":old.usage()}),flush=True)
        except Exception:
            if store.last:
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
