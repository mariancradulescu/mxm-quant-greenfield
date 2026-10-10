"""One-use DEVELOPMENT replay of a NEW extrema-order exact, never old experiments.
Only encrypted numeric results and safe categorical public run status.
"""
import json,os,pathlib,subprocess,tempfile,re
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.extrema_order_v1.kernel_v1 import evaluate,merge
e=rt.e
P="research_core_v4/extrema_order_v1/"
WORKFLOW=".github/workflows/mxm-extrema-order-v1.yml"
PHASE="GATE"

def gate():
    head=os.environ["GITHUB_SHA"]
    e.w.v2.runtime(head)
    auth=json.loads((e.a.ROOT/(P+"EXECUTION_V1.json")).read_text())
    e.w.old.need(auth["authority"]=="EXPLICIT_OWNER_AUTONOMOUS_HISTORICAL_RESEARCH_2026_10_10" and
      auth["broker_requests"]==0 and auth["orders"] is False and auth["protected_forward"] is False and
      auth["reexecute_existing_experiments"] is False,"AUTHORITY_SCOPE")
    e.w.old.need(os.environ.get("GITHUB_EVENT_NAME")=="push" and
      os.environ.get("GITHUB_WORKFLOW_REF")==e.w.old.REPO+"/"+WORKFLOW+"@refs/heads/"+e.w.old.BRANCH,"WORKFLOW_SCOPE")
    e.a.ancestor(auth["base_head"],head)
    for path,h in auth["blob_sha1_bindings"].items():
        got=subprocess.check_output(["git","hash-object",path],cwd=e.a.ROOT,text=True).strip()
        e.w.old.need(got==h,"FROZEN_SOURCE_DRIFT")
    current=e.w.old.api("git/ref/heads/"+e.w.old.BRANCH)["object"]["sha"]
    e.w.old.need(current==head,"LIVE_HEAD_DRIFT")
    old=json.loads((e.a.ROOT/(e.P+"EXACT_COVERAGE_PREARM_V1.json")).read_text())
    for path,h in old["bindings"].items():e.w.old.need(e.w.old.filehash(path)==h,"ORIGINAL_SOURCE_DRIFT")
    e.w.old.need(not e.w.v2.existing_ref(auth["one_use_ref"]),"INVOCATION_CONSUMED")
    e.w.old.api("git/refs",{"ref":"refs/tags/"+auth["one_use_ref"],"sha":head})
    return head,auth,e.w.old.verify_science()

