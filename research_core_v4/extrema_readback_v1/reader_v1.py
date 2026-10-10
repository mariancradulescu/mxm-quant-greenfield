"""Private H1 extrema readback: ONLY decrypt already completed encrypted result
and its attestation, verify stored summary arithmetic, relay aggregate via
ephemeral RSA/AES-GCM recipient. Never read 100 source shards or replay model.
Public release body and runner logs contain ciphertext/metadata ONLY.
"""
import base64,gzip,hashlib,json,math,os,pathlib,re,tempfile,subprocess
from collections import Counter
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding,rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
e=rt.e
P="research_core_v4/extrema_readback_v1/"
W=".github/workflows/mxm-extrema-readback-v1.yml"
PHASE="AUTHENTICATION"

def need(v,code):
    if not v:raise RuntimeError(code)
def sha(x):return hashlib.sha256(x).hexdigest()
def finite(v):return isinstance(v,(int,float)) and math.isfinite(v)
def nearly(a,b):
    if a is None or b is None:return a is b
    return finite(a) and finite(b) and abs(a-b)<=1e-8*max(1.0,abs(a),abs(b))
def digest_metrics(wks):
    names=("calendar","eligible_pair","supported","new_positive","baseline_positive")
    sums=("new_gross_sum_bps","baseline_gross_sum_bps")
    ret={k:sum(w[k] for w in wks) for k in names}
    for k in sums:ret[k]=math.fsum(w[k] for w in wks)
    count=Counter()
    for w in wks:count.update(w["reason_counts"])
    ret["reasons"]=dict(sorted(count.items()))
    n=ret["supported"]
    ret["model_mean_reference_bps"]=ret["new_gross_sum_bps"]/n if n else None
    ret["baseline_mean_reference_bps"]=ret["baseline_gross_sum_bps"]/n if n else None
    ret["paired_increment_bps"]=(ret["new_gross_sum_bps"]-ret["baseline_gross_sum_bps"])/n if n else None
    ret["model_mean_after_flat_cost_sensitivities_bps"]={str(c):(ret["model_mean_reference_bps"]-c if n else None) for c in (2,5,10)}
    ret["baseline_mean_after_flat_cost_sensitivities_bps"]={str(c):(ret["baseline_mean_reference_bps"]-c if n else None) for c in (2,5,10)}
    ret["paired_increment_after_equal_flat_cost_bps"]=ret["paired_increment_bps"]
    ret["calendar_normalized_increment_bps"]=(ret["new_gross_sum_bps"]-ret["baseline_gross_sum_bps"])/ret["calendar"] if ret["calendar"] else None
    ret["supported_fraction"]=n/ret["calendar"] if ret["calendar"] else None
    ret["eligible_fraction"]=ret["eligible_pair"]/ret["calendar"] if ret["calendar"] else None
    return ret
def compare_counts(record,stored):
    for k in ("calendar","eligible_pair","supported","new_positive","baseline_positive"):
        need(record[k]==stored[k],"PERSISTED_REDUCER_COUNT_DRIFT")
    for k in ("new_gross_sum_bps","baseline_gross_sum_bps"):
        need(nearly(record[k],stored[k]),"PERSISTED_REDUCER_GROSS_DRIFT")
    need(record["reasons"]==stored["reason_counts"],"PERSISTED_REASONS_DRIFT")
