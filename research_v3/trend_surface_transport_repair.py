"""Read-only recovery diagnostic for the persisted Epoch38 TREND surface transport.

This module never reruns the market-data scan. It only inspects the bytes already
persisted in Git and attempts bounded recovery of the XZ container. Recovered
content is authoritative only if its decoded SHA256 exactly matches the frozen
manifest hash and the full 560-cell geometry validates.
"""
from __future__ import annotations

import base64
import hashlib
import json
import lzma
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

TRANSPORT_REF = "research_v3/runtime_v2_inputs/EPOCH38_TREND_MOMENTUM_COARSE_PARAMETER_REGION_COMPACT_XZ_BASE64_V1.txt"
MANIFEST_REF = "evidence/EPOCH38_TREND_MOMENTUM_COARSE_PARAMETER_REGION_SURFACE_MANIFEST_V1.json"
EXPECTED_DECODED_SHA256 = "af2bd7e67632448676cfabe42a87a5f3ee2d26867a191fab1eb9aed6329839b6"
EXPECTED_ROWS = 560
EXPECTED_SYMBOLS = ["JPYX", "ZARJPY", "USDCLP", "USDBRL", "USDCZK", "TRUMPUSD", "XPDUSD"]
EXPECTED_LOOKBACKS = [12, 24, 48, 96, 192]
EXPECTED_THRESHOLDS = [0.5, 1.0, 1.5, 2.0]
EXPECTED_HOLDS = ["15m", "1h", "4h", "1d"]
XZ_MAGIC = bytes.fromhex("fd377a585a00")


class TrendSurfaceRecoveryError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _try_xz_salvage(compressed: bytes) -> tuple[bytes | None, dict[str, Any]]:
    """Try standard lib first, then xz --ignore-check without accepting partial data."""
    try:
        return lzma.decompress(compressed, format=lzma.FORMAT_XZ), {
            "method": "PYTHON_LZMA",
            "returncode": 0,
            "stderr": "",
        }
    except lzma.LZMAError as exc:
        standard_error = str(exc)

    with tempfile.NamedTemporaryFile(suffix=".xz") as fh:
        fh.write(compressed)
        fh.flush()
        proc = subprocess.run(
            ["xz", "--decompress", "--stdout", "--ignore-check", fh.name],
            text=False,
            capture_output=True,
            check=False,
        )
    detail = {
        "method": "XZ_IGNORE_CHECK",
        "returncode": proc.returncode,
        "stderr": proc.stderr.decode("utf-8", errors="replace")[-2000:],
        "python_lzma_error": standard_error,
        "stdout_bytes": len(proc.stdout),
    }
    # xz may emit partial output on a corrupt stream. Exact frozen decoded hash is
    # the only authority that can make those bytes usable.
    return (proc.stdout if proc.stdout else None), detail


def _extract_rows_and_columns(decoded: Any, manifest: dict[str, Any]) -> tuple[list[Any], list[str]]:
    expected_columns = list((manifest.get("surface") or {}).get("columns") or [])
    if isinstance(decoded, dict):
        columns = list(decoded.get("columns") or expected_columns)
        for key in ("rows", "surface", "data", "cells"):
            value = decoded.get(key)
            if isinstance(value, list):
                return value, columns
    if isinstance(decoded, list):
        return decoded, expected_columns
    raise TrendSurfaceRecoveryError("decoded compact JSON has no recognized row list")


def _row_dict(row: Any, columns: list[str]) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    if isinstance(row, list) and len(row) == len(columns):
        return dict(zip(columns, row))
    raise TrendSurfaceRecoveryError("row cannot be interpreted against manifest columns")


