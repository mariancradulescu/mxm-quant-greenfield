"""Reusable progress, heartbeat and fail-closed process-resume primitives for captures."""
from __future__ import annotations
import hashlib, json, os, time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

RUNTIME_SCHEMA="mxm.greenfield.capture-runtime-checkpoint.v1"
CONTRACT_VERSION="READ_ONLY_CAPTURE_RUNTIME_V1"

class CaptureResumeError(RuntimeError):
    pass

def utc_now()->str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def canonical_hash(value:Any)->str:
    raw=json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()

def atomic_json(path:str|Path,value:Mapping[str,Any])->None:
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+".tmp")
    tmp.write_text(json.dumps(value,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    os.replace(tmp,p)

@dataclass
class ProgressPlan:
    units:dict[str,int]=field(default_factory=dict)
    completed:dict[str,int]=field(default_factory=dict)

    def set_total(self,phase:str,total:int)->None:
        self.units[phase]=max(0,int(total))
        self.completed.setdefault(phase,0)

    def set_completed(self,phase:str,done:int)->None:
        total=self.units.get(phase,0)
        self.completed[phase]=max(0,min(int(done),total if total else int(done)))

    def total_units(self)->int:
        return sum(self.units.values())

    def done_units(self)->int:
        return sum(min(self.completed.get(k,0),v) for k,v in self.units.items())

    def overall_fraction(self)->float:
        total=self.total_units()
        return 0.0 if total<=0 else min(1.0,self.done_units()/total)

class CaptureProgress:
    def __init__(self,emit:Callable[[str],None]=print,*,heartbeat_seconds:float=15.0,clock:Callable[[],float]=time.monotonic):
        self.emit=emit; self.heartbeat_seconds=float(heartbeat_seconds); self.clock=clock
        self.started=self.clock(); self.last_emit=self.started; self.last_success=self.started
        self.retry_count=0; self.reconnect_count=0; self.phase="INITIALIZING"; self.substage=""
        self.current_identifier=None; self.plan=ProgressPlan(); self.finalized=False
        self._phase_started=self.started; self._phase_initial_done=0

    def configure(self,phase:str,total:int,*,completed:int=0,substage:str="")->None:
        self.phase=phase; self.substage=substage; self.plan.set_total(phase,total); self.plan.set_completed(phase,completed)
        self._phase_started=self.clock(); self._phase_initial_done=completed
        self.heartbeat(force=True)

    def expand(self,phase:str,total:int)->None:
        self.plan.set_total(phase,total)

    def success(self)->None:
        self.last_success=self.clock()

    def retry(self)->None:
        self.retry_count+=1; self.heartbeat(force=True)

    def reconnect(self)->None:
        self.reconnect_count+=1; self.heartbeat(force=True)

    def update(self,done:int,*,substage:str|None=None,current_identifier:Any=None,force:bool=False)->None:
        self.plan.set_completed(self.phase,done)
        if substage is not None:self.substage=substage
        self.current_identifier=current_identifier
        self.heartbeat(force=force)

    def mark_phase_complete(self)->None:
        self.plan.set_completed(self.phase,self.plan.units.get(self.phase,0)); self.heartbeat(force=True)

    def mark_finalized(self)->None:
        self.finalized=True
        for k,v in list(self.plan.units.items()):self.plan.completed[k]=v
        self.heartbeat(force=True)

    def snapshot(self)->dict[str,Any]:
        now=self.clock(); elapsed=max(0.0,now-self.started)
        phase_total=self.plan.units.get(self.phase,0); phase_done=self.plan.completed.get(self.phase,0)
        phase_elapsed=max(1e-9,now-self._phase_started)
        progressed=max(0,phase_done-self._phase_initial_done)
        rate=progressed/phase_elapsed if progressed else 0.0
        remaining=max(0,phase_total-phase_done)
        eta=(remaining/rate) if rate>0 and progressed>=3 else None
        overall=self.plan.overall_fraction()
        if overall>=1.0 and not self.finalized: overall=min(overall,0.999999)
        return {
            "phase":self.phase,"substage":self.substage,
            "completed_work_units":phase_done,"total_work_units":phase_total,
            "phase_percent":round((100*phase_done/phase_total),2) if phase_total else None,
            "overall_percent":100.0 if self.finalized else round(100*overall,2),
            "elapsed_seconds":round(elapsed,1),
            "current_rate_units_per_second":round(rate,4) if rate else 0.0,
            "eta_seconds":round(eta,1) if eta is not None else None,
            "retry_count":self.retry_count,"reconnect_count":self.reconnect_count,
            "last_success_age_seconds":round(max(0.0,now-self.last_success),1),
            "current_identifier":self.current_identifier,
            "finalized":self.finalized,
        }

    def heartbeat(self,*,force:bool=False)->None:
        now=self.clock()
        if not force and now-self.last_emit<self.heartbeat_seconds:return
        s=self.snapshot()
        eta="?" if s["eta_seconds"] is None else f'{s["eta_seconds"]:.0f}s'
        self.emit(
            "[ACTIVE] overall={overall_percent:.2f}% phase={phase} "
            "{completed_work_units}/{total_work_units} phase_pct={phase_percent} "
            "substage={substage} elapsed={elapsed_seconds:.1f}s rate={current_rate_units_per_second:.3f}/s "
            "eta={eta} retries={retry_count} reconnects={reconnect_count} "
            "last_success_age={last_success_age_seconds:.1f}s current={current_identifier}".format(eta=eta,**s)
        )
        self.last_emit=now

class CaptureCheckpoint:
    FORBIDDEN_KEYS={"access_token","refresh_token","client_secret","clientSecret","authorization","github_token"}

    def __init__(self,path:str|Path):self.path=Path(path)

    def load(self)->dict[str,Any]|None:
        if not self.path.exists():return None
        try:doc=json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:raise CaptureResumeError("corrupt capture checkpoint") from exc
        if doc.get("schema")!=RUNTIME_SCHEMA:raise CaptureResumeError("incompatible checkpoint schema")
        self._assert_no_credentials(doc)
        return doc

    def save(self,doc:Mapping[str,Any])->None:
        x=dict(doc); x["schema"]=RUNTIME_SCHEMA; x["last_checkpoint_utc"]=utc_now()
        self._assert_no_credentials(x); atomic_json(self.path,x)

    def clear(self)->None:
        self.path.unlink(missing_ok=True)

    @classmethod
    def _assert_no_credentials(cls,value:Any)->None:
        if isinstance(value,Mapping):
            for k,v in value.items():
                if str(k) in cls.FORBIDDEN_KEYS:raise CaptureResumeError(f"credential field forbidden in checkpoint: {k}")
                cls._assert_no_credentials(v)
        elif isinstance(value,list):
            for v in value:cls._assert_no_credentials(v)

def validate_resume(
    checkpoint:Mapping[str,Any],
    *,
    account_fingerprint:str,
    collector_schema_version:str,
    tool_version:str,
    capture_contract_version:str,
    observed_symbol_universe_hash:str,
    coherence_tolerance_seconds:int,
    now_epoch:float|None=None,
)->dict[str,Any]:
    checks={
        "account_fingerprint":account_fingerprint,
        "collector_schema_version":collector_schema_version,
        "tool_version":tool_version,
        "capture_contract_version":capture_contract_version,
    }
    for key,want in checks.items():
        if checkpoint.get(key)!=want:raise CaptureResumeError(f"unsafe resume blocked: {key} mismatch")
    old_hash=checkpoint.get("observed_or_frozen_symbol_universe_hash")
    if old_hash and old_hash!=observed_symbol_universe_hash:
        raise CaptureResumeError("unsafe resume blocked: current broker symbol universe drift detected")
    now=time.time() if now_epoch is None else now_epoch
    stamp=checkpoint.get("last_checkpoint_epoch")
    age=None if stamp is None else max(0.0,now-float(stamp))
    refresh_time_sensitive=bool(age is not None and age>coherence_tolerance_seconds)
    return {
        "resume_allowed":True,
        "checkpoint_age_seconds":age,
        "reuse_static_symbol_metadata":True,
        "refresh_time_sensitive_expected_margin":refresh_time_sensitive,
        "reason":"COHERENCE_TOLERANCE_EXCEEDED_REFRESH_MARGIN_PHASE" if refresh_time_sensitive else "SAFE_RESUME",
    }

def new_checkpoint(
    *,
    capture_session_id:str,
    collector_schema_version:str,
    tool_version:str,
    capture_contract_version:str,
    account_fingerprint:str,
    capture_start_utc:str,
    observed_symbol_universe_hash:str,
)->dict[str,Any]:
    return {
        "schema":RUNTIME_SCHEMA,
        "capture_session_id":capture_session_id,
        "collector_schema_version":collector_schema_version,
        "tool_version":tool_version,
        "capture_contract_version":capture_contract_version,
        "account_fingerprint":account_fingerprint,
        "capture_start_utc":capture_start_utc,
        "last_checkpoint_utc":capture_start_utc,
        "last_checkpoint_epoch":time.time(),
        "observed_or_frozen_symbol_universe_hash":observed_symbol_universe_hash,
        "active_phase":"INITIALIZING",
        "completed_symbol_metadata_batches":[],
        "completed_symbol_ids":[],
        "completed_expected_margin_symbol_ids":[],
        "completed_leverage_ids":[],
        "retry_count":0,"reconnect_count":0,
        "partial_payload_hashes":{},
        "completion_state":"PARTIAL",
    }