def main():
    global PHASE
    os.umask(0o077)
    head=os.environ["GITHUB_SHA"];e.w.v2.runtime(head)
    auth=json.loads((e.a.ROOT/(P+"EXECUTION_V1.json")).read_text())
    need(auth["type"]=="READ_EXISTING_EXTREMA_RESULT_ONLY" and
         auth["new_broker_requests"]==0 and auth["market_archive_replay"] is False and
         auth["new_scientific_experiment"] is False and auth["orders"] is False and
         auth["protected_forward"] is False,"READBACK_SCOPE")
    need(os.environ.get("GITHUB_EVENT_NAME")=="push" and
         os.environ.get("GITHUB_WORKFLOW_REF")==e.w.old.REPO+"/"+W+"@refs/heads/"+e.w.old.BRANCH,"WORKFLOW_SCOPE")
    e.a.ancestor(auth["base_head"],head)
    for p,expected in auth["git_blob_sha1_bindings"].items():
        got=subprocess.check_output(["git","hash-object",p],cwd=e.a.ROOT,text=True).strip()
        need(got==expected,"IMMUTABLE_READBACK_SOURCE_DRIFT")
    need(e.w.old.api("git/ref/heads/"+e.w.old.BRANCH)["object"]["sha"]==head,"LIVE_HEAD_DRIFT")
    tag="mxm-extrema-readback-oneuse-"+auth["invocation_id"]
    need(not e.w.v2.existing_ref(tag),"READBACK_ALREADY_CONSUMED")
    e.w.old.api("git/refs",{"ref":"refs/tags/"+tag,"sha":head})
    recipient=(e.a.ROOT/(P+"RECIPIENT_PUBLIC_KEY.pem")).read_bytes()
    need(sha(recipient)==auth["recipient_sha256"],"RECIPIENT_FINGERPRINT")
    pub=serialization.load_pem_public_key(recipient)
    need(isinstance(pub,rsa.RSAPublicKey) and pub.key_size>=3072,"RECIPIENT_STRENGTH")
    with tempfile.TemporaryDirectory(prefix="mxm-h1-existing-readback-",dir=os.environ["RUNNER_TEMP"]) as directory:
        tmp=pathlib.Path(directory)
        key,fp=e.w.old._private_key_from_secret(tmp)
        need(fp==e.w.old.FP,"EXISTING_OWNER_KEY_BINDING")
        PHASE="SOURCE_CIPHERTEXT_READBACK"
        source=auth["source"]
        rel=e.w.old.api("releases/"+str(source["release_id"]))
        need(rel["tag_name"]==source["release_tag"] and rel["target_commitish"]==source["source_head"],"ORIGINAL_RELEASE_DRIFT")
        run=e.w.old.api("actions/runs/"+str(source["run"]))
        need(run["status"]=="completed" and run["conclusion"]=="success" and
             run["run_attempt"]==1 and run["head_sha"]==source["source_head"],"SOURCE_RUN_DRIFT")
        full,pmeta=load_asset(key,fp,tmp,source["primary"])
        att,ameta=load_asset(key,fp,tmp,source["attestation"])
        need(att["schema"]=="mxm.owner.frontier.attestation.v1","ATTESTATION_SCHEMA")
        need(att["primary"]["ciphertext_sha256"]==pmeta["ciphertext_sha256"] and
             att["primary"]["canonical_sha256"]==pmeta["canonical_sha256"] and
             att["primary"]["name"]==source["primary"]["name"],"PRIMARY_ATTESTATION_MISMATCH")
        need(att["summary"]["source_head"]==source["source_head"] and att["summary"]["run_id"]==source["run"],"ATTESTED_SOURCE")
        prior=dict(att["summary"])
        for k in ("durable_primary","source_head","run_id"):prior.pop(k,None)
        need(e.a.enc(prior)==e.a.enc(full["summary"]),"ATTESTED_SUMMARY_EQUALITY")
        summary=full["summary"]
        need(summary["schema"]=="mxm.private.authentic.extrema.order.development.v1" and
             summary["new_exact"]=="H1_EXTREMA_TEMPORAL_PRECEDENCE_FIXED_DIRECTION_V1","FROZEN_EXPERIMENT_ID")
        need(summary["broker_requests"]==0 and summary["orders"]==0 and
             summary["protected_forward"] is False and summary["alpha_certified"] is False,"SCIENTIFIC_SCOPE")
        PHASE="PERSISTED_NUMERIC_REDUCTION_ONLY"
        people=full["all_identities"];prov=full["source_provenance"]
        need(len(people)==1576 and len(prov)==100 and
             summary["identities"]==1576 and summary["shards"]==100 and
             summary["authentic_m5_rows"]==3355389,"ORIGINAL_CORPUS_COUNTS")
        need(sum(q["rows"] for q in prov)==3355389,"ORIGINAL_PROVENANCE_COUNTS")
        need(sum(x["source_rows"] for x in people)==3355389,"IDENTITY_ROW_COUNT")
        need(len({x["ordinal"] for x in people})==1576 and len({x["symbol_id"] for x in people})==1576,"IDENTITY_UNIQUENESS")
        original=summary["four_weeks"]
        need(len(original)==4 and all(w["calendar"]==1576*42 for w in original),"FOUR_WEEKS_FIXED")
        need(set(summary["iso_utc"])==set(k for x in people for k in x["result"]["iso_utc"]),"ISO_PERSISTED_KEYS")
        for w in range(4):
            from_id=digest_metrics([x["result"]["four_weeks"][w] for x in people])
            compare_counts(from_id,original[w])
        need(sum(w["calendar"] for w in original)==264768,"SCHEDULED_4_WEEK_COUNTS")
        for k,w in summary["iso_utc"].items():
            from_id=digest_metrics([x["result"]["iso_utc"][k] for x in people if k in x["result"]["iso_utc"]])
            compare_counts(from_id,w)
        need(sum(w["calendar"] for w in summary["iso_utc"].values())==264768,"ISO_CALENDAR_DENOMINATOR")
        original_classes=summary["all_classes"]
        need(set(original_classes)==set(x["asset_class"] for x in people),"ALL_CLASS_IDENTITIES")
        by_class={}
        for cls,blocks in sorted(original_classes.items()):
            subset=[x for x in people if x["asset_class"]==cls]
            need(len(blocks)==4,"CLASS_BLOCK_COUNT")
            for w in range(4):
                from_id=digest_metrics([x["result"]["four_weeks"][w] for x in subset])
                compare_counts(from_id,blocks[w])
            by_class[cls]={"identity_count":len(subset),
                "all":digest_metrics(blocks),
                "blocks":[dict(block=w,**digest_metrics([block])) for w,block in enumerate(blocks)],
                "supported_identities":sum(any(x["result"]["four_weeks"][w]["supported"]>0 for w in range(4)) for x in subset)}
        block_reports=[dict(block=i,**digest_metrics([w])) for i,w in enumerate(original)]
        complete={"2026-W35","2026-W36","2026-W37"}
        iso_reports={k:{"complete_iso_utc_week":k in complete,**digest_metrics([w])} for k,w in sorted(summary["iso_utc"].items())}
        need(complete.issubset(set(iso_reports)),"COMPLETE_ISO_WEEKS_MISSING")
        agg=digest_metrics(original)
        need(agg["calendar"]==264768 and sum(x["identity_count"] for x in by_class.values())==1576,"FULL_UNIVERSE")
        need(sum(x["all"]["supported"] for x in by_class.values())==agg["supported"],"CLASS_PAIRED_DENOMINATOR")
        need(sum(x["supported"] for x in iso_reports.values())==agg["supported"],"ISO_PAIRED_DENOMINATOR")
        distinct=sum(any(w["supported"]>0 for w in x["result"]["four_weeks"]) for x in people)
        evidence={"schema":"mxm.h1.extrema.private.authenticated.aggregate.readback.v1",
           "source_provenance":{"original_run":source["run"],"original_job":source["job"],
              "original_release":source["release_id"],"original_head":source["source_head"],
              "original_primary_cipher_sha256":pmeta["ciphertext_sha256"],
              "original_primary_canonical_sha256":pmeta["canonical_sha256"],
              "original_attestation_cipher_sha256":ameta["ciphertext_sha256"]},
           "experiment":summary["new_exact"],"source_design_commit":auth["frozen_design_commit"],
           "corpus":{"m5_rows":3355389,"encrypted_shards":100,"identities":1576,
                     "fixed_event_clocks":264768,"identity_with_supported_pairs":distinct},
           "all":agg,"four_original_blocks":block_reports,"iso_utc":iso_reports,
           "asset_classes":by_class,"selection":"ALL_ORIGINAL_IDENTITIES_CLASSES_WEEKS_FIXED_NO_POSTHOC_SELECTION",
           "missingness":"FULL_ORIGINAL_CAUSAL_FEATURE_AND_LABEL_REASON_COUNTS_PRESERVED_BY_BLOCK_CLASS_ISO",
           "uncertainty":"DEPENDENT_SAME_INSTRUMENT_TEMPORAL_SEQUENCES_AND_CROSS_INSTRUMENT_COMMON_TIME_MOVES;NO_IID_PVALUES_OR_INDEPENDENT_CONFIRMATION;FOUR_BLOCKS_DO_NOT_LICENSE_SIGNIFICANCE",
           "costs":"GROSS_REFERENCE_M5_ONLY;2_5_10_BPS_ARE_UNIFORM_HYPOTHETICAL_FULL_TRADE_COST_SENSITIVITIES_NOT_ACTUAL_PEPERSTONE_COMMISSION_OR_SPREAD_OR_SWAP",
           "real_fills":0,"net_certified":False,"HARD21_certified":False,
           "historical_broker_requests_during_readback":0,"model_replayed":False,
           "source_shards_read_during_readback":0,"protected_forward":False}
        raw=json.dumps(evidence,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()
        need(len(raw)<150000,"PRIVATE_AGGREGATE_LIMIT")
        compressed=gzip.compress(raw,mtime=0)
        aes=os.urandom(32);nonce=os.urandom(12)
        cipher=AESGCM(aes).encrypt(nonce,compressed,head.encode())
        wrapped=pub.encrypt(aes,padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
        b64=lambda b:base64.b64encode(b).decode("ascii")
        envelope={"version":"MXM_H1_EXTREMA_RSA_OAEP_AES256GCM_V1",
         "head":head,"recipient_pub_sha256":sha(recipient),
         "wrapped_key_b64":b64(wrapped),"nonce_b64":b64(nonce),
         "ciphertext_b64":b64(cipher),"compressed_plain_sha256":sha(compressed),
         "source_cipher_sha256":pmeta["ciphertext_sha256"],
         "source_attestation_sha256":ameta["ciphertext_sha256"]}
        body=json.dumps(envelope,sort_keys=True,separators=(",",":"),ensure_ascii=True)
        need(len(body)<85000 and not any(s in body for s in (
             "model_mean_reference_bps","baseline_mean_reference_bps",
             "paired_increment_bps","supported_fraction","source_rows","reason_counts")),"NO_PUBLIC_NUMERIC_VALUES")
        PHASE="CIPHERTEXT_ONLY_PUBLICATION"
        out=e.w.old.api("releases",{"tag_name":"mxm-private-extrema-h1-readback-"+auth["invocation_id"]+"-"+os.environ["GITHUB_RUN_ID"],
           "target_commitish":head,"name":"MXM H1 extrema authenticated private aggregates ciphertext only",
           "prerelease":True,"body":body})
        remote=e.w.old.api("releases/"+str(out["id"]))
        need(remote["body"]==body,"ENCRYPTED_READBACK_INTEGRITY")
        print(json.dumps({"schema":"mxm.h1.extrema.public.readback.status.v1",
             "status":"PASS","run_id":int(os.environ["GITHUB_RUN_ID"]),
             "release_id":out["id"],"head":head,
             "original_primary_cipher_sha256":pmeta["ciphertext_sha256"],
             "cipher_envelope_sha256":sha(body.encode()),
             "numeric_plaintext_public":False,"broker_requests":0,
             "shards_reread":0,"experiments_replayed":0,"orders":0},sort_keys=True),flush=True)
if __name__=="__main__":
    try:main()
    except Exception as ex:
        code=str(ex) if re.fullmatch("[A-Z][A-Z0-9_]{0,80}",str(ex)) else type(ex).__name__
        print("FAIL_CLOSED_EXTREMA_READBACK_"+PHASE+"_"+code,flush=True)
        raise SystemExit(2) from None
