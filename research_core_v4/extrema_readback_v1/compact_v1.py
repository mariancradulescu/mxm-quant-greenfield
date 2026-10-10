"""Compact transport of one EXISTING authenticated H1 result, no model replay.
Provides dense encrypted aggregate to a private ephemeral RSA recipient; never
publishes numerical market measurements in the public repo or logs.
"""
import base64,gzip,hashlib,json,math,os,pathlib,subprocess,tempfile
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
e=rt.e
ROOT="research_core_v4/extrema_readback_v1/"
WORKFLOW=".github/workflows/mxm-extrema-compact-transport-v1.yml"
def need(x,code):
 if not x:raise RuntimeError(code)
def sha(x):return hashlib.sha256(x).hexdigest()
def pack(w):
 return [w["calendar"],w["eligible_pair"],w["supported"],
         w["new_gross_sum_bps"],w["baseline_gross_sum_bps"],
         w["new_positive"],w["baseline_positive"]]
def main():
 os.umask(0o077)
 head=os.environ["GITHUB_SHA"];e.w.v2.runtime(head)
 auth=json.loads((e.a.ROOT/(ROOT+"COMPACT_EXECUTION_V1.json")).read_text())
 need(os.environ.get("GITHUB_EVENT_NAME")=="push" and
      os.environ.get("GITHUB_WORKFLOW_REF")==e.w.old.REPO+"/"+WORKFLOW+"@refs/heads/"+e.w.old.BRANCH,"WORKFLOW_SCOPE")
 need(auth["no_scientific_replay"] is True and auth["broker_requests"]==0 and auth["orders"] is False and auth["protected_forward"] is False,"SCOPE")
 e.a.ancestor(auth["base_head"],head)
 for p,h in auth["sha1_sources"].items():
  got=subprocess.check_output(["git","hash-object",p],cwd=e.a.ROOT,text=True).strip()
  need(got==h,"SOURCE_DRIFT")
 need(e.w.old.api("git/ref/heads/"+e.w.old.BRANCH)["object"]["sha"]==head,"HEAD_DRIFT")
 tag="mxm-extrema-h1-private-compact-"+auth["invocation_id"]
 need(not e.w.v2.existing_ref(tag),"ONE_USE")
 e.w.old.api("git/refs",{"ref":"refs/tags/"+tag,"sha":head})
 rec=(e.a.ROOT/(ROOT+"RECIPIENT_PUBLIC_KEY.pem")).read_bytes()
 need(sha(rec)==auth["recipient_sha256"],"KEY_ID")
 pub=serialization.load_pem_public_key(rec)
 with tempfile.TemporaryDirectory(prefix="mxm-h1-compact-",dir=os.environ["RUNNER_TEMP"]) as td:
  tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp)
  need(fp==e.w.old.FP,"EXISTING_PRIVATE_KEY")
  a=auth["source"];p,pm=load_asset(key,fp,tmp,a["primary"]);t,tm=load_asset(key,fp,tmp,a["attestation"])
  need(t["primary"]["ciphertext_sha256"]==pm["ciphertext_sha256"] and
       t["primary"]["canonical_sha256"]==pm["canonical_sha256"] and
       t["schema"]=="mxm.owner.frontier.attestation.v1","ATTESTED_SOURCE")
  att=dict(t["summary"])
  need(att.pop("source_head")==a["head"] and att.pop("run_id")==a["run"],"ORIGINAL_RUN")
  att.pop("durable_primary")
  need(e.a.enc(att)==e.a.enc(p["summary"]),"ATTESTED_SUMMARY")
  s=p["summary"]
  need(s["schema"]=="mxm.private.authentic.extrema.order.development.v1" and
       s["new_exact"]=="H1_EXTREMA_TEMPORAL_PRECEDENCE_FIXED_DIRECTION_V1","ORIGINAL_EXACT")
  need(s["identities"]==1576 and s["shards"]==100 and s["authentic_m5_rows"]==3355389,"INPUT")
  weeks=[pack(w) for w in s["four_weeks"]]
  iso={k:pack(v) for k,v in sorted(s["iso_utc"].items())}
  classes={k:[pack(w) for w in blocks] for k,blocks in sorted(s["all_classes"].items())}
  need(len(weeks)==4 and sum(x[0] for x in weeks)==264768 and
       sum(x[0] for x in iso.values())==264768 and
       sum(sum(x[0] for x in blocks) for blocks in classes.values())==264768,"DENOMINATOR")
  need(sum(x[2] for x in weeks)==sum(x[2] for x in iso.values())==
       sum(sum(x[2] for x in blocks) for blocks in classes.values()),"PAIRED_COUNT")
  reasons={}
  for w in s["four_weeks"]:
   for k,v in w["reason_counts"].items():reasons[k]=reasons.get(k,0)+v
  class_identities={}
  for x in p["all_identities"]:
   cl=x["asset_class"];class_identities[cl]=class_identities.get(cl,0)+1
  need(len(p["all_identities"])==1576 and sum(class_identities.values())==1576,"CLASS_IDENTITIES")
  report={"schema":"mxm.private.h1.compact.numeric.v1",
    "metric_order":["scheduled","eligible","paired_supported","model_gross_sum_bps","baseline_gross_sum_bps","model_positive_count","baseline_positive_count"],
    "weeks":weeks,"iso":iso,"classes":classes,"class_identities":class_identities,"missing_reasons":reasons,
    "source":{"run":a["run"],"head":a["head"],"release":a["release_id"],"primary_sha256":pm["ciphertext_sha256"],"attestation_sha256":tm["ciphertext_sha256"]},
    "cost_sensitivities_bps":[2,5,10],
    "original_scope":"ALL1576_ALL4_BLOCKS_NO_POST_SELECTION_M5_REFERENCE_GROSS_NOT_NET",
    "original_replay":False,"historical_shards_opened":0,"new_broker_requests":0,"orders":0,"protected_forward":False}
  raw=json.dumps(report,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()
  packed=gzip.compress(raw,mtime=0);aes=os.urandom(32);iv=os.urandom(12)
  cipher=AESGCM(aes).encrypt(iv,packed,head.encode())
  wrapped=pub.encrypt(aes,padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
  b64=lambda z:base64.b64encode(z).decode("ascii")
  env={"version":"MXM_H1_COMPACT_PRIVATE_RSA_AESGCM_V1","head":head,
       "wrapped_key_b64":b64(wrapped),"nonce_b64":b64(iv),"ciphertext_b64":b64(cipher),
       "compressed_sha256":sha(packed),"recipient_pub_sha256":sha(rec),
       "original_cipher_sha256":pm["ciphertext_sha256"]}
  body=json.dumps(env,sort_keys=True,separators=(",",":"),ensure_ascii=True)
  need(len(body)<19000 and not any(k in body for k in ("model_gross_sum_bps","paired_supported","missing_reasons")),"PUBLIC_ONLY_CIPHER")
  r=e.w.old.api("releases",{"tag_name":"mxm-h1-compact-private-"+auth["invocation_id"]+"-"+os.environ["GITHUB_RUN_ID"],
        "target_commitish":head,"name":"MXM H1 original numeric compact encrypted delivery only",
        "prerelease":True,"body":body})
  need(e.w.old.api("releases/"+str(r["id"]))["body"]==body,"PUBLISHED_CIPHER_READBACK")
  print(json.dumps({"status":"PASS","source_run":a["run"],"relay_run":int(os.environ["GITHUB_RUN_ID"]),
      "relay_release_id":r["id"],"cipher_body_sha256":sha(body.encode()),
      "private_numbers_public":False,"broker_requests":0,"archive_replay":0,"orders":0},sort_keys=True),flush=True)
if __name__=="__main__":
 try:main()
 except Exception as ex:
  print("FAIL_CLOSED_COMPACT_H1_READBACK_"+type(ex).__name__,flush=True)
  raise SystemExit(2) from None
