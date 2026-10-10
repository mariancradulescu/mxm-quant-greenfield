"""Read one completed owner-encrypted NEW directional result; private-only one-use relay.
No fresh ticks, experiments, model calls or raw market data in public output.
"""
import os,json,math,gzip,hashlib,base64,pathlib,tempfile,re
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding,rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.secure_two_liquidity_readback_v1.runner_v1 import source_read
e=rt.e
P="research_core_v4/cloud_native_covariance_readback_v1/"
PHASE="SOURCE_AUTHENTICATION"
def need(ok,code):
 if not ok:raise RuntimeError(code)
def digest(x):return hashlib.sha256(x).hexdigest()
def main():
 global PHASE
 os.umask(0o077);head=os.environ["GITHUB_SHA"];e.w.v2.runtime(head)
 auth=json.loads((e.a.ROOT/(P+"EXECUTION_V1.json")).read_text())
 need(os.environ.get("GITHUB_EVENT_NAME")=="push" and os.environ.get("GITHUB_WORKFLOW_REF")==e.w.old.REPO+"/.github/workflows/mxm-cloud-native-covariance-readback-v1.yml@refs/heads/"+e.w.old.BRANCH,"WORKFLOW_SCOPE")
 need(auth["orders"] is False and auth["new_broker_requests"] is False and auth["model_replay"] is False and auth["protected_forward"] is False,"FORBIDDEN_OPERATION")
 e.a.ancestor(auth["base_head"],head)
 for p,h in auth["bindings"].items():need(e.w.old.filehash(p)==h,"SOURCE_SHA256")
 original=json.loads((e.a.ROOT/(e.P+"EXACT_COVERAGE_PREARM_V1.json")).read_text())
 for p,h in original["bindings"].items():need(e.w.old.filehash(p)==h,"ORIGINAL_FROZEN_DRIFT")
 tag="mxm-owner-cloud-native-private-readback-"+auth["invocation_id"]
 need(not e.w.v2.existing_ref(tag),"ONE_USE_READBACK")
 e.w.old.api("git/refs",{"ref":"refs/tags/"+tag,"sha":head})
 recipient=(e.a.ROOT/(P+"RECIPIENT_PUBLIC_KEY.pem")).read_bytes()
 need(digest(recipient)==auth["recipient_public_key_sha256"],"RECIPIENT_FINGERPRINT")
 pub=serialization.load_pem_public_key(recipient)
 need(isinstance(pub,rsa.RSAPublicKey) and pub.key_size>=3072,"RECIPIENT_STRENGTH")
 with tempfile.TemporaryDirectory(prefix="mxm-new-directional-readback-",dir=os.environ["RUNNER_TEMP"]) as directory:
  PHASE="EXISTING_CIPHERTEXT_ONLY"
  tmp=pathlib.Path(directory);key,fp=e.w.old._private_key_from_secret(tmp)
  need(fp==e.w.old.FP,"OWNER_KEY_FINGERPRINT")
  full,proof=source_read(key,fp,tmp,auth["source"])
  summary=full["summary"]
  need(summary["schema"]=="mxm.private.cloud.native.spread.midpoint.covariance.v1","NEW_EXPERIMENT_ID")
  need(summary["orders"]==0 and summary["demo_orders"]==0 and not summary["protected_forward"] and not summary["cloud_deployment"],"NO_ORDER_DEPLOY_EVIDENCE")
  trials=full["private_event_outcomes"];raw_quotes=full["private_bid_ask_pages"];samples=full["private_identical_csharp_python_samples"]
  need(len(trials)==64*len(summary["selected_contracts"]),"FROZEN_ACTION_DENOMINATOR")
  need(len(trials)==summary["numeric"]["global"]["scheduled"],"ORIGINAL_ACTION_DENOMINATOR")
  need(sum(x["reason"]=="SUPPORTED" for x in trials)==summary["numeric"]["global"]["paired"],"PAIRED_COUNT")
  need(summary["csharp_python_parity"]["samples"]==len(samples),"AUTHENTIC_PARITY_COUNT")
  need(summary["native_requests"]<=10000,"REQUEST_LIMIT")
  from research_core_v4.cloud_native_covariance_v1.runner_v1 import aggregate
  need(aggregate(trials)==summary["numeric"],"ORIGINAL_ALL_NUMERIC_REDUCERS")
  # This is a reducer/authentication check, no market reacquisition and no refitted model.
  safe={"schema":"mxm.owner.authenticated.completed.cloud.native.readback.v1","original_provenance":proof,"numeric_source_summary":summary,"authenticated_event_count":len(trials),"authenticated_quote_boundary_count":len(raw_quotes),"authenticated_parity_input_count":len(samples),"broker_calls_during_readback":0,"new_experiments":0,"fills":0,"net_certified":False,"HARD21_certified":False}
  raw=json.dumps(safe,sort_keys=True,separators=(",",":"),allow_nan=False,ensure_ascii=True).encode()
  need(len(raw)<300000,"PRIVATE_AGGREGATE_BUDGET")
  compressed=gzip.compress(raw,mtime=0)
  aes=os.urandom(32);nonce=os.urandom(12)
  ct=AESGCM(aes).encrypt(nonce,compressed,head.encode())
  wrapped=pub.encrypt(aes,padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
  b64=lambda v:base64.b64encode(v).decode("ascii")
  envelope={"version":"MXM_OWNER_EPHEMERAL_NATIVE_DIRECTIONAL_AES256GCM_V1","head":head,"recipient_pub_sha256":digest(recipient),"nonce_b64":b64(nonce),"wrapped_key_b64":b64(wrapped),"ciphertext_b64":b64(ct),"compressed_plain_sha256":digest(compressed),"original_cipher_sha256":proof["cipher_sha256"]}
  body=json.dumps(envelope,sort_keys=True,separators=(",",":"),ensure_ascii=True)
  need(len(body)<160000 and not any(x in body for x in ['EURUSD','USDJPY','mean_quote_side','model_bps','selected_current_contracts','private_fixed_event_outcomes']),"PUBLIC_CIPHERTEXT_ONLY")
  rel=e.w.old.api("releases",{"tag_name":"mxm-private-cloud-native-verified-aggregate-"+auth["invocation_id"]+"-"+os.environ["GITHUB_RUN_ID"],"target_commitish":head,"name":"MXM encrypted owner-only directional aggregates","body":body,"prerelease":True})
  remote=e.w.old.api("releases/"+str(rel["id"]))
  need(remote["body"]==body,"REMOTE_ENVELOPE_INTEGRITY")
  print(json.dumps({"schema":"mxm.owner.only.cloud.native.readback.status.v1","status":"PASS","run_id":int(os.environ["GITHUB_RUN_ID"]),"release_id":rel["id"],"head":head,"ciphertext_envelope_sha256":digest(body.encode()),"private_aggregate_plaintext_public":False,"new_market_requests":0,"scientific_replay":0,"orders":0},sort_keys=True),flush=True)
if __name__=="__main__":
 try:main()
 except Exception as exc:
  print("FAIL_CLOSED_NATIVE_PRIVATE_READBACK_"+PHASE+"_"+type(exc).__name__,flush=True)
  raise SystemExit(2) from None
