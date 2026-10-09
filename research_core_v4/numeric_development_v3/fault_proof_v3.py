"""One bounded actual-remote finalization proof. Inputs are fabricated only.

Child processes know no report from the parent: they authenticate and restore
the encrypted remote journal. SIGKILL bypasses exception/finally handlers.
No historical input download and no numerical reducer are used in this proof.
"""
import argparse
import base64
import json
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
from research_core_v4.numeric_development_v1 import numeric_machine_entrypoint_v1 as old
from research_core_v4.numeric_development_v2 import machine_v2 as v2
from research_core_v4.numeric_development_v3 import authority_v3 as a
from research_core_v4.numeric_development_v3 import finalization_v3 as f
from research_core_v4.numeric_development_v1.public_output_guard_v1 import ROOT as PUB, validate_public_blob

STOPS=("before_report","after_report","after_receipt","before_public_git","after_public_git","before_completion_readback")
ERRORS=("reject_blob","reject_commit","reject_update","cipher_mismatch","release_mismatch")

def store_for(case,keydir):
    head=os.environ["GITHUB_SHA"]
    arm=a.candidate(head,a.read(a.BINDINGS)["bindings"]);arm["mode"]="synthetic"
    approval={"schema":"mxm.numeric.independent.acceptance.v3","status":"INDEPENDENT_ACCEPTANCE_PASS",
      "mode":"synthetic","role":"FABRICATED_TEST_AUTHORITY","arm_sha256":a.sha(a.enc(arm)),
      "source_head":head,"arm_commit":head,"audit_receipt_sha256":"a"*64,"explicit_acceptance":True}
    a.validate(arm,approval,head,"synthetic",a.enc(arm),artifacts=False)
    kd=pathlib.Path(keydir)
    der=subprocess.check_output(["openssl","pkey","-pubin","-in",str(kd/"public.pem"),"-outform","DER"],stderr=subprocess.DEVNULL)
    store=f.Store(head,kd/"private.pem",kd/"public.pem",kd,arm,a.sha(a.enc(approval)),a.sha(der))
    store.name="mxm-atomicity-v3-"+os.environ["GITHUB_RUN_ID"]+"-"+case.replace("_","")
    return store

def injection(store,fault):
    api=old.api;download=old.download;fired=False
    def once():
        nonlocal fired
        if fired:return False
        fired=True;return True
    def bad_api(endpoint,body=None,method=None):
        if ((fault=="reject_blob" and endpoint=="git/blobs") or
            (fault=="reject_commit" and endpoint=="git/commits" and body is not None) or
            (fault=="reject_update" and endpoint.startswith("git/refs/heads/") and method=="PATCH")) and once():
            raise v2.n.NumericalStop("INJECTED_GIT_REJECTION")
        result=api(endpoint,body,method)
        if fault=="release_mismatch" and endpoint=="releases/"+str(store.release["id"]) and body is None:
            if json.loads(result["body"]).get("encrypted_artifact_name")==f.RECEIPT and once():
                result["body"]="{}"
        return result
    def bad_download(url,limit):
        blob=download(url,limit)
        if fault=="cipher_mismatch" and url.endswith("/"+f.REPORT) and once():
            return bytes([blob[0]^1])+blob[1:]
        return blob
    old.api=bad_api;old.download=bad_download
    def hook(boundary):
        if boundary==fault:
            print(json.dumps({"boundary":boundary,"pid":os.getpid(),"termination":"SIGKILL"}),flush=True)
            os.kill(os.getpid(),signal.SIGKILL)
    return hook

def child(args):
    store=store_for(args.case,args.key_dir)
    store.release=old.api("releases/tags/"+store.name)
    journal,_=store.load_named(f.JOURNAL)
    hook=injection(store,args.fault)
    result=f.finish(store,journal,hook)
    print(json.dumps({"pid":os.getpid(),"result":result,"resources":old.usage()}),flush=True)

def call_child(case,kd,fault="none"):
    p=subprocess.run([sys.executable,"-m","research_core_v4.numeric_development_v3.fault_proof_v3",
      "--child","--case",case,"--key-dir",str(kd),"--fault",fault],capture_output=True,text=True,timeout=300)
    print(p.stdout,end="",flush=True)
    # Tracebacks contain only code/error names, never private document values.
    if p.returncode not in (0,-signal.SIGKILL):print(json.dumps({"child_exit":p.returncode,"case":case,"error":p.stderr.splitlines()[-1] if p.stderr else "NO_ERROR_TEXT"}),flush=True)
    return p.returncode

