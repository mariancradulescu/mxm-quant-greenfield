"""Deterministic broker-native structural frontier selection with no fixed panel size."""
from __future__ import annotations
import csv, hashlib, json, math
from pathlib import Path
from typing import Iterable, Mapping, Any

VERSION="MXM_BROKER_NATIVE_INFORMATION_FRONTIER_V1"
EXPECTED_MAP_SHA256="c2b16c3fc0419ec335ebbd67e0af09043e60a476516db01c55550d661b5f4130"
SIGNATURE_AXES=("asset_class","product_type","coverage_bucket","session_regions","weekend_capable")

def _sha(path: str|Path) -> str:
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def _bool(value: Any) -> bool:
    if isinstance(value,bool): return value
    return str(value).strip().lower() in {"1","true","yes"}

def _float(value: Any, default: float=0.0) -> float:
    try:
        x=float(value)
        return x if math.isfinite(x) else default
    except (TypeError,ValueError):
        return default

def _int(value: Any, default: int=0) -> int:
    try: return int(value)
    except (TypeError,ValueError): return default

def authority_exclusions(scope_audit: Mapping[str,Any],
                         structural_report: Mapping[str,Any],
                         outer_result: Mapping[str,Any]) -> set[str]:
    out=set()
    for item in scope_audit.get("identity_matrix") or []:
        for symbol in item.get("exact_universe") or []:
            out.add(str(symbol))
    out.update(str(x) for x in (structural_report.get("per_symbol") or {}).keys())
    out.update(str(x) for x in (outer_result.get("fixed_symbols") or []))
    return out

def load_map(path: str|Path) -> list[dict[str,Any]]:
    path=Path(path)
    if _sha(path)!=EXPECTED_MAP_SHA256:
        raise ValueError("broker-native structural map SHA256 mismatch")
    with path.open("r",encoding="utf-8",newline="") as f:
        return list(csv.DictReader(f))

def _signature(row: Mapping[str,Any]) -> tuple:
    return tuple(_bool(row[k]) if k=="weekend_capable" else str(row.get(k,"")) for k in SIGNATURE_AXES)

def _eligible(row: Mapping[str,Any], excluded: set[str]) -> bool:
    return (
        str(row.get("broker_symbol","")) not in excluded
        and str(row.get("directional_summary",""))=="BOTH_FEASIBLE"
        and _bool(row.get("shortability"))
        and str(row.get("asset_class","")).upper()!="TEST"
    )

def _order(row: Mapping[str,Any]) -> tuple:
    existing=1 if str(row.get("data_acquisition_burden",""))=="LOW_EXISTING_DEVELOPMENT_COMPONENT" else 0
    return (
        -_float(row.get("surface_minutes_per_margin_eur")),
        -existing,
        _float(row.get("min_feasible_margin_eur"),float("inf")),
        _int(row.get("symbol_id"),2**63-1),
        str(row.get("broker_symbol","")),
    )

def select_frontier(rows: Iterable[Mapping[str,Any]], excluded_symbols: Iterable[str]) -> list[dict[str,Any]]:
    excluded={str(x) for x in excluded_symbols}
    groups: dict[tuple,list[Mapping[str,Any]]]={}
    for row in rows:
        if _eligible(row,excluded):
            groups.setdefault(_signature(row),[]).append(row)
    selected=[]
    for signature in sorted(groups,key=lambda s:tuple(str(x) for x in s)):
        row=min(groups[signature],key=_order)
        selected.append({
            "symbol_id":_int(row.get("symbol_id")),
            "broker_symbol":str(row.get("broker_symbol")),
            "asset_class":str(row.get("asset_class")),
            "product_type":str(row.get("product_type")),
            "coverage_bucket":str(row.get("coverage_bucket")),
            "session_regions":str(row.get("session_regions")),
            "weekend_capable":_bool(row.get("weekend_capable")),
            "shortability":_bool(row.get("shortability")),
            "min_feasible_margin_eur":_float(row.get("min_feasible_margin_eur")),
            "min_feasible_margin_pct_eur200":_float(row.get("min_feasible_margin_pct_eur200")),
            "schedule_minutes_per_week":_float(row.get("schedule_minutes_per_week")),
            "surface_minutes_per_margin_eur":_float(row.get("surface_minutes_per_margin_eur")),
            "existing_development_resolutions":(
                None if not str(row.get("existing_development_resolutions","")).strip()
                else str(row.get("existing_development_resolutions"))
            ),
            "data_acquisition_burden":str(row.get("data_acquisition_burden")),
            "execution_cost_resolvability":str(row.get("execution_cost_resolvability")),
        })
    if len({_signature(x) for x in selected})!=len(selected):
        raise AssertionError("structural signature duplication")
    if any(x["broker_symbol"] in excluded for x in selected):
        raise AssertionError("excluded symbol selected")
    return selected

def build_from_authorities(map_path: str|Path, scope_audit_path: str|Path,
                           structural_report_path: str|Path, outer_result_path: str|Path) -> list[dict[str,Any]]:
    load=lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
    excluded=authority_exclusions(load(scope_audit_path),load(structural_report_path),load(outer_result_path))
    return select_frontier(load_map(map_path),excluded)