def validate_geometry(decoded_bytes: bytes, manifest: dict[str, Any]) -> dict[str, Any]:
    if sha256_bytes(decoded_bytes) != EXPECTED_DECODED_SHA256:
        raise TrendSurfaceRecoveryError("decoded bytes do not match frozen compact JSON SHA256")
    decoded = json.loads(decoded_bytes.decode("utf-8"))
    rows, columns = _extract_rows_and_columns(decoded, manifest)
    if len(rows) != EXPECTED_ROWS:
        raise TrendSurfaceRecoveryError(f"row count mismatch: {len(rows)} != {EXPECTED_ROWS}")

    normalized = [_row_dict(row, columns) for row in rows]
    by_symbol = Counter(str(row.get("symbol")) for row in normalized)
    if set(by_symbol) != set(EXPECTED_SYMBOLS):
        raise TrendSurfaceRecoveryError(f"symbol set mismatch: {sorted(by_symbol)}")
    if any(by_symbol[s] != 80 for s in EXPECTED_SYMBOLS):
        raise TrendSurfaceRecoveryError(f"per-symbol cell counts mismatch: {dict(by_symbol)}")

    coords = defaultdict(set)
    for row in normalized:
        symbol = str(row["symbol"])
        lb = int(row["lookback"])
        th = float(row["momentum_threshold_zscore"])
        hold = str(row["hold_horizon"])
        coords[symbol].add((lb, th, hold))
    expected_coords = {
        (lb, th, hold)
        for lb in EXPECTED_LOOKBACKS
        for th in EXPECTED_THRESHOLDS
        for hold in EXPECTED_HOLDS
    }
    for symbol in EXPECTED_SYMBOLS:
        if coords[symbol] != expected_coords:
            raise TrendSurfaceRecoveryError(f"exact frozen coordinate grid mismatch for {symbol}")

    support_by_cell: dict[tuple[int, float, str], list[tuple[str, str]]] = defaultdict(list)
    for row in normalized:
        if row.get("local_support") is True:
            key = (int(row["lookback"]), float(row["momentum_threshold_zscore"]), str(row["hold_horizon"]))
            support_by_cell[key].append((str(row["symbol"]), str(row["asset_class"])))
    cross_supported = []
    for key, supported in sorted(support_by_cell.items()):
        if len(supported) >= 4 and len({asset for _, asset in supported}) >= 2:
            cross_supported.append({
                "coordinate": key,
                "supported_symbols": sorted(symbol for symbol, _ in supported),
                "supported_asset_classes": sorted({asset for _, asset in supported}),
            })

    return {
        "rows": len(normalized),
        "symbols": sorted(by_symbol),
        "cells_per_symbol": dict(sorted(by_symbol.items())),
        "exact_frozen_grid": True,
        "cross_symbol_supported_cell_count": len(cross_supported),
        "cross_symbol_supported_cells": cross_supported,
    }


