# MXM — price/spread temporal-order investigation, 2026-10-12

Role: EXECUTOR_DIRECTOR_MXM_QUANT_GREENFIELD. Executed preparation of one observable hypothesis; no empirical market pilot, NET result or independent acceptance is asserted.

## Authentication correction

cTrader Open API machine-side access already exists. The seven pinned source files were verified byte-for-byte against Git blobs at HEAD 2fda6cd6564743ae9fd8fe80b9ea75b56e250665. authenticate_segment enforces explicit SCOPE_VIEW, the accepted account fingerprint, isLive and bound account authentication. The existing cost-frequency workflow binds the three CTRADER secrets on GitHub Actions. No credential values were requested, read or exported.

Run 38197915724, job 114644641381, is SUCCESS. Its actual public log reports M5=3066 and BID_ASK=23996 at completion of acquisition. These are verified historical machine-side requests, not new requests in this execution. Missing local variables do not negate that access. The earlier signed executed-flow rejection is preserved and was not rerun.

## One hypothesis using available observations

PRICE_SPREAD_TEMPORAL_ORDER_RESPONSE_V1 distinguishes a midpoint move followed by spread widening from widening preceding a midpoint move. Proposed channels are reactive inventory risk versus pre-emptive adverse-selection quoting. The channels are hypotheses, not causally identified participant behavior.

The input is historical native BID/ASK price/time, not trades, aggressor flags, order-book sizes, external prices, or an invented field. The area of the causal midpoint/spread trajectory is computed over 45 one-second snapshots ending one second before the entry reference. All snapshots require both sides age <=5 seconds and side skew <=2 seconds. Incomplete pages, crossed quotes and conflicting same-side/millisecond prices are censored. Only floating-point cancellation uses a 64-ULP numerical tolerance.

The order statistic is not algebraically identical to terminal return, spread change, update counts, last2/5second side catch-up, or up/down revision counts. Those earlier designs were read and retained. The new area contains sequence information from the same price/time source; different features alone do not establish predictive value or a new profitable economic mechanism.

## Actual local results

Eleven synthetic implementation tests passed; exit code 0. Tests cover endpoint-equivalent opposite path orders, exclusion of future values, timestamp conflicts, hasMore, stale states, constant-spread floating-point cancellation, EUR200 limits, missing cost, unknown selected exit, one position, matched shadow comparators, and an adapter that ignores the saved previous predictors and targets.

The controlled numeric witness has areas +4.000000000002451 and -4.000000000001204 bps². Terminal midpoint return and terminal spread change are both approximately +2.2 bps on each path; their terminal quotes, counts and last5second quotes match. Model orientations differ. These values are SYNTHETIC and prove feature separability only, not alpha.

The code includes analyze_saved for the existing authenticated costfrequency full-result schema. It uses all saved15minute candidate boundaries, deduplicates native symbol/time, retains missingness, and reuses unchanged accounts_v1 for side-aware commissions, FX, conversion fee and funding/slippage scenario accounting. It neither calls the old predictors nor accepts their saved outcomes as new responses. It does not authenticate or decrypt inputs itself: the existing unchanged source-authentication boundary must precede it.

## Frozen prospective economic design

DESIGN_V1.json fixes one direction law (-sign(area)), one45second feature path, one15minute exit, native minimum ticket, one position and allocation by pre-entry cost then native ID. There is no parameter search, direction inversion, exit rescue or winner symbol.

Capital starts at EUR200. Planned aggregate risk <=EUR2, margin <=EUR80 and reserve >=EUR120; relative1%/40%/60% restrictions also tighten these limits after losses. Cached15minute entry risk is a prior-M5/cost planning proxy, not a guarantee against gaps or slippage. The primary accounting scenario uses2bps slippage per side and EUR0.10 funding per24hours. Current broker contract rates are not historical fill/charge evidence.

Comparators are same-entry midpoint direction, quote update-count asymmetry and cash. They are matched-entry shadow markouts, not separately certified executable capital portfolios. Unknown outcomes are not zero. The first selected unknown model exit stops the ledger without replacement; complete NET is then null. Weekly support is retained in the adapter. A future descriptive pilot must report temporal halves; no statistical certification or independent confirmation is supplied by these tests.

The cohort is the entire saved, previously outcome-blind class/quote-stratified costfrequency cohort, not a new arbitrary small panel or PRIMARY145 cap. It is a bounded existing corpus, not the full broker universe. Prior cohort selection and all adaptive exposure remain applicable.

## What remains unexecuted

No authenticated market payload was opened or processed in this session. Empirical feature coverage, return increment and NET remain UNMEASURED. The code adapter was tested on a synthetic schema fixture, not on the private source. This is a frozen investigation design and tested analysis kernel, NOT a qualified market candidate, complete autonomous runner, ARM, executed backtest, profitable system or HARD21 evidence.

The unavailable operation is a new workflow_dispatch call through the current connector. The existing successful costfrequency workflow is push/path bound and guarded by an already consumed one-use identity. Rerunning it or modifying its closed execution file would not be a legitimate new pilot. No such operation was attempted; no refused delivery workflow was varied and no security protection was modified. This does not negate the existing authentication, saved raw pages, secret bindings or machine compute.

An independent empirical invocation through a legitimate permitted runner is still needed to process the authenticated saved source with this kernel, measure support, and test the one fixed hypothesis. No owner token, manual command, new authorization or promised NET is requested. No source/strategy family is declared exhausted.

Code SHA256: 0f8a384542329645a7e2129d0b48fd5f6af735b9eabb1e5d036b80707e0321cb.
Tests SHA256: 69d62b576db76a5ba1bbf0b44ee062e9bc112f18304bff04b79b1afc7bd31c37.
Design SHA256: 5f9da2487c84f9176291ecfc7518d3a0c62396eb9b26e6265f00d29fdd706837.
Full source hashes and the execution receipt are in LOCAL_RECEIPT_V1.json.

Zero new broker requests, orders, protected-forward openings, Cloud deployments, external providers and old-exact reexecutions. Prior files and encrypted results remain unchanged.
