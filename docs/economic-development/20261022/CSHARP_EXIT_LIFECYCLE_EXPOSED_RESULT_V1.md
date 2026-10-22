# MXM — C# full-position lifecycle: economic exposure, no scientific promotion

**Date:** 2026-10-22. **Lane:** engineering DEVELOPMENT sensitivity on previously exposed original Pepperstone BID/ASK, not an independent economic trial, backtest certification or actual trade.

## Source and revision
- Repository: mariancradulescu/mxm-quant-greenfield, protected execution branch `mxm-remediation-p0-p4-20261015-v1`.
- PR #116 merged at `dd56f8fb96a370e38053e2586a1512d8bd75d28e`: add three optional exit policies and share core C# decisions between cTrader adapter and simulator. Original default `ReverseOnly` preserved; DEMO-only guard preserved; all three required CI passed.
- Protected authentic run `39776838582` **SUCCESS**, source `dd56f8fb96a370e38053e2586a1512d8bd75d28e`.
- PR #117 merged at `f4dbf23b3dfed9f5adbd4d435ca69946168658f5`: prevent false neutral exit during six-bar cold-start or missing-bar reset, with native guarded CI. Identical preregistered 216-model study rerun machine-side **SUCCESS** at `39777231786`. After correction M5 BASE results below were unchanged.
- Original immutable native Pepperstone quote source `39660692230`, 14,003 BID plus 14,209 ASK events = 28,212. No new broker request or order. Identical ciphertext custody path preserved.
- Fixed preregistration: `research_core_v4/native_tick_replay_v1/csharp/EXIT_LIFECYCLE_FINITE_DEVELOPMENT_V1.json`. One study with 216 mutually dependent model leaves, not 216 independent strategies or confirmations.
- Original corrected encrypted full-result GitHub Actions artifact `12424029423`, path member `exposed-exit-lifecycle.mxmenc`, 5,081 ciphertext bytes, SHA256 `c4419724f29b1520c6ab34c7dc0ec69badfbf7245f0fdfb6f489a8b7697056f0`. Public bounded `receipt.json` original SHA256 `12849a1b4a061eb1a66d4fe5181b7ed0de075442a66bd0d42e537f8049f7fe61`. These artifacts have 30-day Actions retention; permanent Git repository preserves this scientific result and its provenance, not the original complete encrypted model ledger.

## Exit policy contrast on authentic Pepperstone quotes

Single simulated EUR200 account per model, same previously-exposed 4-hour quote source, all numbers in EUR, one family/timeframe at a time; **NOT** an EUR200 multi-symbol portfolio. Compare M5 only, assumed BASE friction / margin and hypothetical 80% free-margin admission, stop modeled at 12 pips. Margin, fees, slippage, historical EURUSD FX and actual execution are NOT broker certified.

| Causal entry family | Reverse-only exits | Neutral-flat exits | 12-bar horizon exits | Modeled entries (reverse/neutral/horizon) |
|---|---:|---:|---:|---:|
| Adaptive | -2.618182 | -5.390909 | -2.536364 | 7 / 10 / 7 |
| TrendOnly | +1.672727 | +1.163636 | -0.336364 | 2 / 3 / 4 |
| RangeFade | -4.181818 | -5.100000 | -3.490909 | 4 / 6 / 4 |
| Breakout | +1.581818 | -3.881818 | -0.381818 | 2 / 9 / 4 |

The sensitivity makes the full trade lifecycle materially consequential: neutral exit increases churn, worsening PnL across these four families and this exact scenario. A 12-bar exit slightly lessens losses for Adaptive/RangeFade, but can destroy limited gains from TrendOnly/Breakout. No strategy is selected: the mild positive reversals contain just 2 modeled entries on only four hours of quotes.

## Interpretative restrictions
- The baseline stops and 40% / 80% margin settings are engineering scenarios, **NOT** OWNER-imposed constraints.
- Quotes are *not* broker fills; same-millisecond bid/ask order is unknown, and historical spreads, commissions, financing, margins, FX and slippage are incompletely certified.
- M1/M5/M15 and all lifecycle cells reuse previously exposed history and are highly dependent. No fresh CONFIRMATION, PROTECTED, independently reserved outcome identity, posterior-picking or valid multiplicity adjustment.
- There are zero actual orders and no cTrader Cloud activation. HARD21 is not demonstrated for any full ISO week; current source covers only a limited 4-hour period.
- Canonical V2 account and C033 reserved identity are unchanged. Prior negative/insufficient findings remain in force.
- **Director disposition: NO PROMOTION** of any policy to competitive cBot trading. The capability to compare separate exits is now integrated; admission of a complete strategy requires native historical BID/ASK cost verification, adequate independent chronology, real single-account multi-symbol margin accounting and demo.

## Evidence links
- Source/product [PR #116](https://github.com/mariancradulescu/mxm-quant-greenfield/pull/116).
- Warm-up safety [PR #117](https://github.com/mariancradulescu/mxm-quant-greenfield/pull/117).
- Native exposed quote study [run #39777231786](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/39777231786).
- Original prior run [#39776838582](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/39776838582).

This is not a product promotion or authorized live execution.
