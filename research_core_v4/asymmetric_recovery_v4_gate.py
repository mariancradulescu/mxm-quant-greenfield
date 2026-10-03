from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import pathlib
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPO="mariancradulescu/mxm-quant-greenfield"
BRANCH="performance-research-v3-20260922"
SCI_HEAD="68bdee4b51244ae50acd56fe868468b96106450f"
EXPECTED_SPKI="464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11"
EXPECTED_MANIFEST_SHA="d338dcaac31af05819aebd2876946f6af001c31ecca526e0424c4ddee1f3d207"
EXPECTED_PLAINTEXT_BUNDLE_SHA="efaf64d663f11d25cde5e09290e41f21bd61ceb6cede2a3893ba4514599d0ea0"
EXPECTED_ENCRYPTED_BUNDLE_SHA="e601aa8dbbd5a8dd7f76b0ca578b07e9ca3621b5518929dd95a4f0dc48dac78f"
EXPECTED_WRAPPED_SHA="8eecaca7b0e93971dc3ac50613118be7f8daaee0e620955e9c0052c011f4516f"
EXPECTED_PAYLOAD_SHA="6ae52d1123d747fdf976031cd5684fbe9255f35ff865840df86277a3ae7eee10"
PAYLOAD_REL="research_core_v4/runtime_inputs/MXM_V4_ASYMMETRIC_STAGING_PAYLOAD_V1.zip"
MANIFEST_REL="research_core_v4/runtime_inputs/V4_EXACT_M5_INPUT_MANIFEST_V2.json"
WRAPPED_REL="research_core_v4/runtime_inputs/V4_EXACT_M5_INPUT_BUNDLE_V2.bundle_key.rsa_oaep_sha256.bin"
PUBLIC_REL="research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem"
V3_AUTH_REL="research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_AUTHORITY_V3.json"
V4_PROSPECTIVE_REL="research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_AUTHORITY_V4_PROSPECTIVE.json"
V4_ACTIVE_REL="research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_AUTHORITY_V4.json"
CERT_REL="research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_RECOVERY_V4_GREENFIELD_INPUT_STAGING_CERTIFICATE_V1.json"
PREFLIGHT_REL="research_core_v4/state/V4_ASYMMETRIC_PRE_ARM_DECRYPTION_PREFLIGHT_RESULT_V1.json"
ACTIVATION_REL="research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_AUTHORITY_V4_ACTIVATION_V1.json"
STATE_REL="research_core_v4/state/V4_STATE.json"
SUPERSESSION_REL="research_core_v4/state/V4_INPUT_TRANSPORT_ASYMMETRIC_SUPERSESSION_V1.json"
PROBE_REL="research_core_v4/state/V4_ASYMMETRIC_PRIVATE_KEY_PAIR_PROBE_LATEST.json"
WORKFLOW_REL=".github/workflows/v4-greenfield-recovery-v4.yml"
ARM_REL="research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_V4_ARM_V1.json"
LOCK_REL="research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_CRASH_RECOVERY_V4_ATTEMPT_LOCK_V1.txt"
RESULT_REL="research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json"
FROZEN={
 "design":("research_core_v4/state/FIRST_REAL_MARKET_DESIGN_V2.json","3f9a6b1da92b9904da91e86d005f26e8e99d93e5e3497e1b8a72b59b1d4e590e"),
 "evaluator":("research_core_v4/response_evaluator_v3.py","bb846fb3bbbe567c53587a6c22b344ffe39af7129db5e9a4a39c77026f3ade2a"),
 "runner":("research_core_v4/development_execution_runner_v1.py","cebcf2ad4f88e40d575cb46ffc14e0862107b47a84260a15b3310f075af4f79d"),
 "semantics":("research_core_v4/frozen_v2_semantics.py","0a7bda1afe5cbe79373ee833e9d09febc08721d1826d94435f74d900f74f26ed"),
}
PARTS=[
 ("research_core_v4/runtime_inputs/V4_EXACT_M5_INPUT_BUNDLE_V2.gpg.part-000",4194304,"eee428d13c0a6e929910c2db42fbfdd84de1b21602af2892dc847703a0cd28f3"),
 ("research_core_v4/runtime_inputs/V4_EXACT_M5_INPUT_BUNDLE_V2.gpg.part-001",4194304,"b014df37873c9795c6b017b24fc91df765e8f02ed1678fc41db854d54dc392fb"),
 ("research_core_v4/runtime_inputs/V4_EXACT_M5_INPUT_BUNDLE_V2.gpg.part-002",4194304,"0fce41e120d226d99402c4ff38e76d7e722212454324d54144d376947820be4b"),
 ("research_core_v4/runtime_inputs/V4_EXACT_M5_INPUT_BUNDLE_V2.gpg.part-003",4194304,"eb243a001494521921b38edbf711597391435bad8288a6deeaa9aa786c278809"),
 ("research_core_v4/runtime_inputs/V4_EXACT_M5_INPUT_BUNDLE_V2.gpg.part-004",1174143,"3664b4c559a98e82df7db1ce0a65ba03ee79717b044a3946663494b9b85070af"),
]