def proof():
    v2.runtime(os.environ["GITHUB_SHA"])
    arm=a.candidate(os.environ["GITHUB_SHA"],a.read(a.BINDINGS)["bindings"])
    # Fabricated in-memory real-shaped authorization; never an acceptance file.
    approval={"schema":"mxm.numeric.independent.acceptance.v3","status":"INDEPENDENT_ACCEPTANCE_PASS",
      "mode":"real","role":"INDEPENDENT_AUDITOR","arm_sha256":a.sha(a.enc(arm)),
      "source_head":arm["source_head"],"arm_commit":arm["source_head"],"audit_receipt_sha256":"a"*64,"explicit_acceptance":True}
    a.validate(arm,approval,os.environ["GITHUB_SHA"],"real",a.enc(arm),artifacts=False)
    a.need(not (a.ROOT/a.APPROVAL).exists(),"REAL_APPROVAL_MUST_BE_ABSENT")
    campaign="mxm-finalization-v3-proof-"+os.environ["GITHUB_SHA"]
    a.need(not v2.existing_ref(campaign),"PROOF_ALREADY_CONSUMED")
    old.api("git/refs",{"ref":"refs/tags/"+campaign,"sha":os.environ["GITHUB_SHA"]})
    records=[];inventories=[]
    with tempfile.TemporaryDirectory(prefix="mxm-finalization-proof-") as td:
        kd=pathlib.Path(td);kd.chmod(0o700)
        key,fp=old._private_key_from_secret(kd)
        a.need(fp==old.FP,"CONFIGURED_KEY_FINGERPRINT")
        # The existing approved key is used only for fabricated encryption.
        os.replace(key,kd/"private.pem")
        (kd/"public.pem").write_bytes((a.ROOT/old.PUBLIC_KEY).read_bytes())
        for case in (*STOPS,*ERRORS,"normal","after_completion_ref"):
            old.budget(maxwall=3500)
            store=store_for(case,kd)
            document=v2.safe_status(os.environ["GITHUB_SHA"],"PUBLICATION","NOT_PERSISTED",run_id=int(os.environ["GITHUB_RUN_ID"]),failure_code="NONE")
            raw=validate_public_blob(v2.CHECK_STATUS,document)
            store.release=old.api("releases",{"tag_name":store.name,"target_commitish":os.environ["GITHUB_SHA"],
              "name":"MXM V3 fabricated finalization "+case,"draft":False,"prerelease":True,"body":raw.decode()})
            # Tiny private delivery fixtures. Not a MASTER1576 numerical result.
            report={"fixture":"FABRICATED_FINALIZATION_ONLY","private_vector":[1.25,-2.5,3.75],"case":case}
            engine={"next_shard":100,"fixture":"NO_SCIENTIFIC_EXECUTION","case":case}
            journal=store.prepare(report,engine,100)
            code=call_child(case,kd,case if case not in ("normal",) else "none")
            expected=-signal.SIGKILL if case in (*STOPS,"after_completion_ref") else (1 if case in ERRORS else 0)
            a.need(code==expected,"UNEXPECTED_FAULT_EXIT")
            before=f.verify_complete(store)
            a.need((before is not None)==(case in ("normal","after_completion_ref")),"FALSE_PASS_INCOMPLETE")
            assets_before=old.api("releases/"+str(store.release["id"])+"/assets?per_page=100")
            a.need(all(x["name"].endswith(".mxmenc") for x in assets_before),"PRIVATE_ASSET_NOT_ENCRYPTED")
            # Restart is a distinct process with only encrypted GitHub journal.
            # It does not call the numerical worker or replay any source shard.
            resumed=call_child(case,kd)
            a.need(resumed==0,"COLD_FINALIZATION_FAILED")
            complete=f.verify_complete(store);a.need(complete is not None,"COMPLETE_READBACK_ABSENT")
            assets_complete=old.api("releases/"+str(store.release["id"])+"/assets?per_page=100")
            repeated=call_child(case,kd) if case=="normal" else None
            if case=="normal":
                a.need(repeated==0,"REPEATED_FINALIZATION_FAILED")
                a.need(old.api("releases/"+str(store.release["id"])+"/assets?per_page=100")==assets_complete and
                  f.verify_complete(store)["completion_commit"]==complete["completion_commit"],"SECOND_SCIENTIFIC_EXECUTION")
            got,_=store.load_named(f.REPORT);state,_=store.load_named(f.STATE)
            a.need(got==report and state==engine,"FINALIZATION_PARITY")
            record={"case":case,"first_exit":code,"cold_exit":resumed,"repeat_exit":repeated,
              "global_pass_before_recovery":before is not None,"global_pass_after_readback":True,
              "completion_commit":complete["completion_commit"],"completion_ref":complete["completion_ref"],
              "release_id":store.release["id"],"release_tag":store.name,"shards_replayed":0,
              "report_canonical_sha256":a.sha(a.enc(report)),"state_canonical_sha256":a.sha(a.enc(engine))}
            records.append(record)
            inventories.append({"release_id":store.release["id"],"assets":[{k:x[k] for k in ("id","name","size","digest","browser_download_url")} for x in assets_complete]})
            print(json.dumps({"case_result":record}),flush=True)
        proof={"schema":"mxm.numeric.finalization.proof.v3","source_head":os.environ["GITHUB_SHA"],
          "run_id":int(os.environ["GITHUB_RUN_ID"]),"cases":records,"inventories":inventories,
          "resources":old.usage(),"configured_key_fingerprint":fp,"scientific_reducer_calls":0,
          "historical_input_downloads":0,"real_approval_absent":True,"real_numeric_run_started":False,
          "authoritative_pass":"IMMUTABLE_COMPLETION_REF_AND_FULL_REMOTE_BYTE_VERIFICATION"}
        meta=store.put(proof,"finalization-fault-proof.mxmenc")
        a.need(store.restore(meta)==proof,"PROOF_REMOTE_READBACK")
        path=PUB+"FINALIZATION_CRASH_BOUNDARY_PROOF_V1.json"
        store.publish_exact(v2.safe_status(os.environ["GITHUB_SHA"],"PUBLICATION","PASS",
          run_id=int(os.environ["GITHUB_RUN_ID"]),encrypted_artifact_name=meta["name"],encrypted_artifact_sha256=meta["ciphertext_sha256"],
          cpu_seconds=proof["resources"]["cpu_seconds"],wall_seconds=proof["resources"]["wall_seconds"],peak_kib=proof["resources"]["peak_kib"],failure_code="NONE"),path)
        print(json.dumps({"proof":"PASS_ALL_13_REMOTE_CASES","cases":records,"inventories":inventories,
          "proof_asset":meta,"resources":old.usage(),"real_numeric_run_started":False}),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument("--child",action="store_true");p.add_argument("--case");p.add_argument("--key-dir");p.add_argument("--fault",default="none")
    args=p.parse_args()
    if args.child:child(args)
    else:proof()

if __name__=="__main__":main()
