"""Read authenticated Copilot account quota without sending any AI prompt.

Requires github-copilot-sdk==1.0.14, whose managed CLI runtime is pinned by the wheel.
Null fields mean the account RPC did not disclose a supported value.
"""
from __future__ import annotations
import argparse
import asyncio
import json
from pathlib import Path
from research_v3.runtime_v2_primitives import atomic_write_json, iso

REL=Path("research_v3/ai_director/COPILOT_ACCOUNT_QUOTA_V1.json")
SDK_PIN="github-copilot-sdk==1.0.14"

def normalize(snapshot):
    if snapshot is None:
        return {"entitlement_requests":None,"used_requests":None,"remaining_percentage":None,"reset_date":None}
    return {name:getattr(snapshot,name,None) for name in
            ("entitlement_requests","used_requests","remaining_percentage","reset_date")}

async def fetch_account_quota():
    from copilot import CopilotClient
    from copilot.generated.rpc_types import AccountGetQuotaRequest
    async with CopilotClient() as client:
        result=await client.rpc.account.get_quota(AccountGetQuotaRequest())
        return normalize((result.quota_snapshots or {}).get("premium_interactions"))

def record(root:Path,quota:dict,*,run_id:str)->dict:
    doc={"schema":"mxm.greenfield.copilot-account-quota.v1","sdk_pin":SDK_PIN,
         "source":"Copilot SDK account.getQuota premium_interactions",
         "read_only_no_model_prompt":True,"actions_run_id":run_id,
         "observed_utc":iso(),"quota":quota,
         "session_cost_not_inferred":True}
    atomic_write_json(root/REL,doc)
    return doc

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",default=".")
    p.add_argument("--run-id",required=True)
    a=p.parse_args()
    quota=asyncio.run(fetch_account_quota())
    print(json.dumps(record(Path(a.root),quota,run_id=a.run_id),sort_keys=True))

if __name__=="__main__":
    main()
