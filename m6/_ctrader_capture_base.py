"""Pure clean-room helpers for the read-only cTrader M6 capture client.

This module contains no broker credentials and imports no cTrader/Twisted packages so
its safety, OAuth parsing, chunk/resume, redaction and deterministic bundle rules can
be tested in ordinary CI.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import parse_qs, urlencode, urlparse

AUTH_URL = "https://id.ctrader.com/my/settings/openapi/grantingaccess/"
TOKEN_URL = "https://openapi.ctrader.com/apps/token"
READ_ONLY_SCOPE = "accounts"
PROTECTED_FORWARD_START = "2026-09-17T12:02:58Z"
PLAN_SCHEMA = "mxm.greenfield.v2.primary-wave-02-materialization-acquisition-plan.v2"
EXPECTED_PLAN_SHA = "da9e9a65f5c8b3e9a3edb0189de6d60bee2b5cc922d0a3ea99c1dc14ef5066fa"
RAW_HEADER = ("time_utc", "open", "high", "low", "close", "tick_volume")
HISTORICAL_REQUESTS_PER_SECOND = 5
HISTORICAL_MIN_INTERVAL = 0.21
PERIOD_MINUTES = {"M15": 15, "H1": 60, "H4": 240, "D1": 1440}
CHUNK_DAYS = {"M15": 7, "H1": 28, "H4": 84, "D1": 365}
READ_ONLY_PROTO_REQUESTS = frozenset({
    "ProtoOAApplicationAuthReq",
    "ProtoOAGetAccountListByAccessTokenReq",
    "ProtoOAAccountAuthReq",
    "ProtoOAVersionReq",
    "ProtoOATraderReq",
    "ProtoOAAssetListReq",
    "ProtoOAAssetClassListReq",
    "ProtoOASymbolCategoryListReq",
    "ProtoOASymbolsListReq",
    "ProtoOASymbolByIdReq",
    "ProtoOASymbolsForConversionReq",
    "ProtoOAGetTrendbarsReq",
    "ProtoOAGetTickDataReq",
    "ProtoOAExpectedMarginReq",
})
FORBIDDEN_MUTATION_PROTO_REQUESTS = frozenset({
    "ProtoOANewOrderReq", "ProtoOACancelOrderReq", "ProtoOAAmendOrderReq",
    "ProtoOAClosePositionReq", "ProtoOAAmendPositionSLTPReq",
    "ProtoOAClosePositionByLabelReq", "ProtoOAAccountLogoutReq",
    "ProtoOASubscribeSpotsReq", "ProtoOAUnsubscribeSpotsReq",
})
_SECRET_KEYS = {
    "client_secret", "clientsecret", "access_token", "accesstoken",
    "refresh_token", "refreshtoken", "authorization_code", "authorizationcode",
    "code", "password", "authorization",
}
_SECRET_PATTERNS = [
    re.compile(r'(?i)(client_secret|access_token|refresh_token|authorization_code|password)\s*[=:]\s*([^\s,&}]+)'),
    re.compile(r'(?i)([?&](?:code|access_token|refresh_token|client_secret)=)[^&\s]+'),
]


class CaptureContractError(ValueError):
    pass


class OAuthError(CaptureContractError):
    pass


class MappingError(CaptureContractError):
    pass


class ResumeError(CaptureContractError):
    pass


class ResponseError(CaptureContractError):
    pass


def _utc(value: str) -> datetime:
    text = value[:-1] + "+00:00" if isinstance(value, str) and value.endswith("Z") else value
    try:
        dt = datetime.fromisoformat(text)
    except (TypeError, ValueError) as exc:
        raise CaptureContractError(f"invalid UTC timestamp: {value!r}") from exc
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise CaptureContractError(f"timestamp is not explicit UTC: {value!r}")
    return dt.astimezone(timezone.utc)


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def epoch_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def atomic_write_json(path: Path | str, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(canonical_json_bytes(value))
    os.replace(tmp, path)


def require_read_only_request(proto_name: str) -> str:
    if proto_name in FORBIDDEN_MUTATION_PROTO_REQUESTS or proto_name not in READ_ONLY_PROTO_REQUESTS:
        raise CaptureContractError(f"request not permitted by read-only capture contract: {proto_name}")
    return proto_name


def build_authorization_url(client_id: str, redirect_uri: str, scope: str = READ_ONLY_SCOPE) -> str:
    if scope != READ_ONLY_SCOPE:
        raise OAuthError("only cTrader view-only scope 'accounts' is permitted")
    if not client_id or not redirect_uri:
        raise OAuthError("client_id and redirect_uri are required")
    return AUTH_URL + "?" + urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": READ_ONLY_SCOPE,
        "product": "web",
    })


def is_loopback_redirect(redirect_uri: str) -> bool:
    p = urlparse(redirect_uri)
    return p.scheme == "http" and p.hostname in {"127.0.0.1", "localhost"} and bool(p.port) and bool(p.path)


def parse_oauth_redirect(returned_url: str, expected_redirect_uri: str) -> str:
    actual = urlparse(returned_url)
    expected = urlparse(expected_redirect_uri)
    if (actual.scheme, actual.hostname, actual.port, actual.path) != (
        expected.scheme, expected.hostname, expected.port, expected.path
    ):
        raise OAuthError("OAuth redirect target does not match configured redirect URI")
    q = parse_qs(actual.query, keep_blank_values=True)
    if "error" in q:
        raise OAuthError(f"cTrader authorization returned an error: {q['error'][0]}")
    codes = q.get("code", [])
    if len(codes) != 1 or not codes[0]:
        raise OAuthError("OAuth redirect must contain exactly one non-empty authorization code")
    return codes[0]


def drop_secret_fields(value: Any) -> Any:
    if isinstance(value, Mapping):
        out = {}
        secret_norm = {re.sub(r"[^a-z0-9]", "", k) for k in _SECRET_KEYS}
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized in secret_norm:
                continue
            out[key] = drop_secret_fields(item)
        return out
    if isinstance(value, list):
        return [drop_secret_fields(x) for x in value]
    if isinstance(value, tuple):
        return [drop_secret_fields(x) for x in value]
    return value


def redact_text(text: str) -> str:
    result = str(text)
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub(lambda m: m.group(1) + "=<REDACTED>", result)
    return result


def assert_no_secret_values(payload: bytes | str, secret_values: Iterable[str]) -> None:
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    for secret in secret_values:
        if secret and secret.encode("utf-8") in raw:
            raise CaptureContractError("secret value detected in output payload")


def period_minutes(resolution: str) -> int:
    if resolution not in PERIOD_MINUTES:
        raise CaptureContractError(f"unsupported frozen resolution: {resolution}")
    return PERIOD_MINUTES[resolution]


def historical_windows(start_utc: str, end_utc: str, resolution: str) -> list[tuple[int, int]]:
    start = _utc(start_utc)
    end = _utc(end_utc)
    protected = _utc(PROTECTED_FORWARD_START)
    if end >= protected:
        raise CaptureContractError("DEVELOPMENT request reaches protected-forward boundary")
    if end < start:
        raise CaptureContractError("history interval inverted")
    days = CHUNK_DAYS[resolution]
    out: list[tuple[int, int]] = []
    cursor = start
    while cursor <= end:
        stop = min(end, cursor + timedelta(days=days) - timedelta(milliseconds=1))
        out.append((epoch_ms(cursor), epoch_ms(stop)))
        cursor = stop + timedelta(milliseconds=1)
    return out


def next_pagination_to_ms(trendbars: Sequence[Mapping[str, Any]], current_from_ms: int) -> int | None:
    if not trendbars:
        return None
    stamps = []
    for bar in trendbars:
        value = bar.get("utcTimestampInMinutes", bar.get("utc_timestamp_in_minutes"))
        try:
            stamps.append(int(value) * 60_000)
        except (TypeError, ValueError) as exc:
            raise ResponseError("trendbar missing valid utcTimestampInMinutes") from exc
    next_to = min(stamps) - 1
    return next_to if next_to >= current_from_ms else None


def _bar_field(bar: Mapping[str, Any], camel: str, snake: str | None = None, default: Any = None) -> Any:
    if camel in bar:
        return bar[camel]
    if snake and snake in bar:
        return bar[snake]
    return default


def _format_price(relative: int, digits: int) -> str:
    q = Decimal(1).scaleb(-digits)
    return str((Decimal(relative) / Decimal(100000)).quantize(q))


def normalize_trendbars(
    trendbars: Sequence[Mapping[str, Any]], *, resolution: str, digits: int,
    requested_start_utc: str, requested_end_utc: str,
    protected_start_utc: str = PROTECTED_FORWARD_START,
) -> list[dict[str, str]]:
    start = _utc(requested_start_utc)
    end = _utc(requested_end_utc)
    protected = _utc(protected_start_utc)
    minutes = period_minutes(resolution)
    seen: dict[str, dict[str, str]] = {}
    for bar in trendbars:
        try:
            open_min = int(_bar_field(bar, "utcTimestampInMinutes", "utc_timestamp_in_minutes"))
            low = int(_bar_field(bar, "low", default=None))
            d_open = int(_bar_field(bar, "deltaOpen", "delta_open", 0))
            d_high = int(_bar_field(bar, "deltaHigh", "delta_high", 0))
            d_close = int(_bar_field(bar, "deltaClose", "delta_close", 0))
            volume = int(_bar_field(bar, "volume", default=0))
        except (TypeError, ValueError) as exc:
            raise ResponseError("malformed trendbar numeric field") from exc
        opened = datetime.fromtimestamp(open_min * 60, tz=timezone.utc)
        closed = opened + timedelta(minutes=minutes)
        if opened < start or opened > end:
            continue
        if closed >= protected:
            continue
        row = {
            "time_utc": iso_z(opened),
            "open": _format_price(low + d_open, digits),
            "high": _format_price(low + d_high, digits),
            "low": _format_price(low, digits),
            "close": _format_price(low + d_close, digits),
            "tick_volume": str(volume),
        }
        key = row["time_utc"]
        if key in seen and seen[key] != row:
            raise ResponseError(f"conflicting duplicate trendbar at {key}")
        seen[key] = row
    return [seen[k] for k in sorted(seen)]


def raw_csv_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=RAW_HEADER, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row[k] for k in RAW_HEADER})
    return stream.getvalue().encode("utf-8")


def read_raw_csv(path: Path | str) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def merge_chunk_rows(chunk_paths: Sequence[Path | str]) -> list[dict[str, str]]:
    by_time: dict[str, dict[str, str]] = {}
    for path in chunk_paths:
        for row in read_raw_csv(path):
            if set(RAW_HEADER) - set(row):
                raise ResumeError(f"chunk missing required fields: {path}")
            key = row["time_utc"]
            if key in by_time and by_time[key] != row:
                raise ResumeError(f"conflicting resumed chunk row at {key}")
            by_time[key] = {k: row[k] for k in RAW_HEADER}
    return [by_time[k] for k in sorted(by_time)]


def gap_diagnostics(rows: Sequence[Mapping[str, str]], resolution: str) -> dict[str, Any]:
    minutes = period_minutes(resolution)
    gaps = []
    stamps = [_utc(r["time_utc"]) for r in rows]
    for previous, current in zip(stamps, stamps[1:]):
        delta = int((current - previous).total_seconds() // 60)
        if delta > minutes:
            gaps.append({
                "after_utc": iso_z(previous), "before_utc": iso_z(current),
                "elapsed_minutes": delta,
                "missing_regular_intervals_if_24x7": max(0, delta // minutes - 1),
                "classification": "SOURCE_GAP_REPORTED_NOT_FILLED",
            })
    return {"gap_count": len(gaps), "gaps": gaps}


def _norm_symbol(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(name).upper())


def resolve_symbol_mapping(
    canonical: str, light_symbols: Sequence[Mapping[str, Any]], *, exact_override: str | None = None,
) -> Mapping[str, Any]:
    target = exact_override or canonical
    if exact_override:
        matches = [s for s in light_symbols if str(s.get("symbolName", s.get("symbol_name", ""))) == exact_override]
    else:
        norm = _norm_symbol(target)
        matches = [s for s in light_symbols if _norm_symbol(s.get("symbolName", s.get("symbol_name", ""))) == norm]
    matches = [s for s in matches if bool(s.get("enabled", False))]
    if len(matches) != 1:
        names = sorted(str(s.get("symbolName", s.get("symbol_name", ""))) for s in matches)
        raise MappingError(f"{canonical}: expected one enabled exact mapping, found {len(matches)} {names}")
    return matches[0]


def ensure_full_symbol_enabled(symbol: Mapping[str, Any]) -> None:
    mode = symbol.get("tradingMode", symbol.get("trading_mode"))
    enabled = symbol.get("enabled", True)
    if enabled is False or mode not in (0, "ENABLED", "0", None):
        raise MappingError("full broker symbol is not ENABLED")


def select_live_pepperstone_account(
    accounts: Sequence[Mapping[str, Any]], *, account_override: int | None = None,
) -> Mapping[str, Any]:
    live = []
    for a in accounts:
        aid = int(a.get("ctidTraderAccountId", a.get("ctid_trader_account_id", 0)) or 0)
        title = str(a.get("brokerTitleShort", a.get("broker_title_short", "")))
        if bool(a.get("isLive", a.get("is_live", False))) and "pepperstone" in title.lower():
            if account_override is None or aid == int(account_override):
                live.append(a)
    if len(live) != 1:
        raise MappingError(
            "expected exactly one Pepperstone LIVE account; set ctid_trader_account_id locally when more than one is authorized"
        )
    return live[0]


def account_fingerprint(account_id: int | str) -> str:
    return hashlib.sha256(f"ctrader-account:{int(account_id)}".encode("ascii")).hexdigest()


@dataclass
class RateLimiter:
    min_interval: float = HISTORICAL_MIN_INTERVAL
    clock: Callable[[], float] = time.monotonic
    sleeper: Callable[[float], None] = time.sleep
    _last: float | None = None

    def wait(self) -> float:
        now = self.clock()
        slept = 0.0
        if self._last is not None:
            delay = self.min_interval - (now - self._last)
            if delay > 0:
                self.sleeper(delay)
                slept = delay
                now = self.clock()
        self._last = now
        return slept


def new_resume_state(plan_sha256: str) -> dict[str, Any]:
    return {"schema": "mxm.greenfield.v2.ctrader-capture-resume.v1", "plan_sha256": plan_sha256, "chunks": {}}


def load_resume_state(path: Path | str, plan_sha256: str) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return new_resume_state(plan_sha256)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResumeError("resume state unreadable") from exc
    if state.get("plan_sha256") != plan_sha256 or not isinstance(state.get("chunks"), dict):
        raise ResumeError("resume state plan mismatch or malformed chunks")
    return state


def record_completed_chunk(
    state: dict[str, Any], *, chunk_key: str, path: Path | str, raw_capture_id: str,
    request_from_ms: int, request_to_ms: int, page: int, row_count: int,
) -> None:
    p = Path(path)
    state["chunks"][chunk_key] = {
        "raw_capture_id": raw_capture_id, "path": str(p), "sha256": sha256_file(p),
        "request_from_ms": int(request_from_ms), "request_to_ms": int(request_to_ms),
        "page": int(page), "row_count": int(row_count),
    }


def verified_chunk_path(state: Mapping[str, Any], chunk_key: str) -> Path | None:
    item = state.get("chunks", {}).get(chunk_key)
    if not item:
        return None
    p = Path(item["path"])
    if not p.is_file() or sha256_file(p) != item.get("sha256"):
        return None
    return p


def validate_capture_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    if plan.get("schema") != PLAN_SCHEMA or plan.get("plan_sha256") != EXPECTED_PLAN_SHA:
        raise CaptureContractError("unexpected active materialization plan")
    if plan.get("protected_forward_start") != PROTECTED_FORWARD_START or plan.get("protected_evidence_opened") is not False:
        raise CaptureContractError("protected-forward authority mismatch")
    raws = plan.get("unique_raw_capture_tasks")
    bindings = plan.get("candidate_dataset_bindings")
    if not isinstance(raws, list) or len(raws) != 11:
        raise CaptureContractError("active plan must contain exactly 11 unique raw captures")
    if not isinstance(bindings, list) or len(bindings) != 12:
        raise CaptureContractError("active plan must contain exactly 12 candidate bindings")
    us500 = [b for b in bindings if b.get("canonical_instrument") == "US500"]
    ids = {b.get("candidate_id"): b.get("raw_capture_id") for b in us500}
    sem = {b.get("candidate_id"): b.get("semantic_requirements_sha256") for b in us500}
    if ids.get("V2-C006") != ids.get("V2-C012") or not ids.get("V2-C006"):
        raise CaptureContractError("C006/C012 must share one US500 raw identity")
    if sem.get("V2-C006") == sem.get("V2-C012"):
        raise CaptureContractError("C006/C012 candidate semantic bindings must remain distinct")
    inv = plan.get("state_invariants", {})
    for key in ("result_recorded_count", "v2_attempts_used", "v2_evaluated_identities", "economic_outcomes_opened"):
        if inv.get(key) != 0:
            raise CaptureContractError(f"pre-economic invariant changed: {key}")
    if inv.get("protected_evidence_opened") is not False or inv.get("m6_status") != "PENDING":
        raise CaptureContractError("protected/M6 invariant changed")
    interval = plan.get("raw_capture_defaults", {}).get("interval", {})
    if interval.get("classification") != "DEVELOPMENT_ONLY" or _utc(interval.get("end_utc")) >= _utc(PROTECTED_FORWARD_START):
        raise CaptureContractError("raw capture interval is not frozen DEVELOPMENT")
    return {"unique_raw_capture_count": 11, "candidate_binding_count": 12, "shared_us500_raw_capture_id": ids["V2-C006"]}


def deterministic_zip(source_dir: Path | str, zip_path: Path | str) -> str:
    source = Path(source_dir)
    zip_path = Path(zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in source.rglob("*") if p.is_file() and p.resolve() != zip_path.resolve())
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in files:
            rel = p.relative_to(source).as_posix()
            info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, p.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return sha256_file(zip_path)


def write_bundle_checksums(bundle_dir: Path | str) -> dict[str, str]:
    root = Path(bundle_dir)
    checksums: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name not in {"CHECKSUMS.sha256"} and p.suffix.lower() != ".zip":
            checksums[p.relative_to(root).as_posix()] = sha256_file(p)
    lines = "".join(f"{digest}  {name}\n" for name, digest in sorted(checksums.items()))
    (root / "CHECKSUMS.sha256").write_text(lines, encoding="utf-8", newline="\n")
    return checksums


def scan_bundle_for_secrets(bundle_dir: Path | str, secret_values: Iterable[str] = ()) -> None:
    root = Path(bundle_dir)
    forbidden_key_re = re.compile(
        r'(?i)"(?:client_secret|clientSecret|access_token|accessToken|refresh_token|refreshToken|authorization_code|password)"\s*:'
    )
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() == ".zip":
            continue
        raw = p.read_bytes()
        assert_no_secret_values(raw, secret_values)
        text = raw.decode("utf-8", errors="ignore")
        if forbidden_key_re.search(text):
            raise CaptureContractError(f"secret-bearing field name detected in bundle: {p.name}")