def diagnose(root_value: str | Path = ".") -> dict[str, Any]:
    root = Path(root_value).resolve()
    transport_path = root / TRANSPORT_REF
    manifest_path = root / MANIFEST_REF
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    encoded = transport_path.read_bytes()
    compact = b"".join(encoded.split())
    observed_transport_sha = sha256_bytes(encoded)
    invalid_base64 = [
        {"offset": i, "byte": int(value)}
        for i, value in enumerate(compact)
        if not (
            65 <= value <= 90 or 97 <= value <= 122 or 48 <= value <= 57
            or value in (43, 47, 61)
        )
    ]
    strict_base64_error = None
    try:
        compressed = base64.b64decode(compact, validate=True)
        base64_method = "STRICT"
    except Exception as exc:
        strict_base64_error = str(exc)
        # Transport-only recovery: Python's non-validating decoder discards bytes
        # outside the Base64 alphabet. These decoded bytes still have zero authority
        # unless the frozen decoded JSON SHA256 later matches exactly.
        try:
            compressed = base64.b64decode(compact, validate=False)
            base64_method = "IGNORE_NON_ALPHABET_BYTES"
        except Exception as fallback_exc:
            return {
                "schema": "mxm.greenfield.trend-surface-transport-recovery-diagnostic.v1",
                "status": "UNRECOVERABLE_INVALID_BASE64",
                "transport_ref": TRANSPORT_REF,
                "observed_transport_sha256": observed_transport_sha,
                "strict_base64_error": strict_base64_error,
                "fallback_error": str(fallback_exc),
                "invalid_base64_bytes": invalid_base64[:64],
                "invalid_base64_byte_count": len(invalid_base64),
                "research_rerun_performed": False,
            }

    if not compressed.startswith(XZ_MAGIC):
        return {
            "schema": "mxm.greenfield.trend-surface-transport-recovery-diagnostic.v1",
            "status": "UNRECOVERABLE_XZ_MAGIC_MISMATCH",
            "transport_ref": TRANSPORT_REF,
            "observed_transport_sha256": observed_transport_sha,
            "compressed_bytes": len(compressed),
            "research_rerun_performed": False,
        }

    decoded, salvage = _try_xz_salvage(compressed)
    decoded_sha = sha256_bytes(decoded) if decoded is not None else None
    if decoded is None or decoded_sha != EXPECTED_DECODED_SHA256:
        return {
            "schema": "mxm.greenfield.trend-surface-transport-recovery-diagnostic.v1",
            "status": "UNRECOVERABLE_FROM_PERSISTED_TRANSPORT",
            "transport_ref": TRANSPORT_REF,
            "manifest_transport_sha256": (manifest.get("surface") or {}).get("transport_sha256"),
            "observed_transport_sha256": observed_transport_sha,
            "compressed_bytes": len(compressed),
            "base64_method": base64_method,
            "strict_base64_error": strict_base64_error,
            "invalid_base64_bytes": invalid_base64[:64],
            "invalid_base64_byte_count": len(invalid_base64),
            "decoded_bytes": len(decoded or b""),
            "expected_decoded_sha256": EXPECTED_DECODED_SHA256,
            "observed_decoded_sha256": decoded_sha,
            "salvage": salvage,
            "research_rerun_performed": False,
        }

    try:
        geometry = validate_geometry(decoded, manifest)
    except Exception as exc:
        return {
            "schema": "mxm.greenfield.trend-surface-transport-recovery-diagnostic.v1",
            "status": "DECODED_HASH_MATCH_BUT_GEOMETRY_INVALID",
            "transport_ref": TRANSPORT_REF,
            "expected_decoded_sha256": EXPECTED_DECODED_SHA256,
            "observed_decoded_sha256": decoded_sha,
            "salvage": salvage,
            "error": str(exc),
            "research_rerun_performed": False,
        }

    repaired_compressed = lzma.compress(decoded, format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64, preset=6)
    repaired_encoded = base64.b64encode(repaired_compressed)
    return {
        "schema": "mxm.greenfield.trend-surface-transport-recovery-diagnostic.v1",
        "status": "RECOVERABLE_EXACT_DECODED_BYTES",
        "transport_ref": TRANSPORT_REF,
        "manifest_transport_sha256": (manifest.get("surface") or {}).get("transport_sha256"),
        "observed_transport_sha256": observed_transport_sha,
        "base64_method": base64_method,
        "strict_base64_error": strict_base64_error,
        "invalid_base64_bytes": invalid_base64[:64],
        "invalid_base64_byte_count": len(invalid_base64),
        "expected_decoded_sha256": EXPECTED_DECODED_SHA256,
        "observed_decoded_sha256": decoded_sha,
        "salvage": salvage,
        "geometry": geometry,
        "repaired_transport_sha256": sha256_bytes(repaired_encoded),
        "repaired_transport_base64": repaired_encoded.decode("ascii"),
        "research_rerun_performed": False,
    }


def main() -> int:
    report = diagnose()
    # Never print the potentially large recovered payload in CI logs.
    printable = dict(report)
    printable.pop("repaired_transport_base64", None)
    print(json.dumps(printable, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
