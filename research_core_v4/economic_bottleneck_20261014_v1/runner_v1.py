"""Private existing-result economic bottleneck accounting. No scientific replay."""
import base64,collections,datetime,hashlib,json,math,os,pathlib,subprocess,tempfile
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
e=rt.e
HERE=pathlib.Path(__file__).resolve().parent
WORKFLOW=".github/workflows/mxm-economic-bottleneck-20261014-v1.yml"
def ensure(v,c):
 if not v:raise RuntimeError(c)
def gate():
 a=json.loads((HERE/"EXECUTION_V1.json").read_text());h=os.environ["GITHUB_SHA"]
 ensure(a["authority"]=="EXPLICIT_OWNER_MACHINE_SIDE_ECONOMIC_DISCOVERY_RECOVERY_20261014","MANDATE")
 ensure(os.environ["GITHUB_EVENT_NAME"]=="push" and os.environ["GITHUB_RUN_ATTEMPT"]=="1","ONE_PUSH")
 ensure(os.environ["GITHUB_WORKFLOW_REF"]==e.w.old.REPO+"/"+WORKFLOW+"@refs/heads/"+e.w.old.BRANCH,"WORKFLOW")
 ensure(datetime.datetime.now(datetime.timezone.utc).isoformat()<a["expires_utc"],"EXPIRED")
 ensure(subprocess.run(["git","merge-base","--is-ancestor",a["base_head"],h],stdout=subprocess.DEVNULL).returncode==0,"BASE")
 for path,digest in a["source_bindings"].items():ensure(e.w.old.filehash(path)==digest,"FROZEN_DRIFT")
 d=json.loads((e.a.ROOT/"research_core_v4/quote_duration_20261014_v1/EXACT_DECISION_V1.json").read_text())
 ensure(d["decision"]=="CLOSED_NO_PROMOTION_NEGATIVE_EXACT" and not d["further_exact_rescue_authorized"],"CLOSED")
 ensure(e.w.old.api("git/ref/heads/"+e.w.old.BRANCH)["object"]["sha"]==h,"HEAD_DRIFT")
 ensure(not e.w.v2.existing_ref(a["one_use_tag"]),"CONSUMED")
 e.w.old.api("git/refs",{"ref":"refs/tags/"+a["one_use_tag"],"sha":h})
 return h,a
def compute(pre,pilot):
 q=pre["summary"];s=pilot["summary"];rows=q["statuses"];events=pre["records_without_outcomes"];selected=pilot["proposed_records"]
 ensure(len(rows)==5326 and len(events)==q["saved_candidate_boundaries"],"SOURCE_DENOMINATOR")
 ensure(len({(x["sid"],x["t"]) for x in events})==len(events),"UNIQUE_BOUNDARIES")
 ensure(s["verdict"]=="CLOSED_NO_PROMOTION_NEGATIVE_EXACT" and s["qualification"]["catalog_total"]==5326,"PREVIOUS_OUTCOME")
 universe=collections.Counter();struct=collections.Counter();marginal=collections.Counter()
 for r in rows:
  k=("E" if r["structural_eligible"] else "X")+("M" if r["known_accepted_M5"] else "U")+("Q" if r["saved_quote_pages"] else "N")
  universe[k]+=1
  for name in r["structural_reasons"]:struct[name]+=1
  for key,val in (("eligible",r["structural_eligible"]),("known_M5",r["known_accepted_M5"]),("saved_quotes",r["saved_quote_pages"])):marginal[key]+=int(val)
 ensure(sum(universe.values())==5326,"UNIVERSE_SUM")
 stages={"saved_boundaries":len(events),"native_cost_entry_eligible":sum(x["entry"].get("eligible") is True for x in events),"feature_supported":sum(x["feature"].get("state")=="SUPPORTED" for x in events),"both_directional":sum(x["entry"].get("eligible") is True and x["feature"].get("state")=="SUPPORTED" and bool(x["feature"].get("model_side")) for x in events)}
 ensure(stages["both_directional"]==len(selected),"SELECTED_MATCH")
 fields=("midpoint_gross_eur","spread_drag_eur","slippage_drag_eur","entry_commission_eur","exit_commission_eur","pnl_conversion_fee_eur","funding_stress_eur","net_eur")
 economics={}
 for scenario in ("S0_F0","PRIMARY_S2_F010","S5_F050"):
  complete=[x for x in selected if x["accounts"].get(scenario) is not None]
  aggregate={side:{f:math.fsum(z["accounts"][scenario][side][f] for z in complete) for f in fields} for side in ("model","count","momentum")}
  ensure(len(complete)==s["scenarios"][scenario]["paired_evaluable"],"PREVIOUS_PAIR_COUNT")
  for side in aggregate:
   v=aggregate[side];delta=v["midpoint_gross_eur"]-sum(v[f] for f in fields[1:-1])
   ensure(math.isclose(delta,v["net_eur"],abs_tol=1e-7,rel_tol=1e-7),"COST_BRIDGE")
   for f in fields:ensure(math.isclose(v[f],s["scenarios"][scenario][side][f],abs_tol=1e-7,rel_tol=1e-7),"PRIOR_AGGREGATE")
  economics[scenario]={"paired":len(complete),"censored":len(selected)-len(complete),"cash_NET_eur":0,"decompositions_eur":aggregate,"model_minus_count_NET_eur":aggregate["model"]["net_eur"]-aggregate["count"]["net_eur"],"model_minus_momentum_NET_eur":aggregate["model"]["net_eur"]-aggregate["momentum"]["net_eur"]}
 return {"schema":"mxm.owner.project_bottleneck.attribution.v1","catalog":{"total":5326,"class_intersections_structural_M5_quotes":dict(sorted(universe.items())),"marginal":dict(marginal),"structural_reason_occurrences_overlapping":dict(struct),"archived_separate":q["catalog_archived_separate"],"unknown_history_not_alpha_negative":True},"opportunities":{"stages":stages,"entry_reason_occurrences":dict(collections.Counter(x["entry"]["state"] for x in events)),"feature_reasons":dict(collections.Counter(x["feature"]["state"] for x in events)),"native_quote_reasons":q["native_quote_support_reasons"],"weeks_supported_precheck":q["supported_complete_ISO_weeks"],"selected_by_week":dict(collections.Counter(x["iso"] for x in selected))},"economics_same_paired_set":economics,"portfolio_from_original":{"closed_by_week":s["portfolio_weekly_closed"],"existing_portfolio":s["portfolio"],"risk_reference_breaches":s["minimum_ticket_risk_reference_breaches"],"equity_initial_eur":200,"risk_cap_initial_eur":2,"margin_cap_initial_eur":80,"min_reserve_initial_eur":120,"HARD21_proven":False},"interpretation":"Gross-cost bridge applies only to paired opportunities. Missing quote/history are not negative alpha. No additive attribution share of all 5326 is identified. Cost assumptions use current terms and stress, not historical fills.","replay":False,"new_predictor":False,"orders":0,"full_historical_actual_NET":None,"decision":"STOP_NO_NEW_QUALIFIED_NET_CANDIDATE"}
