"""Read already-completed encrypted results and relay *aggregates only* to private chat recipient.
NO broker access, NO new experiment, NO model fitting, NO plain numeric logs or publication.
"""
import os,sys,re,json,math,gzip,base64,hashlib,tempfile,pathlib
from collections import Counter
from datetime import datetime,timezone
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
e=rt.e
P="research_core_v4/secure_two_liquidity_readback_v1/"
PHASE="GATE"
def need(test,code):
 if not test:raise RuntimeError(code)
def sha(buf):return hashlib.sha256(buf).hexdigest()
def source_read(key,fp,tmp,source):
 result,meta=load_asset(key,fp,tmp,source["primary"])
 att,ameta=load_asset(key,fp,tmp,source["attestation"])
 need(att["primary"]["ciphertext_sha256"]==source["primary"]["ciphertext_sha256"],"PRIMARY_ATTESTED_CIPHER_DRIFT")
 need(att["primary"]["canonical_sha256"]==meta["canonical_sha256"],"PRIMARY_ATTESTED_CANONICAL_DRIFT")
 need(att["primary"]["name"]==source["primary"]["name"],"PRIMARY_NAME_DRIFT")
 need(att["schema"]=="mxm.owner.frontier.attestation.v1","ATTESTATION_SCHEMA_DRIFT")
 need(att["summary"]["source_head"]==source["head"] and result["summary"]["source_head"]==source["head"],"SOURCE_HEAD_DRIFT")
 need(att["summary"]["run_id"]==source["run"],"RUN_ID_DRIFT")
 delivered={k:v for k,v in att["summary"].items() if k not in ("durable_primary","run_id")}
 need(e.a.enc(delivered)==e.a.enc(result["summary"]),"ATTESTED_SUMMARY_DRIFT")
 original=e.w.old.api("actions/runs/"+str(source["run"]))
 need(original["status"]=="completed" and original["conclusion"]=="success" and original["head_sha"]==source["head"],"ORIGINAL_RUN_NOT_ACCEPTED")
 need(original["run_attempt"]==1,"ORIGINAL_RUN_ATTEMPT_DRIFT")
 return result,{"original_run":source["run"],"original_head":source["head"],"cipher_sha256":meta["ciphertext_sha256"],"canonical_sha256":meta["canonical_sha256"],"attestation_sha256":ameta["ciphertext_sha256"]}