def req(c:bool,m:str)->None:
    if not c: raise PermissionError("RECOVERY_V4_GATE_FAIL "+m)

def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def load(rel:str)->dict:
    x=json.loads((ROOT/rel).read_text(encoding="utf-8")); req(isinstance(x,dict),rel+" object"); return x

def canonical_sha(x)->str:
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

def expected_series()->list[dict]:
    a=load(V3_AUTH_REL)["frozen_reference"]["exact_18_series"]
    req(len(a)==18,"V3 exact-series count")
    p=load(V4_PROSPECTIVE_REL)["frozen_reference"]["exact_18_series"]
    req(a==p,"V3/prospective V4 exact-series drift")
    if (ROOT/V4_ACTIVE_REL).exists():
        req(load(V4_ACTIVE_REL)["frozen_reference"]["exact_18_series"]==a,"active V4 exact-series drift")
    return a

def verify_frozen()->dict:
    out={}
    for k,(rel,want) in FROZEN.items():
        got=sha256_file(ROOT/rel); req(got==want,"frozen science changed "+rel); out[k]=got
    req(sha256_file(ROOT/"research_core_v4/state/EXACT_SUPPORT_GEOMETRY_CALIBRATION_FULL_V3.json")=="fae10bd4817efb1a20426e2ae35171aa62bd924456c104c4d0aa1d07aec0eb05","calibration V3 changed")
    return out

def verify_public_and_probe()->dict:
    p=subprocess.run(["openssl","pkey","-pubin","-in",str(ROOT/PUBLIC_REL),"-outform","DER"],capture_output=True)
    req(p.returncode==0,"committed public key parse")
    got=hashlib.sha256(p.stdout).hexdigest(); req(got==EXPECTED_SPKI,"committed public fingerprint")
    probe=load(PROBE_REL)
    req(probe.get("conclusion")=="PASS" and probe.get("private_key_parse_status")=="VALID" and probe.get("fingerprint_status")=="MATCH","durable private-key pair probe not PASS")
    req(probe.get("private_derived_public_spki_sha256")==EXPECTED_SPKI,"durable private-key fingerprint drift")
    return {"public_spki_sha256":got,"key_probe_run_id":probe["run_id"]}

