"""GitHub-side numerical development entrypoint.

--synthetic uses ONLY fabricated source packages and ephemeral RSA key.
--real is default-deny absent a separate exact independent approval AND ARM.
Neither mode uses broker APIs, executes orders, nor publishes private results.
"""
import argparse
import base64
import copy
import gzip
import hashlib
import json
import os
import pathlib
import re
import resource
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal

from research_core_v4.numeric_development_v1 import numeric_streaming_executor_v1 as num
from research_core_v4.numeric_development_v1.public_output_guard_v1 import safe_public_git_blob, SCHEMA, ROOT as PUBLIC_ROOT
from research_core_v4 import master1576_screen_v2 as crypto
from research_core_v4.shallow_m5_support_v2_production import encrypt_shard
from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret

ROOT=pathlib.Path(__file__).resolve().parents[2]
REPO="mariancradulescu/mxm-quant-greenfield"
BRANCH="performance-research-v3-20260922"
MANIFEST="research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_FINAL_DURABLE_MANIFEST_V1.json"
MASTER_PATH="research_core_v4/state/QUOTE_CURRENT_METADATA_ANDROID_FRONTIER_V1.json"
DIGITS_PATH="research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_SYMBOL_DIGITS_MAP.json"
PUBLIC_KEY="research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem"
FP="464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11"
ARM_PATH="research_core_v4/numeric_development_v1/EXACT_REAL_DEVELOPMENT_ARM_V1.json"
APPROVAL_PATH="research_core_v4/numeric_development_v1/INDEPENDENT_NUMERIC_PREARM_ACCEPTANCE_V1.json"
WORKER_PATH="research_core_v4/numeric_development_v1/numeric_streaming_executor_v1.py"
ENTRY_PATH="research_core_v4/numeric_development_v1/numeric_machine_entrypoint_v1.py"
GUARD_PATH="research_core_v4/numeric_development_v1/public_output_guard_v1.py"
STARTED=time.monotonic()

def need(cond,code):
    if not cond:raise num.NumericalStop(code)
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(x):return num.enc(x)
def filehash(p):return sha((ROOT/p).read_bytes())
def usage():
    c=resource.getrusage(resource.RUSAGE_CHILDREN);m=resource.getrusage(resource.RUSAGE_SELF)
    return {"wall_seconds":time.monotonic()-STARTED,
            "cpu_seconds":time.process_time()+c.ru_utime+c.ru_stime,
            "peak_kib":max(c.ru_maxrss,m.ru_maxrss)}
def budget(maxwall=3600,maxcpu=7200,maxkib=8*1048576):
    u=usage()
    need(u["wall_seconds"]<=maxwall,"WALL_BUDGET")
    need(u["cpu_seconds"]<=maxcpu,"CPU_BUDGET")
    need(u["peak_kib"]<=maxkib,"RAM_BUDGET")
def verify_science():
    for path,expected in ((MANIFEST,num.MANIFEST_SHA),
                          ("research_core_v4/existing1576_data_first_v1/EXACT_NEW_DEVELOPMENT_SCREEN_DESIGN_V1.json",num.DESIGN_SHA),
                          ("research_core_v4/existing1576_data_first_v1/coupling_response_kernel_v1.py",num.KERNEL_SHA)):
        need(filehash(path)==expected,"FROZEN_SOURCE_DIGEST")
    masterdata=json.loads((ROOT/MASTER_PATH).read_text())
    master=masterdata["entries"] if isinstance(masterdata,dict) else masterdata
    # MASTER source is metadata frontier, not the eligible roster; strict 1576 order.
    need(len(master)==1576 and all(type(x["symbol_id"]) is int for x in master),"MASTER_FRONTIER_INVALID")
    manifest=json.loads((ROOT/MANIFEST).read_text())
    entries=manifest["entries"]
    need(len(entries)==100 and [(e["SEGMENT_INDEX"],e["SHARD_INDEX"]) for e in entries]==
         [(s,k) for s in range(1,5) for k in range(25)],"EXACT_100_ASSET_ORDER")
    dm=json.loads((ROOT/DIGITS_PATH).read_text())
    digits={x["symbol_id"]:x["digits"] for x in dm["entries"]}
    need(len(digits)==1576 and {x["symbol_id"] for x in master}==set(digits),"DIGITS_MASTER_DRIFT")
    return master,entries,digits,manifest
