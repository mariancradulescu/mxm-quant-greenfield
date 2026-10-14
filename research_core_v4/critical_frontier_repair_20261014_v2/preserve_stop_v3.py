"""Owner-authorized checkpoint preservation and controlled cancellation; no broker IO."""
import os,json,time,tempfile,pathlib,base64,hashlib,urllib.request,urllib.error
from datetime import datetime,timezone
from research_core_v4.full_native_frontier_20261014_v1.runner_v1 import E,FrontierStore,encode,need
OLD_RUN=38555928258
OLD_RELEASE=412634211
OLD_HEAD="ad8f9037c8839f5450013f72d97321c52f572c21"
PREFIX="research_core_v4/full_native_frontier_20261014_v1/"
def api(path,method="GET",data=None):
    raw=None if data is None else json.dumps(data).encode()
    req=urllib.request.Request("https://api.github.com/repos/"+E.w.old.REPO+"/"+path,data=raw,method=method,headers={"Authorization":"Bearer "+os.environ["GH_TOKEN"],"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"})
    with urllib.request.urlopen(req,timeout=45) as res:
        content=res.read()
    return json.loads(content) if content else None
def complete_assets(rid):
    result=[];page=1
    while True:
        batch=api("releases/"+str(rid)+"/assets?per_page=100&page="+str(page))
        result.extend(batch)
        if len(batch)<100:return result
        page+=1
def verify_snapshot(store,body,all_references=False):
    meta=body["current_journal"];st=store.restore(meta)
    need(st["generation"]==body["generation"],"GENERATION_BINDING")
    verified=[meta]
    if all_references:
        for field in ("shards","record_shards"):
            for ref in st.get(field,{}).values():
                store.restore(ref);verified.append(ref)
    return st,verified
def main():
    os.umask(0o077)
    need(os.environ["GITHUB_RUN_ATTEMPT"]=="1","NO_AUTO_RERUN")
    need(datetime.now(timezone.utc).isoformat()<"2026-10-18T00:00:00+00:00","AUTHORITY_EXPIRED")
    auth=json.loads((E.a.ROOT/(PREFIX+"EXECUTION_V1.json")).read_text())
    for path,sha in auth["bindings"].items():
        need(E.w.old.filehash(path)==sha,"FROZEN_SOURCE_DRIFT")
    run=api("actions/runs/"+str(OLD_RUN));need(run["head_sha"]==OLD_HEAD,"OLD_RUN_IDENTITY")
    with tempfile.TemporaryDirectory(prefix="mxm-critical-preserve-",dir=os.environ["RUNNER_TEMP"]) as td:
        tmp=pathlib.Path(td);key,fp=E.w.old._private_key_from_secret(tmp)
        need(fp==E.w.old.FP,"OWNER_KEY")
        store=FrontierStore(os.environ["GITHUB_SHA"],key,E.a.ROOT/E.w.old.PUBLIC_KEY,tmp,"real")
        store.release=api("releases/"+str(OLD_RELEASE))
        before=json.loads(store.release["body"]);before_st,before_refs=verify_snapshot(store,before)
        print(json.dumps({"phase":"PRE_CANCEL_OWNER_JOURNAL_VERIFIED","run":OLD_RUN,"generation":before_st["generation"],"journal":before["current_journal"]}),flush=True)
        cancel_requested=False
        if run["status"]!="completed":
            try:
                api("actions/runs/"+str(OLD_RUN)+"/cancel","POST",{})
                cancel_requested=True
            except urllib.error.HTTPError as exc:
                if exc.code!=409:raise RuntimeError("CANCEL_HTTP_"+str(exc.code)) from None
        deadline=time.monotonic()+30
        force_requested=False
        while True:
            run=api("actions/runs/"+str(OLD_RUN))
            if run["status"]=="completed":break
            if time.monotonic()>=deadline:
                if force_requested:raise RuntimeError("OLD_RUN_NOT_TERMINAL_NO_NEW_WRITER")
                api("actions/runs/"+str(OLD_RUN)+"/force-cancel","POST",{})
                force_requested=True;deadline=time.monotonic()+180
            time.sleep(5)
        store.release=api("releases/"+str(OLD_RELEASE));after=json.loads(store.release["body"])
        st,refs=verify_snapshot(store,after,True)
        assets=complete_assets(OLD_RELEASE)
        need(all(any(a["id"]==ref["id"] and a["digest"]=="sha256:"+ref["ciphertext_sha256"] and a["state"]=="uploaded" for a in assets) for ref in refs),"FINAL_REFERENCE_ENUMERATION")
        proof={"schema":"mxm.critical.preservation.proof.v1","created_utc":datetime.now(timezone.utc).isoformat(),"source_head":os.environ["GITHUB_SHA"],"old_run":OLD_RUN,"old_head":OLD_HEAD,"old_status":run["status"],"old_conclusion":run["conclusion"],"cancel_requested":cancel_requested,"force_cancel_requested":force_requested,"old_release":OLD_RELEASE,"last_safe_checkpoint":after["current_journal"],"generation":st["generation"],"identities_processed":st["identity_cursor"],"identities_total":len(st["eligible"]),"requests":st["requests"],"verified_shard_references":len(refs),"accepted_assets_count":len(assets),"pending_requests":st.get("pending_requests",[]),"pending_state":"UNCERTAIN_WIRE_NO_AUTOMATIC_RESEND","asset_inventory":[{k:a[k] for k in ("id","name","size","digest","state")} for a in assets],"before_cancel_journal":before["current_journal"],"OWNER_READBACK_SUCCESS":True,"no_broker_requests":True,"no_asset_deleted":True,"orders":0,"alpha_certified":False,"HARD21":False}
        tag="mxm-critical-preserve-20261014-"+os.environ["GITHUB_RUN_ID"]
        store.release=api("releases","POST",{"tag_name":tag,"target_commitish":os.environ["GITHUB_SHA"],"name":"MXM controlled stop checkpoint preservation","prerelease":True,"body":json.dumps({"state":"PROOF_PENDING","old_run":OLD_RUN})})
        meta=store.encrypted(json.loads(encode(proof)),"checkpoint-preservation-owner.mxmenc")
        need(store.restore(meta)==json.loads(encode(proof)),"PRESERVATION_COLD_READBACK")
        safe={k:proof[k] for k in ("schema","source_head","old_run","old_head","old_status","old_conclusion","cancel_requested","force_cancel_requested","old_release","last_safe_checkpoint","generation","identities_processed","identities_total","requests","verified_shard_references","accepted_assets_count","OWNER_READBACK_SUCCESS","no_broker_requests","no_asset_deleted","orders","alpha_certified","HARD21")}
        safe.update(state="OLD_RUN_TERMINAL_CHECKPOINT_PRESERVED",pending_request_count=len(proof["pending_requests"]),encrypted_proof=meta,preservation_release=store.release["id"])
        api("releases/"+str(store.release["id"]),"PATCH",{"body":json.dumps(safe,sort_keys=True)})
        print(json.dumps(safe,sort_keys=True),flush=True)
if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("CRITICAL_PRESERVATION_FAIL_CLOSED_"+(str(exc) if str(exc).replace("_","").isalnum() and len(str(exc))<120 else type(exc).__name__),flush=True)
        raise SystemExit(1) from None