def main():
    global PHASE
    os.umask(0o077)
    head,auth,source=gate()
    master,entries,digits,manifest=source
    with tempfile.TemporaryDirectory(prefix="mxm-extrema-",dir=os.environ["RUNNER_TEMP"]) as td:
        tmp=pathlib.Path(td)
        key,fp=e.w.old._private_key_from_secret(tmp)
        e.w.old.need(fp==e.w.old.FP,"EXISTING_KEY_BINDING")
        PHASE="SOURCE_READ"
        rel=e.w.old.api("releases/tags/"+manifest["DURABLE_RELEASE_IDENTITY"])
        assets={a["name"]:a for a in e.w.old.api("releases/"+str(rel["id"])+"/assets?per_page=100")}
        allresult=[];provenance=[];rowcount=0
        for group in range(25):
            buffers={ordinal:{} for ordinal in range(group*64+1,min(1576,group*64+64)+1)}
            for segment in range(1,5):
                entry=entries[(segment-1)*25+group]
                asset=assets[entry["ENCRYPTED_ASSET_NAME"]]
                e.w.old.need(asset["digest"]=="sha256:"+entry["ENCRYPTED_ASSET_SHA256"],"ARCHIVE_DIGEST_METADATA")
                blob=e.w.old.download(asset["browser_download_url"],asset["size"])
                e.w.old.need(e.a.sha(blob)==entry["ENCRYPTED_ASSET_SHA256"],"ARCHIVE_CIPHER_SHA256")
                raw=e.w.old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp)
                e.w.old.need(e.a.sha(raw)==entry["PLAINTEXT_CANONICAL_SHA256"],"ARCHIVE_CANON_SHA256")
                obj=e.w.n.canonical.strict_json(raw)
                e.w.old.need(e.w.n.canonical.canonical(obj)==raw and
                  set(obj)==e.w.n.canonical.PACKAGE_KEYS and
                  obj["segment_index"]==segment and obj["shard_index"]==group and
                  obj["identity_range"]==entry["IDENTITY_RANGE"],"ARCHIVE_CANONICAL_SCHEMA")
                lo,hi=entry["IDENTITY_RANGE"]
                e.w.old.need(len(obj["items"])==hi-lo+1,"ARCHIVE_ITEM_COUNTS")
                count=0
                for ordinal,item in zip(range(lo,hi+1),obj["items"]):
                    e.w.old.need(item["ordinal"]==ordinal and item["symbol_id"]==master[ordinal-1]["symbol_id"] and
                      item["failure"] is None,"ARCHIVE_IDENTITY")
                    prev=-1
                    for row in item["rows"]:
                        ts,bar=e.w.n._bar(row,digits[item["symbol_id"]])
                        e.w.old.need(ts>prev and ts not in buffers[ordinal] and
                          (ts-e.w.n.START)//604800==segment-1,"ARCHIVE_ROW_TIMESTAMPS")
                        prev=ts;buffers[ordinal][ts]=bar;count+=1
                e.w.old.need(count==entry["ROW_COUNT"] and entry["PROTECTED_FORWARD_ROW_COUNT"]==0,"ARCHIVE_ROW_COUNTS")
                rowcount+=count
                provenance.append({"segment":segment,"shard":group,
                  "cipher_sha256":entry["ENCRYPTED_ASSET_SHA256"],
                  "canonical_sha256":entry["PLAINTEXT_CANONICAL_SHA256"],"rows":count})
            PHASE="NUMERIC_DEVELOPMENT"
            for ordinal,bars in buffers.items():
                allresult.append({"ordinal":ordinal,"symbol_id":master[ordinal-1]["symbol_id"],
                    "symbol":master[ordinal-1]["symbol"],"asset_class":master[ordinal-1]["asset_class"],
                    "source_rows":len(bars),"result":evaluate(bars)})
            del buffers
            PHASE="SOURCE_READ"
            e.w.old.budget(maxwall=1500,maxcpu=1200,maxkib=2097152)
        e.w.old.need(len(allresult)==1576 and len(provenance)==100 and rowcount==3355389,"FULL_CORPUS_COMPLETENESS")
        weeks=[merge([x["result"]["four_weeks"][w] for x in allresult]) for w in range(4)]
        classnames=sorted(set(x["asset_class"] for x in allresult))
        classes={c:[merge([x["result"]["four_weeks"][w] for x in allresult if x["asset_class"]==c]) for w in range(4)] for c in classnames}
        isoweeks=sorted(set(k for x in allresult for k in x["result"]["iso_utc"]))
        iso={k:merge([x["result"]["iso_utc"][k] for x in allresult if k in x["result"]["iso_utc"]]) for k in isoweeks}
        e.w.old.need(all(m["calendar"]==1576*42 for m in weeks),"ORIGINAL_CALENDAR_FIXED")
        design=json.loads((e.a.ROOT/(P+"DESIGN_V1.json")).read_text())
        summary={"schema":"mxm.private.authentic.extrema.order.development.v1",
          "new_exact":"H1_EXTREMA_TEMPORAL_PRECEDENCE_FIXED_DIRECTION_V1",
          "design":design,"identities":1576,"shards":100,"authentic_m5_rows":rowcount,
          "four_weeks":weeks,"iso_utc":iso,"all_classes":classes,
          "cost":"HISTORICAL_SIDE_SPREAD_FEES_FINANCING_CONVERSION_SLIPPAGE_FILLS_NOT_PAIRED",
          "mean_minus_flat_bps_is_sensitivity_not_actual_net":True,
          "domain":"DEVELOPMENT_ONLY","broker_requests":0,"orders":0,"protected_forward":False,
          "alpha_certified":False,"HARD21_certified":False,"independent_confirmation":False,
          "selection_history":"ONE_ADDITIONAL_EXPLORATORY_EXPOSURE_AFTER_PRIOR_WICK_AND_MULTISCALE_TESTS"}
        PHASE="PRIVATE_ENCRYPTED_DELIVERY"
        rt.output(head,auth,tmp,key,"extrema",{"summary":summary,"all_identities":allresult,
          "source_provenance":provenance},summary)
if __name__=="__main__":
    try:main()
    except Exception as exc:
        rt.fail(exc,PHASE)
        raise SystemExit(2) from None