def api(endpoint,body=None,method=None):
    request=urllib.request.Request("https://api.github.com/repos/"+REPO+"/"+endpoint,
      data=canonical(body) if body is not None else None,method=method,
      headers={"Authorization":"Bearer "+os.environ["GH_TOKEN"],
       "Accept":"application/vnd.github+json","Content-Type":"application/json",
       "X-GitHub-Api-Version":"2022-11-28"})
    try:
        with urllib.request.urlopen(request,timeout=65) as resp:return json.load(resp)
    except Exception:raise num.NumericalStop("GITHUB_REMOTE_FAILURE") from None
def download(url,maxbytes):
    need(url.startswith("https://github.com/"+REPO+"/releases/download/"),"REMOTE_URL_SCOPE")
    try:
        with urllib.request.urlopen(url,timeout=90) as resp:b=resp.read(maxbytes+1)
    except Exception:raise num.NumericalStop("REMOTE_DOWNLOAD_FAILURE") from None
    need(len(b)<=maxbytes,"REMOTE_ASSET_BUDGET")
    return b
class GitHubStore:
    def __init__(self,source,private,public,tmp,mode):
        self.head=source;self.key=private;self.public=public;self.tmp=tmp;self.mode=mode
        self.name="mxm-numeric-"+mode+"-"+source[:16]+"-"+os.environ["GITHUB_RUN_ID"]
        self.release=None;self.uploaded=[]
    def claim(self):
        need(api("git/ref/heads/"+BRANCH)["object"]["sha"]==self.head,"LIVE_BRANCH_DRIFT")
        tag="mxm-numeric-claim-"+self.mode+"-"+self.head[:16]
        api("git/refs",{"ref":"refs/tags/"+tag,"sha":self.head})
        # Reject any second invocation of the same exact-source experiment.
        self.release=api("releases",{"tag_name":self.name,"target_commitish":self.head,
          "name":"MXM confidential numeric "+self.mode,"draft":False,"prerelease":True,
          "body":json.dumps({"mode":self.mode,"source_head":self.head,
              "confidential":"encrypted_only","no_broker":True},sort_keys=True)})
    def encrypted(self,value,name):
        need(self.release is not None and re.fullmatch("[a-z0-9-]+\\.mxmenc",name)!=None,"UNAPPROVED_ENCRYPTED_ASSET")
        raw=canonical(value);need(len(raw)<128*1024*1024,"CHECKPOINT_PLAIN_BUDGET")
        packed=gzip.compress(raw,mtime=0)
        dest=self.tmp/name
        encrypt_shard(packed,public_key=self.public,output=dest)
        ciphertext=dest.read_bytes();need(len(ciphertext)<128*1024*1024,"CHECKPOINT_CIPHER_BUDGET")
        url="https://uploads.github.com/repos/"+REPO+"/releases/"+str(self.release["id"])+"/assets?name="+name
        try:
            request=urllib.request.Request(url,data=ciphertext,method="POST",headers={
              "Authorization":"Bearer "+os.environ["GH_TOKEN"],"Content-Type":"application/octet-stream",
              "Accept":"application/vnd.github+json"})
            with urllib.request.urlopen(request,timeout=120) as resp:asset=json.load(resp)
        except Exception:raise num.NumericalStop("ENCRYPTED_REMOTE_UPLOAD") from None
        meta={"id":asset["id"],"name":name,"size":len(ciphertext),
              "ciphertext_sha256":sha(ciphertext),"canonical_sha256":sha(raw),
              "gzip_sha256":sha(packed),"url":asset["browser_download_url"]}
        need(self.restore(meta)==value,"ENCRYPTED_REMOTE_PLAINTEXT_READBACK")
        dest.unlink(missing_ok=True);self.uploaded.append(meta)
        return meta
    def restore(self,meta):
        need(self.release is not None,"RELEASE_UNINITIALIZED")
        assets=api("releases/"+str(self.release["id"])+"/assets?per_page=100")
        match=[a for a in assets if a["id"]==meta["id"] and a["name"]==meta["name"]]
        need(len(match)==1 and match[0]["size"]==meta["size"] and
             match[0]["digest"]=="sha256:"+meta["ciphertext_sha256"],"CIPHERTEXT_REMOTE_METADATA_DRIFT")
        got=download(match[0]["browser_download_url"],meta["size"])
        need(len(got)==meta["size"] and sha(got)==meta["ciphertext_sha256"],"CIPHERTEXT_REMOTE_READBACK")
        packed=crypto.decrypt_package(got,private_key=self.key,expected_public_spki_sha256=FP if self.mode=="real" else self.synthetic_fp,temp_parent=self.tmp)
        need(sha(packed)==meta["gzip_sha256"],"DECRYPTED_GZIP_SHA256_DRIFT")
        decompressed=gzip.decompress(packed)
        need(sha(decompressed)==meta["canonical_sha256"],"CANONICAL_CHECKPOINT_DRIFT")
        obj=crypto.strict_json(decompressed);need(canonical(obj)==decompressed,"NONCANONICAL_CHECKPOINT")
        return obj
    def publish(self,document,path):
        # Important: the actual Git blob creation closure is NEVER invoked if disallowed.
        need(api("git/ref/heads/"+BRANCH)["object"]["sha"]==self.head,"PUBLISH_PARENT_DRIFT")
        def create(raw):
            return api("git/blobs",{"content":base64.b64encode(raw).decode(),"encoding":"base64"})
        raw=safe_public_git_blob(path,document,create)
        # safe_public_git_blob returns the blob metadata, so independently
        # reconstruct exact allowed bytes for mandatory remote byte check.
        from research_core_v4.numeric_development_v1.public_output_guard_v1 import validate_public_blob
        expected=validate_public_blob(path,document)
        need(raw.get("sha") is not None,"GIT_BLOB_MISSING_SHA")
        tree=api("git/trees",{"base_tree":api("git/commits/"+self.head)["tree"]["sha"],
           "tree":[{"path":path,"mode":"100644","type":"blob","sha":raw["sha"]}]})
        commit=api("git/commits",{"message":"Persist guarded synthetic numeric evidence [skip ci]",
          "parents":[self.head],"tree":tree["sha"]})
        need(api("git/ref/heads/"+BRANCH)["object"]["sha"]==self.head,"PUBLICATION_CAS_DRIFT")
        api("git/refs/heads/"+BRANCH,{"sha":commit["sha"],"force":False},method="PATCH")
        self.head=commit["sha"]
        obj=api("contents/"+path+"?ref="+self.head)
        need(base64.b64decode(obj["content"])==expected,"PUBLIC_GIT_READBACK")
        return {"head":self.head,"public_sha256":sha(expected)}
