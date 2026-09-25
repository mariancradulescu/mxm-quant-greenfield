"""Signal-blind PRE-M6 09:30 causal-state supplement helpers."""
from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, time as dtime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .cost_evidence import (
    DEVELOPMENT_END_DATE,
    DEVELOPMENT_START_DATE,
    TIER1_SYMBOLS,
    SessionWindow,
    sha256_file,
)
from .ctrader_capture import CaptureContractError

PREOPEN_TZ = ZoneInfo("America/New_York")
PREOPEN_START_LOCAL = dtime(9, 15)
CASH_OPEN_LOCAL = dtime(9, 30)
PROTECTED_FORWARD_START = "2026-09-17T12:02:58Z"
PREOPEN_PLAN_REL = "data/TIER1_PREOPEN_0930_SUPPLEMENT_PLAN_V1.json"
PREOPEN_TOOL_VERSION = "MXM_M6_TIER1_PREOPEN_0930_ANDROID_STDLIB_V1"

PREOPEN_PACKAGE_FILES = (
    "M6_PREOPEN_SUPPLEMENT_RUN.py",
    "m6/__init__.py",
    "m6/_ctrader_capture_base.py",
    "m6/ctrader_capture.py",
    "m6/ctrader_transport.py",
    "m6/cost_evidence.py",
    "m6/cost_evidence_openapi.py",
    "m6/preopen_supplement.py",
    "m6/preopen_evidence_openapi.py",
    "m6/session_replay.py",
    "m6/pydroid_preopen_launcher.py",
    "m6/pydroid_oauth.py",
    "m6/ctrader_proto/__init__.py",
    "m6/ctrader_proto/OpenApiCommonModelMessages_pb2.py",
    "m6/ctrader_proto/OpenApiCommonMessages_pb2.py",
    "m6/ctrader_proto/OpenApiModelMessages_pb2.py",
    "m6/ctrader_proto/OpenApiMessages_pb2.py",
    "m6/ctrader_proto/LICENSE_SPOTWARE_OPENAPIPY.txt",
    "tools/requirements-m6-capture.txt",
    "data/TIER1_PREOPEN_0930_SUPPLEMENT_PLAN_V1.json",
    "data/NASDAQ_CASH_SESSION_CALENDAR_2022_2026_V2.json",
    "data/TIER1_DISCOVERY_EXECUTION_COST_CALIBRATION_PROTOCOL_V1.json",
    "data/TIER1_COST_EVIDENCE_CAPTURE_ACCEPTANCE_V1.json",
)


def _epoch_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def signal_blind_preopen_windows():
    protected = datetime.fromisoformat(PROTECTED_FORWARD_START.replace("Z", "+00:00"))
    out = []
    cursor = DEVELOPMENT_START_DATE
    while cursor <= DEVELOPMENT_END_DATE:
        if cursor.weekday() < 5:
            start = datetime.combine(cursor, PREOPEN_START_LOCAL, PREOPEN_TZ).astimezone(timezone.utc)
            boundary = datetime.combine(cursor, CASH_OPEN_LOCAL, PREOPEN_TZ).astimezone(timezone.utc)
            if boundary >= protected:
                raise CaptureContractError("pre-open window reaches protected-forward boundary")
            out.append(SessionWindow(
                session_date=cursor.isoformat(),
                from_ms=_epoch_ms(start),
                to_ms=_epoch_ms(boundary)-1,
                open_utc=start.isoformat(),
                close_utc=(boundary.replace(microsecond=0)).isoformat(),
            ))
        cursor = cursor.fromordinal(cursor.toordinal()+1)
    return out


def build_preopen_pydroid_package(repo_root: Path | str, zip_path: Path | str) -> str:
    root = Path(repo_root)
    target = Path(zip_path)
    missing = [rel for rel in PREOPEN_PACKAGE_FILES if not (root/rel).is_file()]
    if missing:
        raise CaptureContractError(f"pre-open package source files missing: {missing}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in PREOPEN_PACKAGE_FILES:
            info = zipfile.ZipInfo(rel, date_time=(1980,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, (root/rel).read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(target) as zf:
        if set(zf.namelist()) != set(PREOPEN_PACKAGE_FILES):
            raise CaptureContractError("pre-open package member mismatch")
    return sha256_file(target)
