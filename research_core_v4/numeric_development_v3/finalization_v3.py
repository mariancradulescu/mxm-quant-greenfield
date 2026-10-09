"""Crash-consistent delivery, without a scientific reducer or input acquisition.

Only the immutable completion ref plus full referenced-byte verification is
authoritative. Release bodies and delivery files remain NOT_PERSISTED. An
unanchored completion file is a prepared marker, never global success.
"""
import base64
import gzip
import hashlib
import json
from research_core_v4.numeric_development_v2 import machine_v2 as v2
from research_core_v4.numeric_development_v2 import authority_v2 as a
from research_core_v4.numeric_development_v1 import numeric_machine_entrypoint_v1 as old
from research_core_v4.numeric_development_v1.public_output_guard_v1 import safe_public_git_blob, validate_public_blob, ROOT as PUB

JOURNAL="finalization-input.mxmenc"
REPORT="complete-development-result.mxmenc"
STATE="complete-scientific-state.mxmenc"
RECEIPT="complete-final-receipt.mxmenc"
ATTEST="verified-delivery-attestation.mxmenc"

class Store(v2.Store):
    def paths(self):
        stem="REAL_DEVELOPMENT" if self.mode=="real" else "FABRICATED_FINAL_"+self.name.rsplit("-",1)[-1].upper()
        return PUB+stem+"_DELIVERY_V1.json",PUB+stem+"_COMPLETION_V1.json"
    def completion_tag(self):
        identity=self.arm["invocation_id"] if self.mode=="real" else a.sha(self.name.encode())
        return "mxm-numeric-v3-complete-"+self.mode+"-"+identity
    def asset(self,name):
        matches=[x for x in old.api("releases/"+str(self.release["id"])+"/assets?per_page=100") if x["name"]==name]
        a.need(len(matches)<=1,"FINAL_ASSET_DUPLICATE")
        return matches[0] if matches else None
    def load_named(self,name,expected_cipher=None):
        asset=self.asset(name);a.need(asset is not None,"FINAL_ASSET_ABSENT")
        digest=asset.get("digest","")
        a.need(digest.startswith("sha256:") and (expected_cipher is None or digest=="sha256:"+expected_cipher),"FINAL_ASSET_DIGEST")
        blob=old.download(asset["browser_download_url"],asset["size"])
        a.need(len(blob)==asset["size"] and a.sha(blob)==digest[7:],"FINAL_CIPHERTEXT_READBACK")
        packed=old.crypto.decrypt_package(blob,private_key=self.key,
          expected_public_spki_sha256=old.FP if self.mode=="real" else self.synthetic_fp,temp_parent=self.tmp)
        raw=gzip.decompress(packed);value=old.crypto.strict_json(raw)
        a.need(a.enc(value)==raw,"FINAL_CANONICAL_READBACK")
        meta={"id":asset["id"],"name":name,"size":asset["size"],"ciphertext_sha256":digest[7:],
          "canonical_sha256":a.sha(raw),"gzip_sha256":a.sha(packed),"url":asset["browser_download_url"]}
        return value,meta
    def put(self,value,name):
        if self.asset(name):
            got,meta=self.load_named(name)
            a.need(got==value,"FINAL_IDEMPOTENCE_CONFLICT")
            return meta
        return self.encrypted(value,name)
    def git_bytes(self,path,head):
        obj=old.api("contents/"+path+"?ref="+head)
        return base64.b64decode(obj["content"])
    def publish_exact(self,document,path,hook=lambda _:None,kind="delivery"):
        expected=validate_public_blob(path,document)
        # Only allowlisted status bytes enter the actual blob POST.
        blob=safe_public_git_blob(path,document,lambda raw:old.api("git/blobs",{
          "content":base64.b64encode(raw).decode(),"encoding":"base64"}))
        a.need(bool(blob.get("sha")),"GIT_BLOB_MISSING_SHA")
        current=old.api("git/ref/heads/"+old.BRANCH)["object"]["sha"]
        remote=old.api("git/trees/"+current+"?recursive=1")
        a.need(remote.get("truncated") is False,"FINAL_SOURCE_TREE_TRUNCATED")
        blobs={x["path"]:x["sha"] for x in remote["tree"] if x["type"]=="blob"}
        for bound_path,bound_sha256 in self.arm["bindings"].items():
            data=(old.ROOT/bound_path).read_bytes()
            a.need(a.sha(data)==bound_sha256 and blobs.get(bound_path)==hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest(),"FINAL_BOUND_SOURCE_DRIFT")
        comparison=old.api("compare/"+self.arm["source_head"]+"..."+current)
        a.need(comparison["status"] in ("ahead","identical"),"FINAL_SOURCE_ANCESTRY")
        # A recovery checkout may precede already durable delivery commits.
        # Every immutable bound source is checked by the presecret ARM gate;
        # this publication appends only the guarded single status path.
        # Validate the exact target again at the tree mutation boundary. A
        # bound-source pathname can never be substituted for the guarded path.
        a.need(validate_public_blob(path,document)==expected,"FINAL_PUBLIC_TARGET_DRIFT")
        tree=old.api("git/trees",{"base_tree":old.api("git/commits/"+current)["tree"]["sha"],
          "tree":[{"path":path,"mode":"100644","type":"blob","sha":blob["sha"]}]})
        commit=old.api("git/commits",{"message":"Persist guarded V3 finalization "+kind+" [skip ci]",
          "parents":[current],"tree":tree["sha"]})
        a.need(old.api("git/ref/heads/"+old.BRANCH)["object"]["sha"]==current,"PUBLICATION_CAS_DRIFT")
        old.api("git/refs/heads/"+old.BRANCH,{"sha":commit["sha"],"force":False},method="PATCH")
        self.head=commit["sha"]
        if kind=="completion":hook("before_completion_readback")
        a.need(self.git_bytes(path,self.head)==expected,"PUBLIC_GIT_READBACK")
        return {"head":self.head,"path":path,"sha256":a.sha(expected)}
    def prepare(self,report,engine,start):
        if self.asset(JOURNAL):
            journal,meta=self.load_named(JOURNAL)
            validate_journal(self,journal)
            a.need(journal["report"]==report and journal["engine"]==engine,"FINAL_JOURNAL_SCIENCE_CONFLICT")
        else:
            journal={"schema":"mxm.numeric.finalization.input.v3","arm_sha256":a.sha(a.enc(self.arm)),
              "approval_sha256":self.approval_sha,"invocation_id":self.arm["invocation_id"],
              "original_run":self.original_run,"source_head":self.release["target_commitish"],
              "bindings":self.arm["bindings"],"report":report,"engine":engine,
              "resumed_from_shard":start,"prefix_assets":list(self.uploaded),"resources":old.usage()}
            meta=self.put(journal,JOURNAL)
        self.body(status(journal,"NOT_PERSISTED",meta))
        return journal
    def finalization_recovery(self,auth,previous):
        self.original_run=previous;self.name=v2.release_name(self.arm,previous)
        refs=v2.existing_ref(v2.claim_name(self.arm));a.need(len(refs)==1,"ORIGINAL_INVOCATION_NOT_CLAIMED")
        original=refs[0]["object"]["sha"]
        a.ancestor(self.arm["source_head"],original);a.ancestor(original,self.head)
        self.release=old.api("releases/tags/"+self.name)
        body=json.loads(self.release["body"]);validate_public_blob(v2.CHECK_STATUS,body)
        a.need(self.release["target_commitish"]==original and body["source_head"]==original and
          body["run_id"]==previous and body["phase"]=="FINAL" and body["status"]=="NOT_PERSISTED","FINAL_RECOVERY_IDENTITY")
        a.recovery_gate(auth,self.arm,self.approval_sha,previous,body)
        a.need(auth["next_shard"]==100,"FINAL_RECOVERY_NO_SHARD_REPLAY")
        # Authenticate the exact receipt named by the independent recovery.
        anchored,_=self.load_named(body["encrypted_artifact_name"],body["encrypted_artifact_sha256"])
        journal,_=self.load_named(JOURNAL)
        validate_journal(self,journal)
        if body["encrypted_artifact_name"]!=JOURNAL:
            a.need(anchored["journal"]["canonical_sha256"]==a.sha(a.enc(journal)),"FINAL_RECOVERY_JOURNAL_BINDING")
            self.restore(anchored["journal"])
        a.need(all(auth["previous_resource_ceiling"][k]>=journal["resources"][k]
          for k in auth["previous_resource_ceiling"]),"FINAL_RECOVERY_RESOURCE_UNDERSTATEMENT")
        # A new independently accepted recovery is one-use, even after a crash.
        tag="mxm-numeric-v3-finalization-recovery-"+self.mode+"-"+a.sha(a.enc(auth))
        a.need(not v2.existing_ref(tag),"CONSUMED_RECOVERY")
        old.api("git/refs",{"ref":"refs/tags/"+tag,"sha":self.head})
        self.claimed=True;self.last=body;self.prior=auth["previous_resource_ceiling"]
        return journal

