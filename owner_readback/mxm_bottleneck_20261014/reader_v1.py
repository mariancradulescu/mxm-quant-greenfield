"""Signed owner report public-safe counts only; no result recalculation."""
import base64,datetime,hashlib,json,os,pathlib,subprocess,tempfile
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
e=rt.e
P=pathlib.Path(__file__).resolve().parent
WF=".github/workflows/mxm-bottleneck-safe-readback-20261014.yml"
def require(x,reason):
 if not x:raise RuntimeError(reason)
def main():
 os.umask(0o077)
 c=json.loads((P/"READBACK_V1.json").read_text());head=os.environ["GITHUB_SHA"]
 require(c["authority"]=="EXPLICIT_OWNER_RECOVER_PUBLIC_SAFE_BOTTLENECK_COUNTS","OWNER_SCOPE")
 require(os.environ["GITHUB_EVENT_NAME"]=="push" and os.environ["GITHUB_RUN_ATTEMPT"]=="1","ONE_PUSH")
 require(os.environ["GITHUB_WORKFLOW_REF"]==e.w.old.REPO+"/"+WF+"@refs/heads/"+e.w.old.BRANCH,"WORKFLOW")
 require(datetime.datetime.now(datetime.timezone.utc).isoformat()<c["expires_utc"],"EXPIRED")
 require(subprocess.run(["git","merge-base","--is-ancestor",c["source_head"],head],stdout=subprocess.DEVNULL).returncode==0,"ANCESTRY")
 require(e.w.old.api("git/ref/heads/"+e.w.old.BRANCH)["object"]["sha"]==head,"LIVE_HEAD")
 require(not e.w.v2.existing_ref(c["one_use_tag"]),"DUPLICATE")
 e.w.old.api("git/refs",{"ref":"refs/tags/"+c["one_use_tag"],"sha":head})
 with tempfile.TemporaryDirectory(prefix="mxm-safe-readback-",dir=os.environ["RUNNER_TEMP"]) as td:
  tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp)
  require(fp==e.w.old.FP,"PINNED_OWNER")
  signed,_=load_asset(key,fp,tmp,{"release_id":c["release_id"],"asset_id":c["asset_id"],"ciphertext_sha256":c["ciphertext_sha256"]})
  d=signed["payload"];raw=e.a.enc(d)
  require(hashlib.sha256(raw).hexdigest()==signed["payload_sha256"]==c["signed_payload_sha256"],"HASH_BINDING")
  pub=serialization.load_pem_private_key(key.read_bytes(),password=None).public_key()
  pub.verify(base64.b64decode(signed["signature_b64"],validate=True),raw,padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256())
  require(signed["owner_spki_sha256"]==fp and d["catalog"]["total"]==5326,"TRUST_BINDING")
  boxes=d["catalog"]["class_intersections_structural_M5_quotes"]
  n=sum(boxes.values())
  require(n==5326,"COVERAGE_PARTITION")
  stages=d["opportunities"]["stages"]
  m=d["catalog"]["marginal"]
  primary=d["economics_same_paired_set"]["PRIMARY_S2_F010"]
  complete_by_week=d["portfolio_from_original"]["closed_by_week"]
  clean={"schema":"mxm.bottleneck.safe.readback.v1","source_signed_payload_sha256":c["signed_payload_sha256"],
   "data_head":c["source_head"],"readback_head":head,"catalog":n,
   "archived_separately":d["catalog"]["archived_separate"],
   "count_structural_eligible":m.get("eligible",0),
   "count_M5_known":m.get("known_M5",0),
   "count_quote_pages_saved":m.get("saved_quotes",0),
   "intersection_eligible_M5_quotes":boxes.get("EMQ",0),
   "exact_universe_partition":boxes,
   "saved_boundaries":stages["saved_boundaries"],
   "entry_cost_feasible":stages["native_cost_entry_eligible"],
   "feature_supported":stages["feature_supported"],
   "entry_feature_directional":stages["both_directional"],
   "primary_paired_evaluable":primary["paired"],"primary_censored":primary["censored"],
   "precheck_ISO_week_count":len(d["opportunities"]["weeks_supported_precheck"]),
   "portfolio_closed_week_counts":complete_by_week,
   "reference_risk_breach_count":d["portfolio_from_original"]["risk_reference_breaches"],
   "full_NET_and_PER_SYMBOL_data":"ENCRYPTED_ONLY",
   "HARD21_certified":False,"new_alpha":False,"new_data_requests":0,
   "status":"VERIFIED_COUNTS_ONLY"}
  old=e.w.old.api("releases/"+str(c["release_id"]))
  r=json.loads(old["body"])
  require(r["state"]=="PASS" and r["signed_payload_sha256"]==c["signed_payload_sha256"],"RELEASE_AUTHORITY")
  r["public_safe_count_readback"]=clean
  e.w.old.api("releases/"+str(c["release_id"]),{"body":json.dumps(r,sort_keys=True)},method="PATCH")
  require(json.loads(e.w.old.api("releases/"+str(c["release_id"]))["body"])["public_safe_count_readback"]==clean,"DURABLE_READER")
  print(json.dumps(clean,sort_keys=True),flush=True)
if __name__=="__main__":
 try:main()
 except Exception as exc:
  print("FAIL_CLOSED_PUBLIC_SAFE_READBACK_"+type(exc).__name__,flush=True)
  raise SystemExit(1) from None
