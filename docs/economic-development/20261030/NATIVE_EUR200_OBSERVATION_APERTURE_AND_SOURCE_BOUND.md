# B–E native product convergence — current EUR200 minimum-ticket economic observability

## Why this is material, without another negative strategy backtest

The closed #284/#286/#287 studies proved a **sum of percentage returns is not a EUR200 broker-cash advantage**. This work does **NOT** reopen those mechanisms, train a new model, report new profitability, reassign OWNER risk authority, change capital, change any broker order or authorize Cloud execution.

Instead it connects the *existing* single `MxmReferenceProductBot` **native observation-only** purpose to real-time **native account/symbol** price and minimum-volume constraints: at every observed closed-bar callback, after a valid locally observed two-sided native book, it prints a structured `MXM_NATIVE_MIN_TICKET_ECONOMIC_APERTURE` receipt including:
- Exact current symbol identity, native minimum/step volume, BID, ASK and observed crossing-spread in bps;
- Native `GetEstimatedMargin` minimum BUY and SELL in **EUR**, and `AmountRisked` at the configured **illustrative stop pips**;
- Current account equity/free margin and observed quote receipt age, with a *necessary margin only* status;
- Explicit `UNKNOWN` for round-trip EUR commission, slippage, contract-specific NET EUR and predicted EUR edge.

The receipt is read-only, has **no order/event transmission, order ledger, storage, change to native trading execution, equity resets, new broker credential, or new workflow**. The existing `MxmNativeRunFence` must already be latched to `ObservationOnly`. An absent/stale quote, crossed or mismatching book, invalid lot/margin or non-EUR account returns `_UNAVAILABLE`, never a zero-cost estimate or a broker-ready decision. Existing `OnStart` / `OnPortfolioBarClosed` trade guards, native account stop-risk admission and ambiguous order recovery are untouched.

This is a **capability** added to the existing native robot, **not evidence that it has actually been started against cTrader**. The no-order offline C# CI can demonstrate compilation and regression only, not cTrader Cloud runtime reception. No LIVE or DEMO orders, Cloud activation or permissions are authorized.

## Source-only real broker snapshot: 145 annual asset identities

A separate deterministic, source-blind preflight reuses the **original accepted 22 September 2026** Pepperstone Europe EUR200 broker-universe capture ZIP (SHA256 `9553fd3b60f4f5dc8428c30d19cde7d7a13cad12de18a27a93785836e97f5f77`) and the 145 already accepted original-development identity slots, **without reading any prices or reopening the closed model**.

- **145/145** were both-direction min-volume *necessary margin feasible* from the starting EUR200 cash in that dated capture. This is NOT proof of historical execution costs, commission, stop-risk, opening order admission, source timestamp correspondence or safe account survival.
- **129/145** have both-direction minimum ticket margins at or below the **current coded 80 EUR cap**. **16/145** exceed this *current DIRECTOR design* cap in at least one direction — including **9/9 metals**, 4/75 FX, one index, one forward and one other/test. The 145 roster does not become a permanent research exclusion and neither does H1/Forex.
- **Critical authority distinction:** the 80 EUR per-ticket, 120 EUR free-reserve and 2 EUR estimated new-entry loss were an historical DIRECTOR implementation. The OWNER fixed the **single continuous initial capital EUR200**, systematic HARD21, loss-safety and no unauthorized orders, **not these three immutable numerical caps**. This PR does **not** relax or modify the existing conservative C# caps; changing live sizing requires an economically warranted and separately safety-verified policy consistent with the existing mandate. A known 80 EUR cap failure is **not** proof the market could safely fund a larger position.

Full nine-class aggregates and snapshot SHA are in `docs/economic-development/20261030/PRIMARY145_EUR200_NATIVE_SOURCE_FEASIBILITY.json`. Reproducible **no-outcome** calculator: `research_core_v4/laboratory/primary145_native_eur200_preflight_20261030.py`. It requires the accepted original broker ZIP privately, the original repository `research_core_v3/state/PRIMARY_145_INPUT_MANIFEST_V1.json`, and source identity/hash acceptance. Original broker ZIP and per-symbol commercial terms remain outside public GitHub. The numeric public result is authenticated source-only metadata, not derived from an ML re-run.

## Real constraints not falsely solved

1. Pepperstone historically aligned BID/ASK, slippage, actual commission, conversion asset and payoff multiplier still have no certified complete 145-symbol path. Observed one-instrument snapshots can *inform* a later causal EUR cost filter but cannot authorize trades.
2. Native observation needs an actual supported cTrader session/runner. CI alone supplies **no** real broker quote sample or Cloud receipt; no Cloud instance was started.
3. Spotware official Cloud requirements and LocalStorage API (current 30 October 2026) establish that LocalStorage values are **run-memory-only** in Cloud and instance files can be deleted at restart. The fail-closed durable unknown-order recovery block therefore remains. See https://help.ctrader.com/ctrader-algo/documentation/cbots/cloud-requirements/ and https://help.ctrader.com/ctrader-algo/references/Localstorage/LocalStorage/.
4. This is not a new predictive mechanism or negative-ML test: **zero model evaluations, zero new P&L outcomes, zero broker fills**, and absolutely no HARD21 or persistent Cloud qualification claim.

**B–E decision:** next economic hypothesis should have a cash-denominated, broker-min-volume, contract/payoff-aware prospective expected NET value **before** integrating it into the existing shared C# account. Preserve all classes and durations for actual research; qualify cost evidence where it matters rather than building another generic infrastructure loop.