def validate_journal(store,j):
    a.need(j["schema"]=="mxm.numeric.finalization.input.v3" and
      j["arm_sha256"]==a.sha(a.enc(store.arm)) and j["approval_sha256"]==store.approval_sha and
      j["invocation_id"]==store.arm["invocation_id"] and j["bindings"]==store.arm["bindings"] and
      j["original_run"]==store.original_run and j["source_head"]==store.release["target_commitish"],"FINAL_JOURNAL_BINDING")
    a.need(j["engine"]["next_shard"]==100,"FINAL_JOURNAL_INCOMPLETE")
    if store.mode=="real":
        a.need(j["engine"]["rows"]==v2.n.EXPECTED_ROWS and len(j["engine"]["states"])==1576 and
          len(j["report"]["identity_results"])==1576 and set(j["report"]["full_frontier"])=={"0","300","900"},"FINAL_REAL_COMPLETENESS")

def status(j,state,meta):
    return v2.safe_status(j["source_head"],"FINAL",state,run_id=j["original_run"],
      encrypted_artifact_name=meta["name"],encrypted_artifact_sha256=meta["ciphertext_sha256"],failure_code="NONE")

def verify_complete(store):
    refs=v2.existing_ref(store.completion_tag())
    if not refs:return None
    a.need(len(refs)==1,"COMPLETION_REF_AMBIGUOUS")
    head=refs[0]["object"]["sha"];delivery_path,marker_path=store.paths()
    raw=store.git_bytes(marker_path,head);doc=old.crypto.strict_json(raw)
    a.need(validate_public_blob(marker_path,doc)==raw and doc["status"]=="PASS" and doc["phase"]=="FINAL","COMPLETION_MARKER_BYTES")
    att,attmeta=store.load_named(doc["encrypted_artifact_name"],doc["encrypted_artifact_sha256"])
    a.need(att["schema"]=="mxm.numeric.delivery.attestation.v3" and att["marker_path"]==marker_path,"COMPLETION_ATTESTATION")
    journal=store.restore(att["journal"]);validate_journal(store,journal)
    a.need(raw==validate_public_blob(marker_path,status(journal,"PASS",attmeta)),"COMPLETION_IDENTITY")
    receipt=store.restore(att["receipt"])
    a.need(receipt["schema"]=="mxm.numeric.final.receipt.v3" and receipt["journal"]==att["journal"],"COMPLETION_RECEIPT_BINDING")
    a.need(store.restore(receipt["report"])==journal["report"] and
      store.restore(receipt["state"])==journal["engine"],"COMPLETION_SCIENTIFIC_BYTES")
    for meta in journal["prefix_assets"]:store.restore(meta)
    delivery=att["public_git"]
    a.need(delivery["path"]==delivery_path and a.sha(store.git_bytes(delivery_path,delivery["head"]))==delivery["sha256"],"COMPLETION_PUBLIC_GIT_BYTES")
    a.need(store.git_bytes(delivery_path,delivery["head"])==validate_public_blob(delivery_path,status(journal,"NOT_PERSISTED",att["receipt"])),"COMPLETION_PUBLIC_GIT_IDENTITY")
    body=old.api("releases/"+str(store.release["id"]))["body"].encode()
    a.need(a.sha(body)==att["release_body_sha256"] and body==validate_public_blob(v2.CHECK_STATUS,status(journal,"NOT_PERSISTED",att["receipt"])),"COMPLETION_RELEASE_BYTES")
    return {"status":"PASS_COMPLETE_DELIVERY_VERIFIED","completion_commit":head,
      "completion_ref":store.completion_tag(),"attestation":attmeta,"public_git":delivery,
      "scientific_execution_replayed":False}