def generate_key(tmp):
    private=tmp/"private.pem";public=tmp/"public.pem"
    subprocess.run(["openssl","genpkey","-algorithm","RSA","-pkeyopt","rsa_keygen_bits:2048","-out",str(private)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    private.chmod(0o600)
    subprocess.run(["openssl","pkey","-in",str(private),"-pubout","-out",str(public)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    der=subprocess.run(["openssl","pkey","-pubin","-in",str(public),"-outform","DER"],check=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL).stdout
    return private,public,sha(der)
def _fabricated_rows(segment,ordinal,digits):
    # Domain-faithful seven-day segments; useful clocks around both borders.
    segment_start=num.START+(segment-1)*num.SEGMENT_BARS*300
    indices=list(range(52))+list(range(num.SEGMENT_BARS-52,num.SEGMENT_BARS))
    out=[]
    for i in indices:
        ts=segment_start+i*300
        delta=(i%5)-2
        # positive prices and a deterministic mix of A/B agreement/disagreement
        p=100+(ordinal%11)
        op=Decimal(p)
        cl=op+Decimal(delta)/Decimal(10**digits if digits else 1)
        hi=max(op,cl)+Decimal(1)/Decimal(10**digits if digits else 1)
        lo=min(op,cl)-Decimal(1)/Decimal(10**digits if digits else 1)
        fmt=f".{digits}f"
        out.append({"time_utc":datetime.fromtimestamp(ts,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "open":format(op,fmt),"high":format(hi,fmt),
             "low":format(lo,fmt),"close":format(cl,fmt),
             "tick_volume":str((ordinal+i)%7)})
    return out
def fabricated_shard(seg,k,master,digits):
    lo=k*64+1;hi=min(num.MASTER,lo+63);items=[]
    first=None;last=None;count=0
    for ordinal in range(lo,hi+1):
        rows=[] if ordinal==515 else _fabricated_rows(seg,ordinal,digits[master[ordinal-1]["symbol_id"]])
        count+=len(rows)
        if rows:
            first=min(first or rows[0]["time_utc"],rows[0]["time_utc"])
            last=max(last or rows[-1]["time_utc"],rows[-1]["time_utc"])
        items.append({"ordinal":ordinal,"symbol_id":master[ordinal-1]["symbol_id"],
         "classification":"SHALLOW_SUPPORT_COMPLETE" if rows else "NO_HISTORICAL_SUPPORT","request_count":1,
         "retry_count":0,"page_cap_hits":0,"failure":None,
         "transport_geometry_pages":[],"rows":rows})
    raw=crypto.canonical({"schema":"mxm.v4.shallow-m5-v2.raw-shard.v1",
       "segment_index":seg,"shard_index":k,"identity_range":[lo,hi],"items":items})
    entry={"SEGMENT_INDEX":seg,"SHARD_INDEX":k,"IDENTITY_RANGE":[lo,hi],
           "ROW_COUNT":count,"REQUEST_COUNT":len(items),
           "RETRY_COUNT":0,"PAGE_CAP_HITS":0,"FAILURE_LEDGER":{},
           "PROTECTED_FORWARD_ROW_COUNT":0,"FIRST_TIMESTAMP":first,"LAST_TIMESTAMP":last,
           "PLAINTEXT_CANONICAL_SHA256":sha(raw)}
    return raw,entry
def real_prearm(head,master,entries):
    # Strictly before opening even one market ciphertext.
    need((ROOT/ARM_PATH).is_file() and (ROOT/APPROVAL_PATH).is_file(),"MISSING_INDEPENDENT_APPROVAL")
    arm=json.loads((ROOT/ARM_PATH).read_text())
    approval=json.loads((ROOT/APPROVAL_PATH).read_text())
    need(arm.get("status")=="AUTHORIZED_ONE_USE" and approval.get("status")=="INDEPENDENT_ACCEPTANCE_PASS",
         "MISSING_INDEPENDENT_APPROVAL")
    need(arm.get("exact_head")==head and approval.get("arm_sha256")==filehash(ARM_PATH),"REAL_ARM_DRIFT")
    need(arm.get("worker_sha256")==filehash(WORKER_PATH) and
         arm.get("entrypoint_sha256")==filehash(ENTRY_PATH) and
         arm.get("guard_sha256")==filehash(GUARD_PATH) and
         arm.get("design_sha256")==num.DESIGN_SHA and arm.get("input_manifest_sha256")==num.MANIFEST_SHA,
         "REAL_ARM_SOURCE_DRIFT")
    need(arm.get("assets")==100 and arm.get("identities")==1576 and
         arm.get("lags_seconds")==[0,300,900] and arm.get("attempts")==1,"REAL_ARM_SCOPE")
def run(mode):
    os.umask(0o077)
    need(os.environ.get("GITHUB_REPOSITORY")==REPO and
         os.environ.get("GITHUB_REF")=="refs/heads/"+BRANCH and
         os.environ.get("GITHUB_RUN_ATTEMPT")=="1","EVENT_OR_RETRY_DENIED")
    head=os.environ["GITHUB_SHA"]
    local=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    need(head==local,"CHECKOUT_SOURCE_DRIFT")
    master,entries,digits,manifest=verify_science()
    need(api("git/ref/heads/"+BRANCH)["object"]["sha"]==head,"BRANCH_MOVED")
    need(mode=="synthetic" or mode=="real","UNKNOWN_MODE")
    if mode=="real":real_prearm(head,master,entries)
    with tempfile.TemporaryDirectory(prefix="mxm-numeric-",dir=os.environ.get("RUNNER_TEMP","/tmp")) as td:
        tmp=pathlib.Path(td);tmp.chmod(0o700)
        if mode=="synthetic":
            key,public,fp=generate_key(tmp)
        else:
            need(bool(os.environ.get("MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM")),"EXISTING_KEY_ABSENT")
            key,fp=_private_key_from_secret(tmp);public=ROOT/PUBLIC_KEY
            need(fp==FP,"PRIVATE_KEY_FINGERPRINT")
        store=GitHubStore(head,key,public,tmp,mode)
        store.synthetic_fp=fp
        # Production already requires independent acceptance before creating claim.
        store.claim()
        engine=num.new(master)
        release=None;assets={}
        if mode=="real":
            acceptance=json.loads((ROOT/"research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_FINAL_CAMPAIGN_INDEPENDENT_ACCEPTANCE_AUTHORITY_V1.json").read_text())
            expected=acceptance["exact_release_inventory"]
            release=api("releases/tags/"+manifest["DURABLE_RELEASE_IDENTITY"])
            need(release["id"]==expected["release_id"] and json.loads(release["body"])==expected["body"],"INPUT_RELEASE_DRIFT")
            a=api("releases/"+str(release["id"])+"/assets?per_page=100&page=1")
            need(len(a)==100 and api("releases/"+str(release["id"])+"/assets?per_page=100&page=2")==[],"INPUT_ASSET_COUNT")
            assets={v["name"]:v for v in a}
            for x in expected["assets"]:
                need(x["name"] in assets and all(assets[x["name"]].get(k)==v for k,v in x.items()),"INPUT_ASSET_METADATA_DRIFT")
        checkrefs=[]
        expected_rows=0
        for idx in range(100):
            budget()
            seg=idx//25+1;k=idx%25
            if mode=="synthetic":
                raw,meta=fabricated_shard(seg,k,master,digits)
                # SAME real cryptographic envelope and decoder adapter on fabricated bytes.
                encrypted=tmp/"synthetic-input.mxmenc"
                encrypt_shard(raw,public_key=public,output=encrypted)
                blob=encrypted.read_bytes();meta["ENCRYPTED_ASSET_SHA256"]=sha(blob)
                raw=crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp)
                encrypted.unlink(missing_ok=True)
            else:
                meta=entries[idx]
                asset=assets[meta["ENCRYPTED_ASSET_NAME"]]
                blob=download(asset["browser_download_url"],asset["size"])
                need(len(blob)==asset["size"] and sha(blob)==meta["ENCRYPTED_ASSET_SHA256"],"INPUT_CIPHERTEXT_DRIFT")
                raw=crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp)
            expected_rows+=meta["ROW_COUNT"]
            num.consume_shard(engine,raw,meta,master,digits,ciphertext=blob)
            del raw,blob
            if k==24:
                # Persist only private encrypted state and independently read it back.
                mark=store.encrypted(engine,f"numeric-segment-{seg:02d}.mxmenc")
                checkrefs.append({x:mark[x] for x in ("id","name","size","ciphertext_sha256","canonical_sha256","gzip_sha256","url")})
                # Confirm machine-side resume compatibility from ACTUAL remote ciphertext.
                if seg==2:engine=store.restore(mark)
                need(engine["next_shard"]==seg*25,"CHECKPOINT_RESUME_DRIFT")
                print(json.dumps({"checkpoint_segment":seg,"encrypted_remote_readback":"PASS",
                     "processed_shards":engine["next_shard"],"resources":usage()},sort_keys=True),flush=True)
        if mode=="real":need(expected_rows==num.EXPECTED_ROWS,"HISTORICAL_ROW_COUNT_DRIFT")
        report=num.finish(engine,expected_rows)
        # Only encrypted storage receives numeric results, including all unsupported evidence.
        final=store.encrypted(report,"full-frontier-numeric-response.mxmenc")
        budget()
        publicdoc={"schema":SCHEMA,"phase":"FINAL","status":"PASS","source_head":head,
            "scientific_design_sha256":num.DESIGN_SHA,
            "worker_sha256":filehash(WORKER_PATH),"input_manifest_sha256":num.MANIFEST_SHA,
            "run_id":int(os.environ["GITHUB_RUN_ID"]),"identity_count":1576,
            "input_shard_count":100,"encrypted_artifact_name":final["name"],
            "encrypted_artifact_sha256":final["ciphertext_sha256"],
            "resource_cpu_seconds":usage()["cpu_seconds"],
            "resource_wall_seconds":usage()["wall_seconds"],
            "resource_peak_ram_kib":usage()["peak_kib"],"failure_code":"NONE"}
        # Synthetic PASS is allowed only AFTER all 4 encrypted checkpoint and final readbacks.
        if mode=="synthetic":
            publication=store.publish(publicdoc,PUBLIC_ROOT+"INTEGRATED_SYNTHETIC_RESULT_V1.json")
            print(json.dumps({"status":"PASS_FULL_1576_SYNTHETIC_INTEGRATED",
                "source_head":head,"published_head":publication["head"],
                "public_sha256":publication["public_sha256"],"encrypted_checkpoints":checkrefs,
                "result_ciphertext_sha256":final["ciphertext_sha256"],
                "results":"FABRICATED_ONLY_NO_REAL_MARKET_RESPONSE",
                "rows":engine["rows"],"usage":usage()},sort_keys=True),flush=True)
        else:
            publication=store.publish(publicdoc,PUBLIC_ROOT+"REAL_DEVELOPMENT_RESULT_V1.json")
            print(json.dumps({"status":"REAL_DEVELOPMENT_ENCRYPTED_NO_PUBLIC_NUMERICS",
                "published_head":publication["head"],"encrypted_checkpoints":checkrefs,
                "result_ciphertext_sha256":final["ciphertext_sha256"],"usage":usage()},sort_keys=True),flush=True)
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--synthetic",action="store_true")
    parser.add_argument("--real",action="store_true")
    args=parser.parse_args()
    try:
        need(args.real != args.synthetic,"MODE_MUST_BE_EXPLICIT")
        run("synthetic" if args.synthetic else "real")
    except Exception as e:
        code=e.args[0] if isinstance(e,num.NumericalStop) and e.args else "FAIL_CLOSED"
        print(json.dumps({"status":"FAIL_CLOSED","code":str(code),"resource":usage(),
                          "no_automatic_retry":True,"no_real_market_data_disclosed":True}),flush=True)
        raise SystemExit(2) from None

if __name__=="__main__":main()
