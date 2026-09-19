"""Frozen pre-outcome transaction-local Discovery cost application for Tier-1.

This module does not calibrate costs from candidate signals or outcomes.  It selects the
already-computed generic quote-evidence row at an exact transaction timestamp and applies:

    full causal spread + absolute midpoint displacement to first bilateral quote refresh

The refresh is diagnostic uncertainty evidence only; it is not asserted to be a historical fill.
Missing/unsupported rows fail closed as COST_UNRESOLVED.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import csv
import hashlib
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

US500_GENERIC_EVIDENCE_SHA256 = "601eedcb147021fff54f4d3bd2a43d831c455a821ddafa01a0036afe5c5485d6"
NAS100_C012_SUPPORT_SHA256 = "dd4f6be917773fc580d4725d7c30ef4aabd5ec4ce19a30fdced8c5a85f4bd999"

C006_STRESS_DIAGNOSTIC = {
    "entry_points": Decimal("11.1"),
    "exit_points": Decimal("2.2"),
    "round_trip_points": Decimal("13.3"),
}
C012_STRESS_DIAGNOSTIC = {
    "transaction_points": Decimal("95.3"),
    "nominal_round_trip_points": Decimal("190.6"),
}
C012_KNOWN_UNSUPPORTED_BOUNDARIES_MS = frozenset({
    1735675200000,  # 2024-12-31 15:00 ET
    1767211200000,  # 2025-12-31 15:00 ET
})


class CostEvidenceUnavailable(ValueError):
    """Required transaction-local evidence is absent or not applicable."""


class CostEvidenceIntegrityError(ValueError):
    """Evidence bytes or same-row arithmetic violate the frozen contract."""


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(path: Path | str, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise CostEvidenceIntegrityError(
            f"{Path(path)} sha256 mismatch: expected {expected}, got {actual}"
        )


def _decimal(value: Any, *, field: str) -> Decimal:
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise CostEvidenceIntegrityError(f"invalid decimal {field}: {value!r}") from exc
    if not d.is_finite():
        raise CostEvidenceIntegrityError(f"non-finite decimal {field}")
    return d


def _optional_decimal(value: Any, *, field: str) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    return _decimal(value, field=field)


def _boundary_ms(value: Any) -> int:
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            raise ValueError("transaction timestamp must be timezone-aware")
        return int(dt.astimezone(timezone.utc).timestamp() * 1000)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return int(value)
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError("transaction timestamp must be timezone-aware")
    return int(dt.astimezone(timezone.utc).timestamp() * 1000)


@dataclass(frozen=True)
class TransactionCostEvidence:
    instrument: str
    session_date: str
    boundary_timestamp_ms: int
    causal_bid: Decimal | None
    causal_ask: Decimal | None
    causal_spread_points: Decimal | None
    refresh_timestamp_ms: int | None
    refresh_bid: Decimal | None
    refresh_ask: Decimal | None
    absolute_mid_displacement_points: Decimal | None
    transaction_cost_proxy_points: Decimal | None
    availability_state: str

    @property
    def supported(self) -> bool:
        return self.availability_state == "VALID_GENERIC_COST_SUPPORT"

    def require_supported(self) -> "TransactionCostEvidence":
        if not self.supported or self.transaction_cost_proxy_points is None:
            raise CostEvidenceUnavailable(
                f"{self.instrument} {self.boundary_timestamp_ms}: "
                f"{self.availability_state}"
            )
        return self


class TransactionLocalCostIndex:
    """Exact-boundary lookup over signal-blind precomputed generic evidence."""

    def __init__(self, instrument: str, rows: Sequence[TransactionCostEvidence]):
        self.instrument = instrument
        by_boundary: dict[int, TransactionCostEvidence] = {}
        for row in rows:
            if row.instrument != instrument:
                raise CostEvidenceIntegrityError("instrument mismatch in cost evidence")
            if row.boundary_timestamp_ms in by_boundary:
                raise CostEvidenceIntegrityError(
                    f"duplicate {instrument} boundary {row.boundary_timestamp_ms}"
                )
            by_boundary[row.boundary_timestamp_ms] = row
        self._rows = by_boundary

    def evidence_for(self, transaction_timestamp: Any) -> TransactionCostEvidence:
        boundary = _boundary_ms(transaction_timestamp)
        row = self._rows.get(boundary)
        if row is None:
            raise CostEvidenceUnavailable(
                f"{self.instrument} {boundary}: OUTSIDE_CALIBRATED_GENERIC_DOMAIN"
            )
        return row.require_supported()

    def cost_points(self, transaction_timestamp: Any, *, direction: str | None = None) -> Decimal:
        # Direction is accepted only to make explicit that it cannot improve/reduce the adverse cost.
        _ = direction
        return self.evidence_for(transaction_timestamp).transaction_cost_proxy_points  # type: ignore[return-value]

    def has_boundary(self, transaction_timestamp: Any) -> bool:
        return _boundary_ms(transaction_timestamp) in self._rows

    def __len__(self) -> int:
        return len(self._rows)


def _same_row_cost(
    *,
    causal_bid: Decimal,
    causal_ask: Decimal,
    recorded_spread: Decimal,
    refresh_bid: Decimal,
    refresh_ask: Decimal,
    recorded_abs_displacement: Decimal | None = None,
) -> tuple[Decimal, Decimal]:
    if causal_ask < causal_bid:
        raise CostEvidenceIntegrityError("negative causal spread")
    spread = causal_ask - causal_bid
    if spread != recorded_spread:
        raise CostEvidenceIntegrityError(
            f"causal spread mismatch: row={recorded_spread} recomputed={spread}"
        )
    causal_mid = (causal_bid + causal_ask) / Decimal("2")
    refresh_mid = (refresh_bid + refresh_ask) / Decimal("2")
    displacement = abs(refresh_mid - causal_mid)
    if recorded_abs_displacement is not None and displacement != recorded_abs_displacement:
        raise CostEvidenceIntegrityError(
            "same-row midpoint displacement mismatch: "
            f"row={recorded_abs_displacement} recomputed={displacement}"
        )
    return displacement, spread + displacement


def from_original_boundary_rows(
    instrument: str,
    rows: Iterable[Mapping[str, Any]],
) -> TransactionLocalCostIndex:
    parsed: list[TransactionCostEvidence] = []
    for row in rows:
        boundary = int(row["boundary_timestamp_ms"])
        causal_available = row.get("causal_state_availability") == "CAUSAL_TWO_SIDED_AVAILABLE"
        refresh_available = (
            row.get("both_sides_refreshed_classification") == "QUOTE_REFRESH_DIAGNOSTIC_ONLY"
            and str(row.get("both_sides_refreshed_bid", "")).strip() != ""
            and str(row.get("both_sides_refreshed_ask", "")).strip() != ""
            and str(row.get("both_sides_refreshed_state_timestamp_ms", "")).strip() != ""
        )
        if not causal_available or not refresh_available:
            state = (
                "MISSING_CAUSAL_TWO_SIDED_STATE"
                if not causal_available
                else "MISSING_POST_BOUNDARY_BILATERAL_REFRESH"
            )
            parsed.append(TransactionCostEvidence(
                instrument=instrument,
                session_date=str(row.get("session_date", "")),
                boundary_timestamp_ms=boundary,
                causal_bid=_optional_decimal(row.get("causal_bid"), field="causal_bid"),
                causal_ask=_optional_decimal(row.get("causal_ask"), field="causal_ask"),
                causal_spread_points=_optional_decimal(row.get("causal_spread"), field="causal_spread"),
                refresh_timestamp_ms=None,
                refresh_bid=None,
                refresh_ask=None,
                absolute_mid_displacement_points=None,
                transaction_cost_proxy_points=None,
                availability_state=state,
            ))
            continue

        bid = _decimal(row["causal_bid"], field="causal_bid")
        ask = _decimal(row["causal_ask"], field="causal_ask")
        spread = _decimal(row["causal_spread"], field="causal_spread")
        refresh_bid = _decimal(row["both_sides_refreshed_bid"], field="refresh_bid")
        refresh_ask = _decimal(row["both_sides_refreshed_ask"], field="refresh_ask")
        displacement, cost = _same_row_cost(
            causal_bid=bid,
            causal_ask=ask,
            recorded_spread=spread,
            refresh_bid=refresh_bid,
            refresh_ask=refresh_ask,
        )
        parsed.append(TransactionCostEvidence(
            instrument=instrument,
            session_date=str(row["session_date"]),
            boundary_timestamp_ms=boundary,
            causal_bid=bid,
            causal_ask=ask,
            causal_spread_points=spread,
            refresh_timestamp_ms=int(row["both_sides_refreshed_state_timestamp_ms"]),
            refresh_bid=refresh_bid,
            refresh_ask=refresh_ask,
            absolute_mid_displacement_points=displacement,
            transaction_cost_proxy_points=cost,
            availability_state="VALID_GENERIC_COST_SUPPORT",
        ))
    return TransactionLocalCostIndex(instrument, parsed)


def from_c012_support_rows(
    rows: Iterable[Mapping[str, Any]],
) -> TransactionLocalCostIndex:
    parsed: list[TransactionCostEvidence] = []
    for row in rows:
        boundary = int(row["boundary_timestamp_ms"])
        source_state = str(row.get("state", "")).strip()
        if source_state != "VALID_GENERIC_COST_SUPPORT":
            parsed.append(TransactionCostEvidence(
                instrument="NAS100",
                session_date=str(row.get("session_date", "")),
                boundary_timestamp_ms=boundary,
                causal_bid=_optional_decimal(row.get("causal_bid"), field="causal_bid"),
                causal_ask=_optional_decimal(row.get("causal_ask"), field="causal_ask"),
                causal_spread_points=_optional_decimal(row.get("causal_spread"), field="causal_spread"),
                refresh_timestamp_ms=None,
                refresh_bid=None,
                refresh_ask=None,
                absolute_mid_displacement_points=None,
                transaction_cost_proxy_points=None,
                availability_state=source_state or "UNSUPPORTED_GENERIC_COST_ROW",
            ))
            continue

        bid = _decimal(row["causal_bid"], field="causal_bid")
        ask = _decimal(row["causal_ask"], field="causal_ask")
        spread = _decimal(row["causal_spread"], field="causal_spread")
        refresh_bid = _decimal(row["refresh_bid"], field="refresh_bid")
        refresh_ask = _decimal(row["refresh_ask"], field="refresh_ask")
        recorded_disp = _decimal(
            row["absolute_mid_displacement_points"],
            field="absolute_mid_displacement_points",
        )
        displacement, cost = _same_row_cost(
            causal_bid=bid,
            causal_ask=ask,
            recorded_spread=spread,
            refresh_bid=refresh_bid,
            refresh_ask=refresh_ask,
            recorded_abs_displacement=recorded_disp,
        )
        parsed.append(TransactionCostEvidence(
            instrument="NAS100",
            session_date=str(row["session_date"]),
            boundary_timestamp_ms=boundary,
            causal_bid=bid,
            causal_ask=ask,
            causal_spread_points=spread,
            refresh_timestamp_ms=int(row["refresh_timestamp_ms"]),
            refresh_bid=refresh_bid,
            refresh_ask=refresh_ask,
            absolute_mid_displacement_points=displacement,
            transaction_cost_proxy_points=cost,
            availability_state="VALID_GENERIC_COST_SUPPORT",
        ))
    return TransactionLocalCostIndex("NAS100", parsed)


def load_us500_transaction_local_index(path: Path | str) -> TransactionLocalCostIndex:
    verify_sha256(path, US500_GENERIC_EVIDENCE_SHA256)
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        return from_original_boundary_rows("US500", csv.DictReader(f))


def load_c012_transaction_local_index(path: Path | str) -> TransactionLocalCostIndex:
    verify_sha256(path, NAS100_C012_SUPPORT_SHA256)
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        return from_c012_support_rows(csv.DictReader(f))