def _private_key_from_secret(tmp:Path)->tuple[Path,str]:
    raw=os.environ.get("MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM","")
    req(bool(raw),"private-key secret absent")
    cand=[]
    def add(s):
        if s and s not in cand: cand.append(s)
    add(raw); add(raw.replace("\r\n","\n").replace("\r","\n"))
    if "\\n" in raw: add(raw.replace("\\r\\n","\n").replace("\\n","\n"))
    s=raw.strip()
    if len(s)>=2 and s[0]==s[-1] and s[0] in "'\"": add(s[1:-1].replace("\\n","\n"))
    if "-----BEGIN" not in raw:
        try:
            d=base64.b64decode(raw,validate=True).decode("utf-8")
            if "-----BEGIN" in d: add(d)
        except Exception: pass
    for i,value in enumerate(cand):
        key=tmp/f"private-{i}.pem"; key.write_text(value,encoding="utf-8"); key.chmod(0o600)
        der=tmp/f"pub-{i}.der"
        r=subprocess.run(["openssl","pkey","-in",str(key),"-pubout","-outform","DER","-out",str(der)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if r.returncode==0:
            fp=sha256_file(der); der.unlink(missing_ok=True)
            if fp==EXPECTED_SPKI: return key,fp
        key.unlink(missing_ok=True); der.unlink(missing_ok=True)
    raise PermissionError("RECOVERY_V4_GATE_FAIL private-key parse/pair match")

def verify_staged_ciphertext()->tuple[dict,list[dict]]:
    mpath=ROOT/MANIFEST_REL; req(mpath.is_file(),"manifest absent"); req(sha256_file(mpath)==EXPECTED_MANIFEST_SHA,"manifest byte hash")
    m=load(MANIFEST_REL)
    req(m.get("schema")=="mxm.research-core-v4.exact-m5-input-manifest.v2","manifest schema")
    req(m.get("canonical_repository")==REPO and m.get("research_branch")==BRANCH and m.get("scientific_source_head")==SCI_HEAD,"manifest identity")
    req(m.get("public_key_spki_sha256")==EXPECTED_SPKI,"manifest public key")
    req(m.get("plaintext_bundle_sha256")==EXPECTED_PLAINTEXT_BUNDLE_SHA,"manifest plaintext bundle")
    req(m.get("encrypted_bundle_sha256")==EXPECTED_ENCRYPTED_BUNDLE_SHA,"manifest encrypted bundle")
    req(m.get("exact_series_count")==18 and m.get("exact_18_series")==expected_series(),"manifest exact 18 series")
    req(m.get("market_outcome_inspected") is False and m.get("plaintext_persisted") is False and m.get("private_key_persisted") is False and m.get("raw_bundle_passphrase_persisted") is False,"manifest secrecy/outcome boundary")
    req(m.get("key_wrap")=={"algorithm":"RSA_OAEP","hash":"SHA256","mgf1_hash":"SHA256"},"manifest OAEP params")
    wrap=m.get("wrapped_bundle_key",{}); req(wrap.get("filename")==WRAPPED_REL and wrap.get("sha256")==EXPECTED_WRAPPED_SHA and wrap.get("size_bytes")==512,"wrapped-key manifest")
    wp=ROOT/WRAPPED_REL; req(wp.is_file() and wp.stat().st_size==512 and sha256_file(wp)==EXPECTED_WRAPPED_SHA,"wrapped key bytes")
    declared=m.get("encrypted_parts"); req(isinstance(declared,list) and len(declared)==5,"manifest parts")
    actual=[]
    h=hashlib.sha256()
    for (rel,size,digest),item in zip(PARTS,declared):
        req(item=={"filename":rel,"sha256":digest,"size_bytes":size},"part declaration "+rel)
        p=ROOT/rel; req(p.is_file() and p.stat().st_size==size and sha256_file(p)==digest,"part bytes "+rel)
        actual.append(item)
        with p.open("rb") as f:
            for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    req(h.hexdigest()==EXPECTED_ENCRYPTED_BUNDLE_SHA,"ordered encrypted bundle hash")
    return m,actual

def verify_plaintext_dir(raw:Path,series:list[dict])->list[dict]:
    wanted={f"{int(x['symbol_id'])}_M5.csv":x for x in series}
    actual={p.name for p in raw.iterdir() if p.is_file()}; req(actual==set(wanted),"plaintext file set")
    out=[]
    for name,item in sorted(wanted.items(),key=lambda z:int(z[1]["symbol_id"])):
        p=raw/name; req(sha256_file(p)==item["series_sha256"],"plaintext sha "+name)
        with p.open("r",encoding="utf-8",newline="") as f:
            r=csv.DictReader(f); req("time_utc" in (r.fieldnames or []),"time_utc "+name)
            n=0; first=None; last=None
            for row in r:
                t=row["time_utc"]; first=t if first is None else first; last=t; n+=1
        req(n==item["row_count"],"row count "+name); req(first==item["first_timestamp_utc"],"first timestamp "+name); req(last==item["last_timestamp_utc"],"last timestamp "+name)
        out.append({"symbol":item["symbol"],"symbol_id":item["symbol_id"],"sha256":item["series_sha256"],"row_count":n,"first_timestamp_utc":first,"last_timestamp_utc":last})
    return out

def decrypt_verify(raw_output:Path|None=None)->dict:
    verify_public_and_probe(); m,_=verify_staged_ciphertext(); frozen=verify_frozen()
    td_obj=tempfile.TemporaryDirectory(prefix="mxm-v4-asym-"); td=Path(td_obj.name)
    gpghome=td/"gnupg"; gpghome.mkdir(mode=0o700)
    try:
        key,fp=_private_key_from_secret(td)
        passfile=td/"bundle-passphrase"; 
        r=subprocess.run(["openssl","pkeyutl","-decrypt","-inkey",str(key),"-in",str(ROOT/WRAPPED_REL),"-out",str(passfile),"-pkeyopt","rsa_padding_mode:oaep","-pkeyopt","rsa_oaep_md:sha256","-pkeyopt","rsa_mgf1_md:sha256"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        req(r.returncode==0 and passfile.is_file() and passfile.stat().st_size>0,"RSA-OAEP bundle-key unwrap")
        passfile.chmod(0o600)
        cipher=td/"bundle.gpg"
        with cipher.open("wb") as w:
            for rel,_,_ in PARTS:
                with (ROOT/rel).open("rb") as f:
                    for b in iter(lambda:f.read(1024*1024),b""): w.write(b)
        req(sha256_file(cipher)==EXPECTED_ENCRYPTED_BUNDLE_SHA,"reconstructed ciphertext")
        tar=td/"bundle.tar"
        r=subprocess.run(["gpg","--homedir",str(gpghome),"--no-symkey-cache","--batch","--yes","--pinentry-mode","loopback","--passphrase-file",str(passfile),"--output",str(tar),"--decrypt",str(cipher)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        req(r.returncode==0 and tar.is_file(),"OpenPGP decrypt/integrity")
        req(sha256_file(tar)==EXPECTED_PLAINTEXT_BUNDLE_SHA,"plaintext deterministic bundle hash")
        raw=raw_output if raw_output is not None else td/"raw"
        raw.mkdir(parents=True,exist_ok=True)
        series=expected_series(); expected_names={f"{int(x['symbol_id'])}_M5.csv" for x in series}
        with tarfile.open(tar,"r:") as tf:
            names=[x.name for x in tf.getmembers() if x.isfile()]
            req(set(names)==expected_names and len(names)==18,"tar exact 18 file set")
            for member in tf.getmembers():
                req(member.isfile() and member.name in expected_names and "/" not in member.name and "\\" not in member.name,"unsafe/unexpected tar member")
            tf.extractall(raw,filter="data")
        rows=verify_plaintext_dir(raw,series)
        return {"private_key_parse_status":"VALID","private_derived_public_spki_sha256":fp,"fingerprint_status":"MATCH","wrapped_bundle_passphrase_decrypt":"SUCCESS","encrypted_bulk_decrypt":"SUCCESS","openpgp_integrity_check":"SUCCESS","plaintext_bundle_sha256":EXPECTED_PLAINTEXT_BUNDLE_SHA,"exact_plaintext_series_count":18,"all_18_sha256_match":True,"all_18_row_counts_match":True,"all_18_first_timestamps_match":True,"all_18_last_timestamps_match":True,"frozen_hashes":frozen,"series":rows}
    finally:
        subprocess.run(["gpgconf","--homedir",str(gpghome),"--kill","gpg-agent"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if raw_output is None: td_obj.cleanup()
        else:
            for p in td.iterdir():
                try:
                    if p.is_file(): p.unlink()
                except Exception: pass
            td_obj.cleanup()

def verify_boundary(*,arm_allowed:bool=False)->None:
    if not arm_allowed: req(not (ROOT/ARM_REL).exists(),"ARM already present")
    req(not (ROOT/LOCK_REL).exists(),"Recovery V4 attempt lock already present")
    req(not (ROOT/RESULT_REL).exists(),"canonical result already present")
    for rel in [RESULT_REL+".tmp","V4_FIRST_DEVELOPMENT_RESPONSE_RESULT_V1.json","V4_FIRST_DEVELOPMENT_RESPONSE_RESULT_V1.json.tmp"]: req(not (ROOT/rel).exists(),"alternate/partial canonical result present")
    st=load(STATE_REL)
    prep=st.get("recovery_v4_preparation",{})
    if prep: req(prep.get("accepted_canonical_result_count",0)==0 and prep.get("real_execution_authorized") is False,"V4 state execution/result boundary")

def validate_certificate(final_required:bool=False)->dict:
    cert=load(CERT_REL)
    req(cert.get("schema")=="mxm.research-core-v4.recovery-v4-greenfield-input-staging-certificate.v1","certificate schema")
    allowed={"STAGED_NOT_ARMED_NOT_EXECUTED_PENDING_REAL_PREARM_PREFLIGHT","STAGED_VALIDATED_NOT_ARMED_NOT_EXECUTED"}
    req(cert.get("status") in allowed,"certificate status")
    if final_required: req(cert.get("status")=="STAGED_VALIDATED_NOT_ARMED_NOT_EXECUTED","final certificate required")
    req(cert.get("canonical_repository")==REPO and cert.get("research_branch")==BRANCH and cert.get("scientific_source_head")==SCI_HEAD,"certificate identity")
    req(cert.get("transport_payload_file")==PAYLOAD_REL and cert.get("transport_payload_sha256")==EXPECTED_PAYLOAD_SHA,"certificate restart-payload binding")
    req((ROOT/PAYLOAD_REL).is_file() and sha256_file(ROOT/PAYLOAD_REL)==EXPECTED_PAYLOAD_SHA,"durable encrypted restart payload")
    req(cert.get("rsa_public_key_spki_sha256")==EXPECTED_SPKI,"certificate public fingerprint")
    req(cert.get("rsa_oaep_parameters")=={"algorithm":"RSA_OAEP","hash":"SHA256","mgf1_hash":"SHA256"},"certificate OAEP")
    req(cert.get("wrapped_bundle_key",{}).get("sha256")==EXPECTED_WRAPPED_SHA,"certificate wrapped key")
    req(cert.get("plaintext_bundle_sha256")==EXPECTED_PLAINTEXT_BUNDLE_SHA and cert.get("encrypted_bundle_sha256")==EXPECTED_ENCRYPTED_BUNDLE_SHA,"certificate bundle hashes")
    req(cert.get("exact_18_series")==expected_series(),"certificate exact 18")
    req(cert.get("accepted_canonical_result_count")==0 and cert.get("arm_present_at_staging") is False and cert.get("attempt_lock_present_at_staging") is False and cert.get("real_execution_authorized_at_staging") is False,"certificate hard stop")
    req(cert.get("installed_recovery_workflow_sha256")==sha256_file(ROOT/WORKFLOW_REL),"certificate runtime workflow binding")
    for rel,want in cert.get("execution_path_bindings",{}).items(): req(sha256_file(ROOT/rel)==want,"execution control binding "+rel)
    req(cert.get("asymmetric_transport_supersession_sha256")==sha256_file(ROOT/SUPERSESSION_REL),"certificate transport supersession binding")
    return cert

def run_preflight(output:Path)->dict:
    verify_boundary(); cert=validate_certificate(False)
    result={"schema":"mxm.research-core-v4.asymmetric-pre-arm-decryption-preflight-result.v1","run_id":int(os.environ.get("GITHUB_RUN_ID","0") or 0),"run_attempt":int(os.environ.get("GITHUB_RUN_ATTEMPT","1") or 1),"trigger_head":os.environ.get("GITHUB_SHA"),"certificate_sha256_at_preflight":sha256_file(ROOT/CERT_REL),"secret_status":"PRESENT","response_computed":False,"market_outcome_exposed":False,"plaintext_artifact_persisted":False,"arm_created":False,"attempt_lock_created":False}
    result.update(decrypt_verify())
    verify_boundary()
    result["conclusion"]="PASS"; output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:result[k] for k in ["conclusion","run_id","private_key_parse_status","private_derived_public_spki_sha256","fingerprint_status","exact_plaintext_series_count","plaintext_bundle_sha256"]},sort_keys=True))
    return result

def arm_binding_files()->list[str]:
    return [V4_ACTIVE_REL,CERT_REL,WORKFLOW_REL,MANIFEST_REL,
            'research_core_v4/asymmetric_recovery_v4_gate.py',
            'research_core_v4/recovery_v4_transaction_v1.py',
            'research_core_v4/numeric_environment_v1.py',
            'research_core_v4/numeric_worker_v1.py',
            'research_core_v4/runtime/NUMERIC_ENVIRONMENT_V1.json',
            'research_core_v4/runtime/numeric-requirements-v1.txt',
            'research_core_v4/state/V4_EXECUTION_PATH_DEEP_AUDIT_V1.json',
            'research_core_v4/runtime/V4_CRASH_RECOVERY_LAW_V1.json']

def build_arm_document(parent_head:str,decision:dict)->dict:
    # Pure constructor: caller must separately publish a single-file ARM commit.
    audit()
    head=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    req(head==parent_head,'constructor parent must be checked-out certified head')
    req(decision.get('explicit_separate_arm_authorization') is True and
        isinstance(decision.get('decision_id'),str) and bool(decision['decision_id']) and
        decision.get('certified_parent_head')==parent_head,'separate exact-parent governance decision')
    req(load(STATE_REL).get('execution_path_audit',{}).get('status')=='READY_FOR_SEPARATE_ARM_GOVERNANCE_DECISION','execution path not ready')
    tree=subprocess.check_output(['git','-C',str(ROOT),'rev-parse',parent_head+'^{tree}'],text=True).strip()
    return {'schema':'mxm.research-core-v4.recovery-v4-arm.v2','status':'ARMED_NOT_EXECUTED',
      'canonical_repository':REPO,'research_branch':BRANCH,'pre_arm_parent_head':parent_head,
      'pre_arm_parent_tree':tree,'bound_files_sha256':{rel:sha256_file(ROOT/rel) for rel in arm_binding_files()},
      'governance_decision':decision,'accepted_canonical_result_count':0,
      'accepted_canonical_result_limit':1,'no_prior_recovery_v4_attempt_lock':True,
      'no_canonical_result_present':True,'automatic_retry':False}

def validate_arm_binding(arm_path:Path)->dict:
    req(arm_path.resolve()==(ROOT/ARM_REL).resolve(),'canonical ARM path required')
    verify_boundary(arm_allowed=True); validate_certificate(True)
    active=load(V4_ACTIVE_REL)
    req(active.get('execution_path_bindings',{})==load(CERT_REL).get('execution_path_bindings',{}),'authority/certificate controls disagree')
    req(active.get('status')=='ACTIVE_TRANSPORT_ONLY_SUCCESSOR_STAGED_VALIDATED_NOT_ARMED_NOT_EXECUTED','active V4 authority status')
    arm=json.loads(arm_path.read_text())
    req(load(STATE_REL).get('execution_path_audit',{}).get('status')=='READY_FOR_SEPARATE_ARM_GOVERNANCE_DECISION','execution path not certified ready')
    req(arm.get('schema')=='mxm.research-core-v4.recovery-v4-arm.v2' and arm.get('status')=='ARMED_NOT_EXECUTED' and 'arm_commit' not in arm,'nonrecursive ARM schema')
    req(arm.get('canonical_repository')==REPO and arm.get('research_branch')==BRANCH,'ARM repository/branch')
    head=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    req(subprocess.check_output(['git','-C',str(ROOT),'show',head+':'+ARM_REL])==arm_path.read_bytes(),'ARM worktree bytes differ from committed event')
    req(os.environ.get('GITHUB_SHA')==head and os.environ.get('GITHUB_RUN_ATTEMPT')=='1','exact event head / first workflow attempt only')
    parents=subprocess.check_output(['git','-C',str(ROOT),'rev-list','--parents','-n','1','HEAD'],text=True).split()
    req(len(parents)==2 and parents[1]==arm.get('pre_arm_parent_head'),'ARM parent binding')
    tree=subprocess.check_output(['git','-C',str(ROOT),'rev-parse',parents[1]+'^{tree}'],text=True).strip()
    req(tree==arm.get('pre_arm_parent_tree'),'parent tree binding')
    changed=subprocess.check_output(['git','-C',str(ROOT),'diff-tree','--no-commit-id','--name-only','-r','HEAD'],text=True).splitlines()
    req(changed==[ARM_REL],'isolated ARM commit')
    req(arm.get('bound_files_sha256')=={rel:sha256_file(ROOT/rel) for rel in arm_binding_files()},'complete control/input/environment bindings')
    d=arm.get('governance_decision',{})
    req(d.get('explicit_separate_arm_authorization') is True and d.get('certified_parent_head')==parents[1] and isinstance(d.get('decision_id'),str) and bool(d['decision_id']),'explicit separate governance decision')
    req(arm.get('accepted_canonical_result_count')==0 and arm.get('accepted_canonical_result_limit')==1 and arm.get('automatic_retry') is False and arm.get('no_prior_recovery_v4_attempt_lock') is True and arm.get('no_canonical_result_present') is True,'ARM exactly-once boundary')
    subprocess.check_call(['git','-C',str(ROOT),'fetch','--no-tags','origin','+refs/heads/'+BRANCH+':refs/remotes/origin/'+BRANCH],stdout=subprocess.DEVNULL)
    remote=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','origin/'+BRANCH],text=True).strip()
    req(remote==head,'remote drift/replay before decryption')
    return {'arm_commit':head,'pre_arm_parent_head':parents[1],'arm_document_sha256':sha256_file(arm_path)}

def validate_arm_and_runtime(arm_path:Path,raw_output:Path)->dict:
    binding=validate_arm_binding(arm_path)
    out=decrypt_verify(raw_output)
    req(not (ROOT/LOCK_REL).exists() and not (ROOT/RESULT_REL).exists(),'prelock invariant')
    return {'status':'PASS_RECOVERY_V4_PRELOCK_RUNTIME_VALIDATION',**binding,**out}

def audit()->dict:
    verify_boundary(); static=verify_public_and_probe(); frozen=verify_frozen(); sup=load(SUPERSESSION_REL)
    req(sup.get("status")=="SHARED_PASSPHRASE_TRANSPORT_PERMANENTLY_SUPERSEDED_FOR_FUTURE_STAGING" and sup.get("superseded",{}).get("may_be_used_for_future_staging") is False,"old shared passphrase supersession")
    if not (ROOT/CERT_REL).exists():
        req(not (ROOT/MANIFEST_REL).exists(),"manifest present without certificate in pre-staging state")
        return {"status":"PASS_ASYMMETRIC_TRANSPORT_PRE_STAGING_NOT_ARMED","accepted_canonical_result_count":0,"arm_present":False,"attempt_lock_present":False,**static,"frozen_hashes":frozen}
    verify_staged_ciphertext(); cert=validate_certificate(True); pre=load(PREFLIGHT_REL); req(pre.get("conclusion")=="PASS" and pre.get("fingerprint_status")=="MATCH" and pre.get("exact_plaintext_series_count")==18,"preflight result")
    active=load(V4_ACTIVE_REL); req(active.get("status")=="ACTIVE_TRANSPORT_ONLY_SUCCESSOR_STAGED_VALIDATED_NOT_ARMED_NOT_EXECUTED","active V4 authority")
    req(active.get("staging_certificate_sha256")==sha256_file(ROOT/CERT_REL),"active authority certificate binding")
    act=load(ACTIVATION_REL); req(act.get("status")=="ACTIVATED_TRANSPORT_ONLY_AFTER_REAL_PREARM_PREFLIGHT_PASS" and act.get("active_recovery_authority_sha256")==sha256_file(ROOT/V4_ACTIVE_REL),"activation record")
    st=load(STATE_REL); p=st.get("recovery_v4_preparation",{})
    req(st.get("status")=="FIRST_REAL_MARKET_DESIGN_V2_ASYMMETRIC_RECOVERY_V4_STAGED_VALIDATED_NOT_ARMED_NOT_EXECUTED","V4_STATE final status")
    req(p.get("status")=="STAGED_VALIDATED_NOT_ARMED_NOT_EXECUTED" and p.get("accepted_canonical_result_count")==0 and p.get("arm_present") is False and p.get("attempt_lock_present") is False and p.get("real_execution_authorized") is False,"V4_STATE recovery V4 boundary")
    return {"status":"PASS_ASYMMETRIC_RECOVERY_V4_STAGED_VALIDATED_NOT_ARMED_NOT_EXECUTED","accepted_canonical_result_count":0,"arm_present":False,"attempt_lock_present":False,"canonical_result_present":False,"real_execution_authorized":False,"preflight_run_id":pre.get("run_id"),"staging_data_commit":cert.get("staging_data_commit"),"staging_certificate_sha256":sha256_file(ROOT/CERT_REL),"active_recovery_authority_sha256":sha256_file(ROOT/V4_ACTIVE_REL),**static,"frozen_hashes":frozen}

def main()->None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--preflight-output",type=Path)
    ap.add_argument("--prelock-report",type=Path)
    ap.add_argument("--runtime-arm",type=Path)
    ap.add_argument("--raw-output",type=Path)
    ap.add_argument("--audit",action="store_true")
    ap.add_argument("--keypair-only",action="store_true")
    x=ap.parse_args()
    modes=sum([x.preflight_output is not None,x.runtime_arm is not None,x.audit,x.keypair_only])
    req(modes==1,"choose one mode")
    if x.keypair_only:
        static=verify_public_and_probe()
        with tempfile.TemporaryDirectory(prefix="mxm-v4-keypair-") as td:
            _,fp=_private_key_from_secret(Path(td))
        print(json.dumps({"status":"PASS_PRIVATE_KEY_PARSE_AND_PUBLIC_FINGERPRINT_MATCH","private_key_parse_status":"VALID","private_derived_public_spki_sha256":fp,"fingerprint_status":"MATCH",**static},sort_keys=True))
    elif x.preflight_output is not None:
        run_preflight(x.preflight_output)
    elif x.runtime_arm is not None:
        req(x.raw_output is not None,"runtime raw output required")
        x.raw_output.mkdir(parents=True,exist_ok=True)
        report=validate_arm_and_runtime(x.runtime_arm,x.raw_output)
        if x.prelock_report is not None: x.prelock_report.write_text(json.dumps(report,sort_keys=True)+"\n")
        print(json.dumps(report,sort_keys=True))
    else:
        print(json.dumps(audit(),sort_keys=True))

if __name__=="__main__":
    main()