def finish(store,journal,hook=lambda _:None):
    old.budget(maxwall=a.BUDGET["wall_seconds"]-store.prior["wall_seconds"],
      maxcpu=a.BUDGET["cpu_seconds"]-store.prior["cpu_seconds"])
    validate_journal(store,journal)
    completed=verify_complete(store)
    if completed:return completed
    _,journal_meta=store.load_named(JOURNAL)
    hook("before_report")
    report=store.put(journal["report"],REPORT)
    hook("after_report")
    state=store.put(journal["engine"],STATE)
    receipt=store.put({"schema":"mxm.numeric.final.receipt.v3","journal":journal_meta,
      "report":report,"state":state,"prefix_assets":journal["prefix_assets"],
      "resources":journal["resources"],"original_run":journal["original_run"],
      "resumed_from_shard":journal["resumed_from_shard"]},RECEIPT)
    hook("after_receipt");hook("before_public_git")
    pending=status(journal,"NOT_PERSISTED",receipt)
    delivery_path,marker_path=store.paths()
    if store.asset(ATTEST):
        att,attmeta=store.load_named(ATTEST)
        a.need(att["receipt"]==receipt and att["journal"]==journal_meta,"FINAL_ATTESTATION_CONFLICT")
        a.need(a.sha(store.git_bytes(delivery_path,att["public_git"]["head"]))==att["public_git"]["sha256"],"FINAL_PRIOR_GIT_READBACK")
    else:
        delivery=store.publish_exact(pending,delivery_path,hook)
        hook("after_public_git")
        store.body(pending)
        body=old.api("releases/"+str(store.release["id"]))["body"].encode()
        a.need(body==validate_public_blob(v2.CHECK_STATUS,pending),"FINAL_RELEASE_READBACK")
        att={"schema":"mxm.numeric.delivery.attestation.v3","journal":journal_meta,"receipt":receipt,
          "public_git":delivery,"release_body_sha256":a.sha(body),"marker_path":marker_path}
        attmeta=store.put(att,ATTEST)
    # Reverify all mandatory encrypted/Git/Release bytes immediately before
    # preparing the marker. No acknowledgement or exception handler is relied on.
    a.need(store.restore(receipt)=={"schema":"mxm.numeric.final.receipt.v3","journal":journal_meta,
      "report":report,"state":state,"prefix_assets":journal["prefix_assets"],"resources":journal["resources"],
      "original_run":journal["original_run"],"resumed_from_shard":journal["resumed_from_shard"]},"FINAL_RECEIPT_READBACK")
    a.need(store.restore(report)==journal["report"] and store.restore(state)==journal["engine"],"FINAL_OUTPUT_READBACK")
    for meta in journal["prefix_assets"]:store.restore(meta)
    a.need(a.sha(old.api("releases/"+str(store.release["id"]))["body"].encode())==att["release_body_sha256"],"FINAL_RELEASE_READBACK")
    marker=store.publish_exact(status(journal,"PASS",attmeta),marker_path,hook,"completion")
    old.budget(maxwall=a.BUDGET["wall_seconds"]-store.prior["wall_seconds"],
      maxcpu=a.BUDGET["cpu_seconds"]-store.prior["cpu_seconds"])
    # Linearization point. It is impossible to reach this POST before all
    # mandatory prior persistence and readbacks succeeded. Concurrent writers
    # cannot replace the completion ref. A lost POST response is reconciled by
    # the reader; a Release body or an unanchored Git file is insufficient.
    old.api("git/refs",{"ref":"refs/tags/"+store.completion_tag(),"sha":marker["head"]})
    hook("after_completion_ref")
    result=verify_complete(store);a.need(result is not None,"FINAL_COMPLETION_READBACK")
    return result
