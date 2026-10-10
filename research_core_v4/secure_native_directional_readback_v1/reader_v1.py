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
P="research_core_v4/secure_native_directional_readback_v1/"
PHASE="SOURCE_AUTHENTICATION"
def need(ok,code):
 if not ok:raise RuntimeError(code)
def digest(x):return hashlib.sha256(x).hexdigest()
def main():
 global PHASE
 os.umask(0o077);head=os.environ["GITHUB_SHA"];e.w.v2.runtime(head)
 auth=json.loads((e.a.ROOT/(P+"EXECUTION_V1.json")).read_text())
 need(os.environ.get("GITHUB_EVENT_NAME")=="push" and os.environ.get("GITHUB_WORKFLOW_REF")==e.w.old.REPO+"/.github/workflows/mxm-secure-native-directional-readback-v1.yml@refs/heads/"+e.w.old.BRANCH,"WORKFLOW_SCOPE")
 need(auth["orders"] is False and auth["new_broker_requests"] is False and auth["model_replay"] is False and auth["protected_forward"] is False,"FORBIDDEN_OPERATION")
 e.a.ancestor(auth["base_head"],head)
 for p,h in auth["bindings"].items():need(e.w.old.filehash(p)==h,"SOURCE_SHA256")
 original=json.loads((e.a.ROOT/(e.P+"EXACT_COVERAGE_PREARM_V1.json")).read_text())
 for p,h in original["bindings"].items():need(e.w.old.filehash(p)==h,"ORIGINAL_FROZEN_DRIFT")
 tag="mxm-owner-native-directional-private-readback-"+auth["invocation_id"]
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
  need(summary["schema"]=="mxm.private.authentic.native.update.asymmetry.directional.development.v1","EXPERIMENT_ID")
  need(summary["native_broker_requests"]<=1300 and summary["selected_count"]<=5,"EXPERIMENT_REQUEST_OR_UNIVERSE_DRIFT")
  need(summary["real_orders"]==0 and summary["demo_orders"]==0 and not summary["protected_forward"],"NO_ORDER_EVIDENCE")
  trials=full["private_fixed_event_outcomes"];q=full["private_original_bid_ask_tick_pages"]
  need(len(q)==summary["quote_boundaries_attempted"],"ORIGINAL_QUOTE_COUNT")
  need(len(trials)==summary["real_directional_numeric"]["global"]["scheduled"],"ORIGINAL_ACTION_DENOMINATOR")
  need(sum(x["reason"]=="SUPPORTED" for x in trials)==summary["real_directional_numeric"]["global"]["supported"],"ORIGINAL_PAIR_DENOMINATOR")
  for block in summary["real_directional_numeric"]["four_original_blocks"]:
   rows=[x for x in trials if x["block"]==block["block"]]
   need(block["scheduled"]==len(rows) and block["supported"]==sum(x["reason"]=="SUPPORTED" for x in rows),"FOUR_BLOCK_COUNT_DRIFT")
  need(len(summary["real_directional_numeric"]["four_original_blocks"])==4,"ORIGINAL_BLOCKS_REQUIRED")
  need(summary["real_directional_numeric"]["global"]["supported"]<=summary["real_directional_numeric"]["global"]["scheduled"],"PAIR_SUPPORT")
  PHASE="PRIVATE_AGGREGATE_RELAY"
  safe={"schema":"mxm.owner.private.native.directional.exact.readback.v1","original_provenance":proof,"numeric_source_summary":summary,"recomputed_only_counts":{"event_rows":len(trials),"authentic_quote_boundaries":len(q)},"broker_calls_during_readback":0,"models_replayed":0,"historical_M5_shards_downloaded":0,"fills":0,"net_certified":False,"HARD21_certified":False}
  raw=json.dumps(safe,sort_keys=True,separators=(",",":"),allow_nan=False,ensure_ascii=True).encode()
  need(len(raw)<180000,"PRIVATE_AGGREGATE_BUDGET")
  compressed=gzip.compress(raw,mtime=0)
  aes=os.urandom(32);nonce=os.urandom(12)
  ct=AESGCM(aes).encrypt(nonce,compressed,head.encode())
  wrapped=pub.encrypt(aes,padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
  b64=lambda v:base64.b64encode(v).decode("ascii")
  envelope={"version":"MXM_OWNER_EPHEMERAL_NATIVE_DIRECTIONAL_AES256GCM_V1","head":head,"recipient_pub_sha256":digest(recipient),"nonce_b64":b64(nonce),"wrapped_key_b64":b64(wrapped),"ciphertext_b64":b64(ct),"compressed_plain_sha256":digest(compressed),"original_cipher_sha256":proof["cipher_sha256"]}
  body=json.dumps(envelope,sort_keys=True,separators=(",",":"),ensure_ascii=True)
  need(len(body)<160000 and not any(x in body for x in ['EURUSD','USDJPY','mean_quote_side','model_bps','selected_current_contracts','private_fixed_event_outcomes']),"PUBLIC_CIPHERTEXT_ONLY")
  rel=e.w.old.api("releases",{"tag_name":"mxm-private-native-directional-aggregate-"+auth["invocation_id"]+"-"+os.environ["GITHUB_RUN_ID"],"target_commitish":head,"name":"MXM encrypted owner-only directional aggregates","body":body,"prerelease":True})
  remote=e.w.old.api("releases/"+str(rel["id"]))
  need(remote["body"]==body,"REMOTE_ENVELOPE_INTEGRITY")
  print(json.dumps({"schema":"mxm.owner.only.readback.status.v1","status":"PASS","run_id":int(os.environ["GITHUB_RUN_ID"]),"release_id":rel["id"],"head":head,"ciphertext_envelope_sha256":digest(body.encode()),"private_aggregate_plaintext_public":False,"new_market_requests":0,"scientific_replay":0,"orders":0},sort_keys=True),flush=True)
if __name__=="__main__":
 try:main()
 except Exception as exc:
  print("FAIL_CLOSED_NATIVE_PRIVATE_READBACK_"+PHASE+"_"+type(exc).__name__,flush=True)
  raise SystemExit(2) from None
