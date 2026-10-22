"""Precommitted M5 DEVELOPMENT outcome exposure: two paired causal contrasts, not broker fills.
One bounded protected-GitHub read of immutable Pepperstone release, zero new broker requests.
Do NOT classify this developmental exposure as independent confirmation or a qualified edge.
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
from research_core_v4.laboratory import m5_authentic_envelope as env

REPO=env.REPO
SPECS_PATH=env.ROOT/"research_core_v4/laboratory/M5_CAUSAL_GROSS_DEVELOPMENT_V1.json"
FIRST="2026-08-20T00:00:00Z"
LAST="2026-09-16T23:55:00Z"
COSTS=(0,10,20,40)
EXPECTED_SHARDS=100
EXPECTED_ROWS=3355389

def need(condition,msg):
    if not condition: raise RuntimeError("MXM_M5_CAUSAL_DEV_FAIL_"+msg)

def sha(blob):return hashlib.sha256(blob).hexdigest()

def statistic():
    return {"signals":0,"sum_gross_bps":0.0,"gross_positive":0,
            "after_10bps_positive":0,"after_20bps_positive":0,
            "total_gross_after_assumed_bps":{str(k):0.0 for k in COSTS},
            "iso_utc_entry_week_counts":{}}

def verify_specs():
    blob=SPECS_PATH.read_bytes()
    spec=json.loads(blob)
    need(spec["schema"]=="mxm.scientific.m5-causal-gross-development-precommit.v1"
         and spec["program_id"]=="MXM_M5_CAUSAL_GROSS_DEVELOPMENT_20261022_V1",
         "PROGRAM")
    hs=spec["hypotheses"]
    need(len(hs)==4 and [x["id"] for x in hs]==[
        "MXM20261022_M5_L3_TREND","MXM20261022_M5_L3_FADE",
        "MXM20261022_M5_L12_TREND","MXM20261022_M5_L12_FADE"],"PRECOMMITTED_IDENTITIES")
    for i,row in enumerate(hs):
        need(row["lookback_bars"]==row["hold_bars"]==(3 if i<2 else 12) and
             row["delayed_entry_open_bars"]==2 and
             row["abs_trailing_threshold_bps"]==10 and
             row["direction"]==("TRAILING_MOVE" if i%2==0 else "OPPOSITE_TRAILING_MOVE"),
             "SPEC_CHANGED")
    need(spec["scientific_budget"]["finite_predeclared_model_leaves"]==4 and
         spec["scientific_budget"]["dependent_paired_contrasts"]==2 and
         spec["scientific_budget"]["independent_confirmation_claims_allowed"]==0 and
         spec["temporal_policy"]["entire_window_marked_exposed"] and
         spec["temporal_policy"]["development_observation_from_utc"]==FIRST and
         spec["temporal_policy"]["development_observation_through_utc"]==LAST and
         not spec["temporal_policy"]["confirmation_opened"] and
         not spec["temporal_policy"]["protected_forward_opened"],"EXPOSURE_GUARD")
    return spec,sha(blob)

def load_market_geometry():
    manifest=json.loads(env.MANIFEST.read_bytes())
    need(manifest["status"]=="COMPLETE" and manifest["DURABLE_RELEASE_IDENTITY"]==env.RELEASE_IDENTITY and
         manifest["PROTECTED_FORWARD_ROW_COUNT"]==0 and manifest["encrypted_shard_count"]==100 and
         len(manifest["entries"])==100 and sum(e["ROW_COUNT"] for e in manifest["entries"])==EXPECTED_ROWS,"MANIFEST")
    entries={(e["SEGMENT_INDEX"],e["SHARD_INDEX"]):e for e in manifest["entries"]}
    need(len(entries)==100 and set(entries)=={(segment,shard)
         for segment in range(1,5) for shard in range(25)},"SHARD_SET")
    release=env.gh_json("repos/"+REPO+"/releases/tags/"+env.RELEASE_IDENTITY)
    assets={a["name"]:a for a in release["assets"]}
    need(len(assets)==100 and release["target_commitish"]==manifest["ARM_COMMIT"] and
         release["draft"] is False,"RELEASE")
    for e in entries.values():
        a=assets[e["ENCRYPTED_ASSET_NAME"]]
        need(a["digest"]=="sha256:"+e["ENCRYPTED_ASSET_SHA256"] and a["state"]=="uploaded","RELEASE_SHA")
    return entries,sha(env.MANIFEST.read_bytes())

def parse_rows(rows):
    # Source order strictly ascending. Adjacent exact M5 timestamps are required for every trial.
    timestamps=[];opens=[];closes=[]
    last=-1
    for row in rows:
        t=row["time_utc"]
        need(FIRST<=t<=LAST and t<env.PROTECTED_START,"PROTECTED_TIME")
        v=dt.datetime.fromisoformat(t.replace("Z","+00:00"))
        ts=int(v.timestamp())//300
        need(ts>last and ts*300==int(v.timestamp()),"MONOTONIC_M5")
        op=float(row["open"]);cl=float(row["close"])
        lo=float(row["low"]);hi=float(row["high"])
        need(all(math.isfinite(q) and q>0 for q in (op,cl,lo,hi))
             and lo<=op<=hi and lo<=cl<=hi,"OHLC")
        last=ts; timestamps.append(ts);opens.append(op);closes.append(cl)
    return timestamps,opens,closes

def evaluate_one(rows,models):
    if not rows:return
    stamps,opens,closes=parse_rows(rows)
    n=len(stamps)
    for lookback,hold,ids in ((3,3,("MXM20261022_M5_L3_TREND","MXM20261022_M5_L3_FADE")),
                              (12,12,("MXM20261022_M5_L12_TREND","MXM20261022_M5_L12_FADE"))):
        i=lookback
        while i+2+hold<n:
            # A valid signal must use earlier already-completed M5 bars only.
            # The entry is the NEXT-NEXT bar open: one whole M5 step after completed signal.
            entry_idx=i+2; exit_idx=i+2+hold
            if (stamps[i]-stamps[i-lookback]!=lookback or
                stamps[exit_idx]-stamps[i] != 2+hold):
                i+=1;continue
            trailing=(closes[i]-closes[i-lookback])/closes[i-lookback]*10000.0
            if abs(trailing)<10:
                i+=1;continue
            direction=1 if trailing>0 else -1
            gross=direction*(opens[exit_idx]-opens[entry_idx])/opens[entry_idx]*10000.0
            eventweek=(dt.datetime.fromtimestamp(stamps[entry_idx]*300,tz=dt.timezone.utc).
                       strftime("%G-W%V"))
            for key,mult in ((ids[0],1),(ids[1],-1)):
                out=models[key]
                signed=gross*mult
                out["signals"]+=1
                out["sum_gross_bps"]+=signed
                out["gross_positive"]+=int(signed>0)
                out["after_10bps_positive"]+=int(signed>10)
                out["after_20bps_positive"]+=int(signed>20)
                for charge in COSTS:
                    out["total_gross_after_assumed_bps"][str(charge)]+=signed-charge
                weeks=out["iso_utc_entry_week_counts"]
                weeks[eventweek]=weeks.get(eventweek,0)+1
            # No overlapping positions for this ONE instrument/horizon; other instruments
            # and different horizons are INDEPENDENT PAPER CHANNELS, not a EUR200 portfolio.
            i=exit_idx

def selftest():
    spec,_=verify_specs()
    t=dt.datetime(2026,8,24,tzinfo=dt.timezone.utc)
    rows=[]
    for i in range(54):
        price=1.0+0.002*i
        rows.append({"time_utc":(t+dt.timedelta(minutes=5*i)).isoformat().replace("+00:00","Z"),
                     "open":str(price),"high":str(price+0.001),"low":str(price-0.001),
                     "close":str(price),"tick_volume":"12"})
    models={x["id"]:statistic() for x in spec["hypotheses"]}
    evaluate_one(rows,models)
    need(models["MXM20261022_M5_L3_TREND"]["signals"]>0 and
         models["MXM20261022_M5_L3_TREND"]["signals"]==models["MXM20261022_M5_L3_FADE"]["signals"] and
         abs(models["MXM20261022_M5_L3_TREND"]["sum_gross_bps"]+
             models["MXM20261022_M5_L3_FADE"]["sum_gross_bps"])<1e-7,"DIRECTION_PAIR")
    need(models["MXM20261022_M5_L3_TREND"]["sum_gross_bps"]>0,"NO_LOOKAHEAD")
    rows[6]["time_utc"]="2026-09-17T00:00:00Z"
    try:evaluate_one(rows,{x["id"]:statistic() for x in spec["hypotheses"]})
    except RuntimeError as e:need("PROTECTED_TIME" in str(e),"TIME_FENCE_TEST")
    else:need(False,"TIME_FENCE_TEST")
    print("MXM_M5_CAUSAL_DEV_SELFTEST_PASS")

def protected_run(dest):
    need(os.environ.get("GITHUB_REPOSITORY")==REPO and
         os.environ.get("GITHUB_REF")=="refs/heads/mxm-remediation-p0-p4-20261015-v1" and
         os.environ.get("GITHUB_RUN_ATTEMPT")=="1","NATIVE_PROTECTED_CUSTODY_ONLY")
    spec,spechash=verify_specs()
    entries,manifesthash=load_market_geometry()
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.shallow_m5_support_v2_production import decrypt_synthetic_package,encrypt_shard,public_spki_sha256
    models={x["id"]:statistic() for x in spec["hypotheses"]}
    rows_verified=0;shards_verified=0;identity_count=0
    with tempfile.TemporaryDirectory(prefix="mxm-m5-causal-") as rawdir:
        root=Path(rawdir)
        key,fp=_private_key_from_secret(root)
        need(fp=="464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11","PRIVATE_KEY_FP")
        assetsdir=root/"cipher";assetsdir.mkdir(mode=0o700)
        subprocess.run(["gh","release","download",env.RELEASE_IDENTITY,"--repo",REPO,
                        "--dir",str(assetsdir)],check=True,stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        need(len(list(assetsdir.iterdir()))==EXPECTED_SHARDS,"DOWNLOADED_COUNT")
        for shard_index in range(25):
            by_ordinal=collections.defaultdict(list)
            for segment in range(1,5):
                e=entries[(segment,shard_index)]
                c=(assetsdir/e["ENCRYPTED_ASSET_NAME"]).read_bytes()
                need(sha(c)==e["ENCRYPTED_ASSET_SHA256"],"CIPHER_DIGEST")
                blob=decrypt_synthetic_package(c,private_key=key)
                need(sha(blob)==e["PLAINTEXT_CANONICAL_SHA256"],"PLAINTEXT_DIGEST")
                data=json.loads(blob)
                need(data["schema"]=="mxm.v4.shallow-m5-v2.raw-shard.v1" and
                     data["segment_index"]==segment and data["shard_index"]==shard_index and
                     data["identity_range"]==e["IDENTITY_RANGE"],"SHARD_IDENTITY")
                expected_ord=list(range(e["IDENTITY_RANGE"][0],e["IDENTITY_RANGE"][1]+1))
                need([x["ordinal"] for x in data["items"]]==expected_ord,"ITEM_ORDINALS")
                n=0
                for item in data["items"]:
                    need(item["classification"] in ("NO_HISTORICAL_SUPPORT","SHALLOW_SUPPORT_COMPLETE",
                         "SHALLOW_SUPPORT_PARTIAL_DATA_LIMITED"),"SUPPORT_CLASS")
                    rr=item["rows"]
                    need(isinstance(rr,list),"ROWS")
                    n+=len(rr)
                    by_ordinal[item["ordinal"]].extend(rr)
                need(n==e["ROW_COUNT"],"SHARD_ROW_COUNT")
                rows_verified+=n;shards_verified+=1
            for ordinal in sorted(by_ordinal):
                rows=by_ordinal[ordinal]
                identity_count+=1
                # Raw times increase over the four disjoint segments; missing session
                # gaps are not filled. Their effect is handled by exact-contiguity checks.
                evaluate_one(rows,models)
        need(rows_verified==EXPECTED_ROWS and shards_verified==EXPECTED_SHARDS
             and identity_count==1576,"FULL_EXPOSURE_COUNT")
        details={"schema":"mxm.m5-causal-gross-development-exposure-result.v1",
            "spec_sha256":spechash,"manifest_sha256":manifesthash,
            "classification":"DEVELOPMENT_EXPOSED_UNCERTIFIED_M5_INDICATIVE_OPEN_PRICES",
            "model_outputs":models,"broker_orders":0,"broker_requests":0,
            "historical_fills_proven":False,"roundtrip_cost_authority":"NONE",
            "confirmation_or_protected_forward_opened":False,
            "is_EUR200_capital_continuous_portfolio":False,"hard21":False,
            "every_observed_week_exposed":True,"multiple_testing_adjusted":False}
        encoded=json.dumps(details,sort_keys=True,separators=(",",":")).encode()
        out=Path(dest);out.mkdir(parents=True,exist_ok=True)
        recipient=env.ROOT/"research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem"
        need(public_spki_sha256(recipient)==fp,"CUSTODY_RECIPIENT_MISMATCH")
        cipher=out/"full-development-result.mxmenc"
        encrypt_shard(encoded,public_key=recipient,output=cipher)
        agg=[]
        for name,m in models.items():
            n=m["signals"]
            agg.append({"model_id":name,"opportunities":n,
              "gross_avg_bps":round(m["sum_gross_bps"]/n,5) if n else None,
              "mean_minus_hypothetical_10bps":round(m["sum_gross_bps"]/n-10,5) if n else None,
              "gross_positive_share":round(m["gross_positive"]/n,5) if n else None})
        receipt={"schema":"mxm.m5-causal-gross-development-public-limited.v1",
            "spec_sha256":spechash,"manifest_sha256":manifesthash,
            "rows_verified":rows_verified,"shards_verified":shards_verified,
            "identity_count":identity_count,"finite_registered_model_leaves":4,
            "dependent_paired_contrasts":2,"models":agg,
            "encrypted_private_result_sha256":sha(cipher.read_bytes()),
            "classification":"DEVELOPMENT_ONLY_NO_INDEPENDENT_CONFIRMATION_NO_BROKER_FILLS",
            "hypothetical_10bps_is_not_cost_evidence":True,
            "economic_identity_certified":False,"canonical_V2_book_changed":False,
            "all_market_data_exposed_to_development":True,
            "protected_forward_opened":False,"broker_requests":0,"orders":0,
            "eur200_executable_pnl":None,"hard21":False,
            "no_new_confirmation_data":True}
        (out/"receipt.json").write_text(json.dumps(receipt,sort_keys=True,separators=(",",":"))+"\n")
        print("MXM_M5_CAUSAL_GROSS_DEVELOPMENT "+json.dumps(receipt,sort_keys=True),flush=True)

def main():
    args=argparse.ArgumentParser()
    args.add_argument("--selftest",action="store_true")
    args.add_argument("--protected-output")
    a=args.parse_args()
    need(bool(a.selftest)!=bool(a.protected_output),"MODE")
    if a.selftest:selftest()
    else:protected_run(a.protected_output)
if __name__=="__main__":main()