def distribution(values):
 values=sorted(float(x) for x in values if x is not None and isinstance(x,(int,float)) and math.isfinite(x))
 if not values:return {"n":0}
 n=len(values)
 return {"n":n,"min":values[0],"median":values[(n-1)//2],"p05":values[math.ceil(.05*n)-1],"p95":values[math.ceil(.95*n)-1],"max":values[-1],"mean":sum(values)/n}
def paired(rows,reason="PAIRED_SUPPORTED"):
 selected=[x for x in rows if x["reason"]==reason]
 b=[(x["baseline_spread_bps"]-x["future_authentic_spread_bps"])**2 for x in selected]
 m=[(x["model_spread_bps"]-x["future_authentic_spread_bps"])**2 for x in selected]
 return {"n":len(selected),"baseline_mse_bps2":sum(b)/len(b) if b else None,"model_mse_bps2":sum(m)/len(m) if m else None,"increment_mse_bps2":sum(x-y for x,y in zip(b,m))/len(b) if b else None}
def summarize_broker(data):
 summary=data["summary"];allrows=data["all_predeclared_events"];rawquotes=data["private_historical_ticks"]
 need(len(allrows)==32*len(summary["current_contracts"]),"BROKER_SCHEDULED_COHORT")
 clock_keys={(int(z["symbol_id"]),z["timestamp_utc"]) for z in rawquotes}
 need(len(clock_keys)==len(rawquotes),"BROKER_ORIGINAL_QUOTE_KEYS")
 ages=[];age_by_side={"bid":[],"ask":[]};invalid=Counter()
 for q in rawquotes:
  for side,v in q["sides"].items():
   invalid[side+"|"+v["state"]]+=1
   if v["state"]=="VALID":
    ages.append(v["age_ms"]);age_by_side[side].append(v["age_ms"])
 orig=summary["new_experiment"]
 safe={
 "selected_current_contracts":summary["current_contracts"],
 "universe":summary["price_blind_universe"],
 "authentic_quote_capture":summary["native_capture"],
 "scheduled_action_count":len(allrows),
 "quote_boundary_count":len(rawquotes),
 "quote_side_states":dict(invalid),
 "quote_age_ms":distribution(ages),
 "quote_age_per_side_ms":{side:distribution(v) for side,v in age_by_side.items()},
 "recorded_original_numeric_summary":orig,
 "future_spread_distribution_bps_all_labels":distribution([x["future_authentic_spread_bps"] for x in allrows]),
 "future_spread_distribution_bps_paired":distribution([x["future_authentic_spread_bps"] for x in allrows if x["reason"]=="PAIRED_SUPPORTED"]),
 "age5s_fresh_paired":paired([x for x in allrows if x["all_quote_ages_le5sec"]]),
 "age5s_stale_or_partially_old_paired":paired([x for x in allrows if not x["all_quote_ages_le5sec"]]),
 "original_four_block_reducer_check":[],
 "original_iso_reducer_check":[]
 }
 for item in orig["four_original_blocks"]:
  calc=paired([x for x in allrows if x["block"]==item["block"]])
  need(calc["n"]==item["paired_supported"],"ORIGINAL_BLOCK_COVERAGE_DRIFT")
  safe["original_four_block_reducer_check"].append({"block":item["block"],**calc})
 for item in orig["iso_utc"]:
  w=item["week"];calc=paired([x for x in allrows if x["iso_utc"]==w])
  need(calc["n"]==item["paired_supported"],"ORIGINAL_ISO_COVERAGE_DRIFT")
  safe["original_iso_reducer_check"].append({"week":w,"complete_iso_week":item["complete_iso_week"],**calc})
 return safe
def summarize_cross(data,broker):
 summary=data["summary"];rows=data["all_private_paired_cross_asset_trials"];orig=summary["new_actual_numeric"]
 need(len(rows)==broker["scheduled_action_count"],"CROSS_COHORT_SOURCE_DRIFT")
 reasons=Counter(x["reason"] for x in rows)
 peers=distribution([x["peer_count"] for x in rows])
 overlap={x["action_utc"] for x in rows}
 return {
 "source_original_ciphertext":summary["underlying_quote_provenance"],
 "native_broker_reacquisitions":summary["new_broker_requests"],
 "scheduled":len(rows),
 "original_action_clocks":len(overlap),
 "missingness":dict(reasons),
 "cross_class_peer_counts":peers,
 "original_numeric_cross_asset_summary":orig,
 "original_own_model_paired_baseline_identity":"PERSISTED_ORIGINAL_OWN_MODEL_FORECAST_NO_REMODEL",
 "cohort_retention_against_first_experiment":(orig["all"]["paired"]/broker["recorded_original_numeric_summary"]["global"]["paired_supported"] if broker["recorded_original_numeric_summary"]["global"]["paired_supported"] else None),
 "all_old_files_and_closed_exacts_untouched":True
 }
def guard(envelope,recipient_hex,head):
 need(set(envelope)=={"version","head","recipient_pub_sha256","wrapped_key_b64","nonce_b64","ciphertext_b64","compressed_plain_sha256","source_cipher_sha256"},"ENVELOPE_FIELD_GUARD")
 need(envelope["version"]=="MXM_EPHEMERAL_RSA_OAEP_AES256GCM_V1" and envelope["head"]==head and envelope["recipient_pub_sha256"]==recipient_hex,"ENVELOPE_IDENTITY")
 for field in ("wrapped_key_b64","nonce_b64","ciphertext_b64"):
  need(type(envelope[field]) is str and 0<len(envelope[field])<150000 and re.fullmatch("[A-Za-z0-9+/]+={0,2}",envelope[field]),"ENVELOPE_CIPHER_ONLY")
 need(len(envelope["source_cipher_sha256"])==2 and all(re.fullmatch("[0-9a-f]{64}",v) for v in envelope["source_cipher_sha256"]),"SOURCE_CIPHERS")
 payload=json.dumps(envelope,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
 need(len(payload)<150000,"ENVELOPE_SIZE_BUDGET")
 return payload
def main():
 global PHASE
 os.umask(0o077);head=os.environ["GITHUB_SHA"];e.w.v2.runtime(head)
 a=json.loads((e.a.ROOT/(P+"EXECUTION_V1.json")).read_text())
 need(os.environ.get("GITHUB_EVENT_NAME")=="push" and os.environ.get("GITHUB_WORKFLOW_REF")==e.w.old.REPO+"/.github/workflows/mxm-secure-two-liquidity-readback-v1.yml@refs/heads/"+e.w.old.BRANCH,"WORKFLOW_SCOPE")
 need(a["orders"] is False and a["protected_forward"] is False and a["new_market_requests"] is False and a["scientific_replay"] is False,"READBACK_SCOPE")
 e.a.ancestor(a["base_head"],head)
 for path,h in a["bindings"].items():need(e.w.old.filehash(path)==h,"FROZEN_SOURCE_BINDING")
 orig=json.loads((e.a.ROOT/(e.P+"EXACT_COVERAGE_PREARM_V1.json")).read_text())
 for path,h in orig["bindings"].items():need(e.w.old.filehash(path)==h,"ORIGINAL_HISTORICAL_BINDING")
 tag="mxm-owner-secure-private-readback-"+a["invocation_id"]
 need(not e.w.v2.existing_ref(tag),"ONE_USE_READBACK_ALREADY_CLAIMED")
 e.w.old.api("git/refs",{"ref":"refs/tags/"+tag,"sha":head})
 recipient=(e.a.ROOT/(P+"RECIPIENT_PUBLIC_KEY.pem")).read_bytes()
 need(sha(recipient)==a["recipient_public_key_sha256"],"RECIPIENT_KEY_DRIFT")
 from cryptography.hazmat.primitives.asymmetric import rsa
 public_key=serialization.load_pem_public_key(recipient)
 need(isinstance(public_key,rsa.RSAPublicKey) and public_key.key_size>=3072,"WEAK_RECIPIENT_KEY")
 with tempfile.TemporaryDirectory(prefix="mxm-existing-readback-",dir=os.environ["RUNNER_TEMP"]) as directory:
  PHASE="EXACT_PRIOR_CIPHER_AUTHENTICATION"
  tmp=pathlib.Path(directory);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,"EXISTING_OWNER_KEY_DRIFT")
  broker,p1=source_read(key,fp,tmp,a["broker"])
  cross,p2=source_read(key,fp,tmp,a["cross"])
  need(cross["summary"]["underlying_quote_provenance"]["ciphertext_sha256"]==p1["cipher_sha256"],"CROSS_ORIGINAL_CIPHER_PROVENANCE")
  PHASE="NONREPLAY_EXISTING_RESULT_AGGREGATION"
  b=summarize_broker(broker);c=summarize_cross(cross,b)
  document={"schema":"mxm.private.recovered.two.liquidity.aggregate.report.v1","readback_source_head":head,"scope":"EXISTING_ENCRYPTED_RESULTS_ONLY_NO_NEW_BROKER_REQUESTS_OR_REPLAY","broker_provenance":p1,"cross_provenance":p2,"broker_liquidity":b,"cross_asset_liquidity":c,"execution_trades":0,"net_certified":False,"HARD21_certified":False,"independent_confirmation":False,"all_old_sources_untouched":True}
  raw=json.dumps(document,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()
  need(len(raw)<180000,"PRIVATE_REPORT_SIZE_BUDGET")
  compressed=gzip.compress(raw,mtime=0)
  aes=os.urandom(32);iv=os.urandom(12)
  ciphertext=AESGCM(aes).encrypt(iv,compressed,head.encode())
  wrapped=public_key.encrypt(aes,padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
  b64=lambda v:base64.b64encode(v).decode("ascii")
  envelope={"version":"MXM_EPHEMERAL_RSA_OAEP_AES256GCM_V1","head":head,"recipient_pub_sha256":sha(recipient),"wrapped_key_b64":b64(wrapped),"nonce_b64":b64(iv),"ciphertext_b64":b64(ciphertext),"compressed_plain_sha256":sha(compressed),"source_cipher_sha256":[p1["cipher_sha256"],p2["cipher_sha256"]]}
  PHASE="PUBLIC_CIPHERTEXT_ONLY_GUARD"
  body=guard(envelope,a["recipient_public_key_sha256"],head)
  PHASE="CIPHERTEXT_PUBLICATION_WITH_PRIVATE_RECIPIENT"
  release=e.w.old.api("releases",{"tag_name":"mxm-private-relay-only-"+a["invocation_id"]+"-"+os.environ["GITHUB_RUN_ID"],"target_commitish":head,"name":"MXM double liquidity aggregate ciphertext-only owner readback","prerelease":True,"body":body.decode()})
  found=e.w.old.api("releases/"+str(release["id"]))
  need(found["body"]==body.decode(),"CIPHERTEXT_REMOTE_READBACK")
  print(json.dumps({"schema":"mxm.private.ciphertext.relay.public.status.v1","status":"PASS","run_id":int(os.environ["GITHUB_RUN_ID"]),"release_id":release["id"],"recipient_key_sha256":a["recipient_public_key_sha256"],"cipher_envelope_sha256":sha(body),"historical_market_requests":0,"model_replays":0,"numeric_plaintext_publication":False},sort_keys=True),flush=True)
if __name__=="__main__":
 try:main()
 except Exception as ex:
  print("FAIL_CLOSED_SECURE_READBACK_"+PHASE+"_"+type(ex).__name__,flush=True)
  raise SystemExit(2) from None
