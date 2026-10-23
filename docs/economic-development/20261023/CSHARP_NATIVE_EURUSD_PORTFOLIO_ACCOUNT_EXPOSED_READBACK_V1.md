# Native Pepperstone quote source into C# EUR200 portfolio account engine — exposed DEVELOPMENT

Date: 2026-10-23. Integrated extension of the existing single-instance C# product and preserved R3 custody. This PR adds no parallel trading system, new market providers or new broker connection.

## What now executes

Before this patch, PR #128's reusable C# single-account multi-symbol replay had only **mathematical/artificial** fixture evidence. This patch connects its very same execution and capital classes to the **original encrypted Pepperstone EURUSD BID/ASK 2026-09-09 08:00–12:00 UTC** capture, run `39660692230`.

Under existing native protected environment `mxm-r3-custody-v1`, the original release's sealed source `d2fae5641b759b1c8c24161d83d62d39e104eafd` is pinned and independently redecodes original protobuf wire events. Existing `chronology_csharp_bridge.py` verifies ciphertext SHA, plaintext SHA, historical account fingerprint, original source/run/attempt, pagination, wire receipts, exactly **14,003 BID plus 14,209 ASK** events and derives a byte-hashed chronological NDJSON stream. This workflow then compiles and runs `MxmPortfolioNativeQuoteReadback.csproj`, validates that **exact stream hash equals the protected bridge's readback**, and feeds atomically grouped same-millisecond snapshots to `MxmPortfolioAccountReplay`.

The native-quote adaptor never fabricates later timestamps to enable an order: its closed-bar decision happens at a bar-transition quote timestamp and any simulated decision can fill only on a **strictly later** quote event. It excludes conflicting same-side revisions within a millisecond, crossed BID/ASK and stale incomplete quote pairs; it never infers within-ms cross-side arrival order. No future quote is interpolated to fill a missing interval; causal kernels must warm up again after a gap.

The original cBot model still uses ONE continuous **EUR200** cash ledger, mark-to-liquidation equity and aggregate account margin. All simulated monetary execution prerequisites are **unverified modeling inputs**, explicitly fixed here to `1000` base units, `€50` per-position margin, `€0.10` each side, `0.00002` quote-price slippage each side, `EUR-per-USD=1/1.10`, `€1.20` estimated stop exposure, and the existing C# Adaptive family with 5-minute bars. These values are NOT Pepperstone historical commissions, leverage, currency conversion, swap, broker min-volume, stop executions or guaranteed liquidity. There are no broker orders. The model comparison is a **reanalysis of already DEVELOPMENT-exposed data**, not a new protected trial or alpha selection.

## What is verified

The no-secret CI produces a shape-compatible artificial bid/ask quote stream and confirms that the existing C# replay correctly consumes genuine-format timestamps, bar boundary signals and a later executable-side quote. The independent Python test recomputes the continuous cash and bid-side marked equity from the C# ledger and last quote, and rejects tampered invalid event metadata. The protected native workflow additionally checks original source digests and native totals and independently verifies every recorded debit/credit in its modeled cash ledger before encrypting all detailed private outputs to the unchanged existing public recipient.

A limited public receipt records the actual native price-event count, simulated account entry/exit counts, cash and marked equity under those **explicit unverified costs**, quote-source hashes, a no-promotion classification, zero complete ISO weeks, and zero live orders. All private individual decisions and trading traces remain in the existing encrypted artifact.

## Scientific and operational disposition

**This source is EURUSD ONLY and spans four hours.** It is neither multi-instrument native historical proof nor coverage of any complete ISO UTC week, and 11,414 same-ms cross-side groups have unproved original event-arrival order. Its venue-specific volume lattice, actual historical spreads at execution, commission schedules, swaps, margin dynamics, liquidations and native cTrader fills are unproven.

No advantage is certified, HARD21 is false, no C033/V2 economic identity has been added/promoted, no independent confirmation or protected-forward data has been opened, and neither Cloud nor live orders are enabled. The canonical persistent account state, OWNER1807, existing R3 keys, active authority, branch protection and custody have not been modified. The workflow may verify the economic accounting of the same model against native *prices* but cannot independently certify trading *execution* on a broker account.

To complete the objective, the next evidence must resolve multi-symbol broker-native executable quote coverage and actual instrument-specific cost/margin/FX feasibility over enough complete ISO UTC weeks, then prove on DEMO that one cTrader instance recovers its broker positions without duplicate orders or manual takeover. Repeated profitable model cells on this original four-hour window are not confirmation.
