"""Read only the already-COMPLETED, ORIGINAL EUR200 native CSharp results
from GitHub run 41347641856, artifact 13099648067. NO source or model replay,
CSharp execution, original H1 price requests, trading or Cloud activation.
Only existing private archive SHA, cash ledger and CSharp account are checked.
"""
import argparse,hashlib,json,os,pathlib,subprocess
from research_core_v4.laboratory import mxm_be_jpy_residual_annual_funded_20261101 as study
from research_core_v4.laboratory.common import need

ORIGINAL_RUN=41347641856
ORIGINAL_HEAD="f5f09a4d06994859fe3214a9ac5d1ab1f06704e5"
ORIGINAL_ARTIFACT=13099648067
ORIGINAL_ZIP_SHA="ad4ec7dadd0d62c196e81792e52f495de0774fb8a5aa94802ba3a51efba3cae2"
ORIGINAL_PRIVATE_SHA="39aead51b11fa8e80e457d82a519c9e11d4aaec8c80d06439bdcd2b6d2f1b8a6"
REPO="mariancradulescu/mxm-quant-greenfield"
BRANCH="mxm-remediation-p0-p4-20261015-v1"

def flag(v,label):
 need(v,"MXM_JPY_EXISTING_COLD_ONLY_"+label)
def api(path):
 return json.loads(subprocess.check_output(["gh","api","repos/"+REPO+"/"+path],text=True))
def selftest():
 flag(study.IDENT=="V4-JPY-FOURHOUR-FACTOR-RESIDUAL-20261101","IDENTITY")
 flag(study.OUT.name=="mxm-be-jpy-residual-annual-20261101","ORIGINAL_PATH")
 flag(len(ORIGINAL_ZIP_SHA)==64 and len(ORIGINAL_PRIVATE_SHA)==64,
      "PINNED_SHA")
 print("MXM_JPY_ORIGINAL_COLD_ONLY_SOURCE_BLIND_SELFTEST_OK")
def admit():
 selftest()
 flag(os.environ.get("GITHUB_REPOSITORY")==REPO and
      os.environ.get("GITHUB_REF")=="refs/heads/"+BRANCH and
      os.environ.get("GITHUB_EVENT_NAME")=="push" and
      os.environ.get("GITHUB_RUN_ATTEMPT")=="1","FIRST_ONLY_SCOPE")
 head=os.environ["GITHUB_SHA"]
 flag(api("git/ref/heads/"+BRANCH)["object"]["sha"]==head,"OFFICIAL_SHA")
 parents=api("commits/"+head)["parents"]
 flag(len(parents)==2 and parents[0]["sha"]==ORIGINAL_HEAD,"REVIEWED_COLD_MERGE")
 attempts=api("actions/workflows/mxm-be-jpy-residual-cold-only-20261101.yml/runs?per_page=100")
 pushes=[r for r in attempts["workflow_runs"] if r["event"]=="push" and r["head_branch"]==BRANCH]
 flag(attempts["total_count"]<=100 and len(pushes)==1 and
      pushes[0]["id"]==int(os.environ["GITHUB_RUN_ID"]), "NO_SECOND_COLD_READ")
 prs=api("actions/runs?event=pull_request&per_page=100")["workflow_runs"]
 green={r["name"] for r in prs if r["head_sha"]==parents[1]["sha"] and
        r["conclusion"]=="success"}
 flag({"MXM R3 protected technical installation CI",
       "MXM CSharp Pepperstone protected gateway CI"}<=green,"REQUIRED_REVIEW_CI")
 original=api("actions/runs/"+str(ORIGINAL_RUN))
 flag(original["head_sha"]==ORIGINAL_HEAD and
      original["conclusion"]=="failure" and original["run_attempt"]==1,
      "EXACT_ECONOMIC_ORIGINAL")
 a=api("actions/runs/"+str(ORIGINAL_RUN)+"/artifacts")
 flag(a["total_count"]==1 and len(a["artifacts"])==1,"ONE_ORIGINAL_ARCHIVE")
 original_art=a["artifacts"][0]
 flag(original_art["id"]==ORIGINAL_ARTIFACT and
      original_art["digest"]=="sha256:"+ORIGINAL_ZIP_SHA and
      not original_art["expired"],"ORIGINAL_ARCHIVE_SHA_AND_ID")
 jobs=api("actions/runs/"+str(ORIGINAL_RUN)+"/jobs?per_page=100")["jobs"]
 real=[j for j in jobs if j["name"]=="first-protected-original"]
 flag(len(real)==1 and real[0]["conclusion"]=="failure","ORIGINAL_COLD_FAIL")
 steps={x["name"]:x["conclusion"] for x in real[0]["steps"]}
 flag(steps["Original M5 derived annual returns, actual native EUR200 account and stress"]=="success"
      and steps["Cold independently reconcile original CSharp cash ledger under owner encryption"]=="failure",
      "ECONOMIC_RESULT_ALREADY_SAVED")
 print("MXM_ORIGINAL_13099648067_COLD_ONLY_ADMITTED_NO_MODEL_RERUN")

def read_previously_published():
 # Called after 'gh run download', without any private key.
 root=study.OUT
 r=json.loads((root/"receipt.json").read_bytes())
 flag(r["run_id"]==ORIGINAL_RUN and r["head"]==ORIGINAL_HEAD and
      r["classification"]=="NET_FAIL_FUNDED_SCENARIO" and
      r["identity"]==study.IDENT,"PUBLIC_ECONOMIC_IDENTITY")
 flag(r["scenario_results"]["0.04"]["initial_eur"]==200 and
      r["scenario_results"]["0.04"]["entries"]==149 and
      len(r["baseline_weekly_equity_observed"])==26,
      "ORIGINAL_ECONOMIC_RECEIPT")
 cipher=(root/"private.mxmenc").read_bytes()
 flag(hashlib.sha256(cipher).hexdigest()==ORIGINAL_PRIVATE_SHA and
      r["private_cipher_sha256"]==ORIGINAL_PRIVATE_SHA,
      "PRIVATE_ORIGINAL_CIPHER_SHA")
 flag(not (root/"cold.json").exists(),"COLD_PROOF_NOT_PREEXISTING")
 print("MXM_ORIGINAL_EUR200_CSHARP_AGGREGATES_VERIFIED_WITHOUT_OPENING_SOURCE")

if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("mode",choices=("selftest","admit","preflight"))
 a=p.parse_args()
 {"selftest":selftest,"admit":admit,
  "preflight":read_previously_published}[a.mode]()
