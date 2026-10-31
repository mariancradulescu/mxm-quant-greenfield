"""One bounded authentic SOURCE recovery, no rerun of closed economic models.

Verifies ALL 100 original release asset identities and decrypts ONE existing
shard, with original R3 custody, in GitHub's official protected environment.
Records source-access receipt only; never exports bars or private key.
"""
import datetime as dt
import hashlib
import json
import os
import pathlib
import subprocess
import tempfile
from . import m5_authentic_envelope as source

ROOT=source.ROOT
OUT=ROOT/"verification/be-original-custody-recovery-20261031"
FP="464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11"

def require(ok,why):
    if not ok: raise ValueError("MXM_BE_ORIGINAL_RECOVERY_"+why)

def source_manifest():
    manifest=json.loads(source.MANIFEST.read_bytes())
    entries=manifest["entries"]
    require(manifest["status"]=="COMPLETE" and manifest["DURABLE_RELEASE_IDENTITY"]==source.RELEASE_IDENTITY
            and manifest["PROTECTED_FORWARD_ROW_COUNT"]==0 and len(entries)==100
            and sum(int(e["ROW_COUNT"]) for e in entries)==3355389,"FROZEN_MANIFEST")
    names=[e["ENCRYPTED_ASSET_NAME"] for e in entries]
    require(len(set(names))==100 and all(len(e["ENCRYPTED_ASSET_SHA256"])==64
            and len(e["PLAINTEXT_CANONICAL_SHA256"])==64 for e in entries),"SHARD_IDENTITIES")
    return manifest, entries

def selftest():
    manifest, entries=source_manifest()
    first=min(entries,key=lambda e:(e["SEGMENT_INDEX"],e["SHARD_INDEX"]))
    require(first["SEGMENT_INDEX"]==1 and first["SHARD_INDEX"]==0,"FIRST_SHARD")
    require(source.REPO=="mariancradulescu/mxm-quant-greenfield","OWNER_REPOSITORY")
    require(len(source.digest(source.MANIFEST.read_bytes()))==64,"LOCAL_DIGEST")
    print("MXM_BE_ORIGINAL_SOURCE_BLIND_RECOVERY_PREFLIGHT_PASS")

def protected():
    selftest()
    require(os.getenv("GITHUB_REPOSITORY")==source.REPO and
      os.getenv("GITHUB_REF")=="refs/heads/mxm-remediation-p0-p4-20261015-v1" and
      os.getenv("GITHUB_EVENT_NAME")=="push" and
      os.getenv("GITHUB_RUN_ATTEMPT")=="1","EXACT_OFFICIAL_MACHINE_SIDE")
    sha=os.environ["GITHUB_SHA"]
    remote_head=source.gh_json("repos/"+source.REPO+"/git/ref/heads/mxm-remediation-p0-p4-20261015-v1")
    require(remote_head["object"]["sha"]==sha,"STALE_HEAD")
    manifest,entries=source_manifest()
    release=source.gh_json("repos/"+source.REPO+"/releases/tags/"+source.RELEASE_IDENTITY)
    meta={x["name"]:x for x in release["assets"]}
    require(release["target_commitish"]==manifest["ARM_COMMIT"] and
      len(meta)==100 and len(release["assets"])==100,"ORIGINAL_RELEASE")
    for entry in entries:
        asset=meta.get(entry["ENCRYPTED_ASSET_NAME"])
        require(asset is not None and asset["state"]=="uploaded" and
          asset["digest"]=="sha256:"+entry["ENCRYPTED_ASSET_SHA256"],"REMOTE_CIPHER_IDENTITY")
    first=min(entries,key=lambda e:(e["SEGMENT_INDEX"],e["SHARD_INDEX"]))
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.shallow_m5_support_v2_production import decrypt_synthetic_package
    with tempfile.TemporaryDirectory(prefix="mxm-be-source-recovery-") as path:
        temp=pathlib.Path(path)
        private_key, fp=_private_key_from_secret(temp)
        require(fp==FP,"AUTHORIZED_R3_KEY")
        shards=temp/"original";shards.mkdir(mode=0o700)
        subprocess.run(["gh","release","download",source.RELEASE_IDENTITY,
             "--repo",source.REPO,"--pattern",first["ENCRYPTED_ASSET_NAME"],
             "--dir",str(shards)],check=True,stdout=subprocess.DEVNULL,
             stderr=subprocess.DEVNULL,timeout=150)
        files=list(shards.iterdir())
        require(len(files)==1 and files[0].name==first["ENCRYPTED_ASSET_NAME"],
            "SINGLE_ORIGINAL_DOWNLOAD")
        cipher=files[0].read_bytes()
        require(hashlib.sha256(cipher).hexdigest()==first["ENCRYPTED_ASSET_SHA256"],
            "ORIGINAL_CIPHER_HASH")
        plain=decrypt_synthetic_package(cipher,private_key=private_key)
        require(hashlib.sha256(plain).hexdigest()==first["PLAINTEXT_CANONICAL_SHA256"],
            "ORIGINAL_PLAINTEXT_HASH")
        shard=json.loads(plain)
        require(shard["schema"]=="mxm.v4.shallow-m5-v2.raw-shard.v1"
            and shard["segment_index"]==first["SEGMENT_INDEX"]
            and shard["shard_index"]==first["SHARD_INDEX"]
            and shard["identity_range"]==first["IDENTITY_RANGE"],"ORIGINAL_SHARD_PROVENANCE")
        expected=list(range(first["IDENTITY_RANGE"][0],first["IDENTITY_RANGE"][1]+1))
        require([x["ordinal"] for x in shard["items"]]==expected,
            "ORIGINAL_ORDINALS")
        rows=sum(len(x["rows"]) for x in shard["items"])
        require(rows==first["ROW_COUNT"],"ORIGINAL_ROWS")
        # Verify complete M5 structure, strictly pre-protected time and noninterpolated observations.
        for item in shard["items"]:
            source.inspect_rows(item["rows"],first["SEGMENT_INDEX"],source.analysis_bucket())
    OUT.mkdir(parents=True,exist_ok=False)
    receipt={
      "schema":"mxm.be.original-source-recovery.v1",
      "source_release":source.RELEASE_IDENTITY,
      "manifest_sha256":source.digest(source.MANIFEST.read_bytes()),
      "remote_original_cipher_assets_verified":100,
      "remote_original_source_manifest_rows":3355389,
      "original_decrypted_shards_in_this_run":1,
      "first_shard_ordinal_count":len(expected),
      "first_shard_bar_count":rows,
      "original_cipher_and_plaintext_sha256_matched":True,
      "custody_source":"existing R3 protected GitHub Actions secret",
      "all_100_shards_decrypted_this_run":False,
      "new_broker_requests":0,"repeated_economic_models":0,
      "signal_or_outcome_evaluation":False,"costs_verified":False,
      "EUR200_economic_edge_proven":False,"HARD21_broker_fills":0,
      "LIVE_or_DEMO_orders":0,"cloud_activations":0,
      "private_prices_published":False,"source_key_published":False,
      "status":"ONE_SHARD_AUTHENTIC_SOURCE_RECOVERY_PROVED_NOT_FULL_DATASET_BACKTEST"}
    (OUT/"public.json").write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    print("MXM_BE_ORIGINAL_SOURCE_RECOVERY_RESULT "+json.dumps(receipt,sort_keys=True))

if __name__=="__main__":
    import sys
    require(sys.argv[1:] in (["selftest"],["protected"]),"ARGUMENTS")
    selftest() if sys.argv[1:]==["selftest"] else protected()