def main():
 os.umask(0o077);h,a=gate()
 with tempfile.TemporaryDirectory(prefix="mxm-bottleneck-",dir=os.environ["RUNNER_TEMP"]) as td:
  tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp)
  ensure(fp==e.w.old.FP,"PINNED_OWNER")
  pre,_=load_asset(key,fp,tmp,a["precheck"]);pilot,_=load_asset(key,fp,tmp,a["pilot"])
  doc=compute(pre,pilot);raw=e.a.enc(doc)
  signing=serialization.load_pem_private_key(key.read_bytes(),password=None)
  sig=signing.sign(raw,padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256())
  signing.public_key().verify(sig,raw,padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256())
  signed={"payload":doc,"payload_sha256":hashlib.sha256(raw).hexdigest(),"signature_algorithm":"RSA-PSS-SHA256","signature_b64":base64.b64encode(sig).decode(),"owner_spki_sha256":fp}
  store=e.w.old.GitHubStore(h,key,e.a.ROOT/e.w.old.PUBLIC_KEY,tmp,"real")
  public={"schema":"mxm.economic.bottleneck.owner.receipt.v1","source_head":h,"run_id":int(os.environ["GITHUB_RUN_ID"]),"state":"NOT_PERSISTED","no_market_replay":True}
  store.release=e.w.old.api("releases",{"tag_name":"mxm-economic-bottleneck-20261014-"+os.environ["GITHUB_RUN_ID"],"target_commitish":h,"name":"MXM owner signed bottleneck accounting","prerelease":True,"body":json.dumps(public,sort_keys=True)})
  asset=store.encrypted(signed,"economic-bottleneck-owner-signed.mxmenc")
  again,proof=load_asset(key,fp,tmp,{"release_id":store.release["id"],"asset_id":asset["id"],"ciphertext_sha256":asset["ciphertext_sha256"]})
  ensure(again==signed,"REMOTE_OWNER_READBACK")
  ensure(proof["canonical_sha256"]==hashlib.sha256(e.a.enc(signed)).hexdigest(),"SIGNED_HASH")
  public.update(state="PASS",release_id=store.release["id"],asset_id=asset["id"],ciphertext_sha256=asset["ciphertext_sha256"],signed_payload_sha256=signed["payload_sha256"],catalog_total=doc["catalog"]["total"],economic_decision=doc["decision"])
  e.w.old.api("releases/"+str(store.release["id"]),{"body":json.dumps(public,sort_keys=True)},method="PATCH")
  ensure(json.loads(e.w.old.api("releases/"+str(store.release["id"]))["body"])==public,"RELEASE_READBACK")
  print(json.dumps(public,sort_keys=True),flush=True)
if __name__=="__main__":
 try:main()
 except Exception as ex:
  print("FAIL_CLOSED_ECONOMIC_BOTTLENECK_"+type(ex).__name__,flush=True)
  raise SystemExit(1) from None
