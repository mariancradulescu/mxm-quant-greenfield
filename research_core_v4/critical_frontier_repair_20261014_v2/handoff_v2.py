"""Finite campaign handoff; serialized by workflow concurrency, never an error retry loop."""
import os,json,datetime
from .preserve_stop_v2 import api
from .storage_v2 import ROOT_TAG
from research_core_v4.full_native_frontier_20261014_v1 import runner_v1 as v1
def main():
 body=json.loads(api("releases/tags/"+ROOT_TAG)["body"])
 if body["state"]=="FINAL_CLASSIFIED_WITH_EXPLICIT_LIMITS":print("ALL_REQUIRED_IDENTITIES_CLASSIFIED_NO_NEXT_CAMPAIGN");return
 if body["state"]!="RUNNING_REPAIRED_NATIVE_WORK":raise RuntimeError("NOT_ELIGIBLE_FOR_AUTONOMOUS_CONTINUATION")
 if datetime.datetime.now(datetime.timezone.utc).isoformat()>="2026-10-18T00:00:00+00:00":raise RuntimeError("ACCEPTED_AUTHORITY_EXPIRED")
 if body["new_requests"]["BID_ASK"]>=450000 or body["new_requests"]["M5"]>=12000:raise RuntimeError("ACCEPTED_REQUEST_CAP_REACHED")
 need=lambda x,c:v1.need(x,c)
 need(api("actions/runs/38555928258")["status"]=="completed","OLD_RUN_ACTIVE")
 # Duplicate dispatch is fenced by the durable generation plus a one-use Git ref.
 claim="mxm-native-frontier-next-from-"+str(body["generation"])
 try:api("git/ref/tags/"+claim)
 except Exception as ex:
  import urllib.error
  if not isinstance(ex,urllib.error.HTTPError) or ex.code!=404:raise
 else:raise RuntimeError("GENERATION_ALREADY_DISPATCHED_NO_RETRY")
 api("git/refs","POST",{"ref":"refs/tags/"+claim,"sha":os.environ["GITHUB_SHA"]})
 api("actions/workflows/mxm-native-frontier-repaired-20261014-v2.yml/dispatches","POST",{"ref":v1.E.w.old.BRANCH,"inputs":{"previous_generation":str(body["generation"])}})
 print(json.dumps({"state":"NEXT_FINITE_CAMPAIGN_DISPATCH_ACCEPTED","from_generation":body["generation"],"remaining":body["remaining"],"source_head":os.environ["GITHUB_SHA"]}),flush=True)
if __name__=="__main__":
 try:main()
 except Exception as exc:
  cause=str(exc) if str(exc).replace("_","").isalnum() else type(exc).__name__
  print("FAIL_CLOSED_HANDOFF_"+cause,flush=True);raise SystemExit(1) from None

