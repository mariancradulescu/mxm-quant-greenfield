"""Local-only Pepperstone LIVE canonical-to-broker symbol mapping state.

This module never uses strategy/economic information. Mappings are user-local structural
identity decisions and are not part of the transferable research bundle.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from .ctrader_capture import (
    SYMBOL_MAPPING_SOURCE_ENVIRONMENT,
    atomic_write_json,
)
from .pydroid_oauth import PRIVATE_ROOT

SYMBOL_MAPPING_PATH = PRIVATE_ROOT / "symbol_mappings.json"
SCHEMA = "mxm.greenfield.v2.local-live-symbol-mappings.v1"


def _load_json(path: Path):
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def load_symbol_overrides() -> dict[str, dict[str, Any]]:
    state = _load_json(SYMBOL_MAPPING_PATH)
    if not isinstance(state, dict):
        return {}
    if state.get("schema") != SCHEMA:
        return {}
    if state.get("source_environment") != SYMBOL_MAPPING_SOURCE_ENVIRONMENT:
        return {}
    mappings = state.get("mappings")
    if not isinstance(mappings, dict):
        return {}
    out = {}
    for canonical, item in mappings.items():
        if not isinstance(item, dict):
            continue
        try:
            sid = int(item.get("symbol_id"))
        except (TypeError, ValueError):
            continue
        name = str(item.get("broker_symbol") or "")
        if sid <= 0 or not name:
            continue
        out[str(canonical)] = {
            "symbol_id": sid,
            "broker_symbol": name,
            "source_environment": SYMBOL_MAPPING_SOURCE_ENVIRONMENT,
            "account_fingerprint_sha256": item.get("account_fingerprint_sha256"),
        }
    return out


def _write_mappings(mappings: Mapping[str, Any]) -> None:
    SYMBOL_MAPPING_PATH.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(SYMBOL_MAPPING_PATH, {
        "schema": SCHEMA,
        "source_environment": SYMBOL_MAPPING_SOURCE_ENVIRONMENT,
        "transferable": False,
        "mappings": dict(sorted(mappings.items())),
    })
    try:
        os.chmod(SYMBOL_MAPPING_PATH.parent, 0o700)
        os.chmod(SYMBOL_MAPPING_PATH, 0o600)
    except OSError:
        pass


def save_symbol_override(canonical: str, mapping: Mapping[str, Any]) -> None:
    current = load_symbol_overrides()
    current[str(canonical)] = {
        "symbol_id": int(mapping["symbol_id"]),
        "broker_symbol": str(mapping["broker_symbol"]),
        "source_environment": SYMBOL_MAPPING_SOURCE_ENVIRONMENT,
        "account_fingerprint_sha256": mapping.get("account_fingerprint_sha256"),
    }
    _write_mappings(current)


def clear_symbol_override(canonical: str) -> None:
    current = load_symbol_overrides()
    if str(canonical) not in current:
        return
    current.pop(str(canonical), None)
    _write_mappings(current)


def choose_symbol_locally(canonical: str, discovery: Mapping[str, Any]):
    candidates = (
        discovery.get("credible_candidates")
        or discovery.get("related_candidates")
        or []
    )
    print("")
    print(f"Canonical instrument: {canonical}")
    print("Possible ENABLED Pepperstone LIVE symbols:")
    if candidates:
        for index, row in enumerate(candidates, 1):
            print(
                f"{index}. {row['symbol_name']} — "
                f"{row.get('description') or '-'} — symbolId {row['symbol_id']} "
                f"— enabled={row['enabled']}"
            )
    else:
        print("(no structurally related enabled LIVE candidates)")
    print("0. BLOCK / none of these")

    while True:
        try:
            raw = input("Select broker symbol: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("")
            return None
        if raw == "0":
            return None
        try:
            index = int(raw)
        except ValueError:
            print("Enter one of the displayed numbers.")
            continue
        if 1 <= index <= len(candidates):
            return int(candidates[index - 1]["symbol_id"])
        print("Enter one of the displayed numbers.")
