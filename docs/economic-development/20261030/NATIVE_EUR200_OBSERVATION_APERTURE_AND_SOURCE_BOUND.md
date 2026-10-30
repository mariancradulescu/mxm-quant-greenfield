# B–E — authentic PRIMARY145 EUR200 minimum-volume account source aperture (2026-10-30)

## New material non-PnL result: funding feasibility vs current C# design

This was **not** another experiment on closed #284/#286/#287 predictors. No P&L outcomes, retuning, protected confirmation, new broker request, trade, account reset or Cloud activation. It is one verified **source-only account-fundability envelope** answering which original PRIMARY145 annual instruments are constrained by minimum broker ticket margin when starting with EUR200.

Source: the ORIGINAL accepted read-only Pepperstone Europe broker-universe ZIP dated 2026-09-22 04:12:43Z, SHA256 **9553fd3b60f4f5dc8428c30d19cde7d7a13cad12de18a27a93785836e97f5f77**, and original frozen 145-symbol research roster. Original snapshot remains private, not uploaded into GitHub. A deterministic selftest-checked no-outcome reader is in `research_core_v4/laboratory/primary145_native_eur200_preflight_20261030.py`; full class aggregates are in `docs/economic-development/20261030/PRIMARY145_EUR200_NATIVE_SOURCE_FEASIBILITY.json`.

**Actual source observation, at snapshot date only**:
- **145/145** PRIMARY145 identities were both-direction minimum-volume margin-necessary-feasible using **EUR200**, *before* spread, entry commission, stop-risk, price changes or shared capital occupancy.
- **129/145** were also under the **current historical DIRECTOR 80 EUR per-ticket margin threshold** in both directions.
- **16/145** had a BUY or SELL minimum ticket margin above this 80 EUR implementation limit: **9/9 metals**, 4/75 Forex, 1/2 cash indices, 1/3 forward/futures-style and 1/2 other/test categories. The other/test categories are not thereby validated for economic research.
- The **80 EUR margin / 120 EUR reserve / 2 EUR new-entry risk** numbers are pre-existing DIRECTOR implementation choices, **not immutable OWNER numerical limits**. The OWNER's fixed cash requirement remains one continuous **EUR200** account and system HARD21. No protective cap was relaxed by this work.

The 145 snapshot entries constitute **a necessary margin screening only**. Their broker minimum volume lattice and expected margin do not establish an actual historical spread, slippage, commission or conversion, stop-loss occupancy, nonlinear product multipliers, trading-session fills, expected NET EUR return or profitable HARD21. No market strategy, prediction, source M5 price series or previously closed economic result was evaluated.

## Product immutability boundary materially identified and preserved

A proposed additional native read-only economic observation method in `MxmReferenceProductBot.cs` was locally compiled, but the existing compulsory CI *correctly failed*: the **entire** bot file is pinned by exact SHA256 in the original **frozen** `PORTFOLIO_PROGRAMME_20261030.json`. The CI regression is `LAB_PORTFOLIO_IMPLEMENTATION_CHANGED`. This is an authoritative preservation barrier, not an economic model failure.

**The change was fully withdrawn**, restoring the exact historical bot blob `62efbd708d8f7d524dd65da685e3c41ba42de881` and leaving all trading, observation, Cloud, safety and native C# product files untouched. We did **not** rewrite old experiment hashes or bypass the guard merely to obtain green CI. A future product revision must be separated from historically frozen research source identities while preserving one deployable cBot and the immutable scientific provenance; it must not alter any closed outcomes or silently relax protections.

Spotware official Cloud requirements and LocalStorage API document that Cloud LocalStorage is **run-memory-only** and the instance filesystem is not restart-durable; the current unknown-order fail-closed Cloud barrier remains valid. Official docs:
- https://help.ctrader.com/ctrader-algo/references/Localstorage/LocalStorage/
- https://help.ctrader.com/ctrader-algo/documentation/cbots/cloud-requirements/

The existing cBot already uses native `Symbol.GetEstimatedMargin`, native stop-risk estimates and observed cost FX on its **guarded Desktop/trading path**, but its read-only observation output is **not expanded by this PR**. Neither old nor new code was run against Cloud or live broker account in this study. Production C# functional acceptance remains open.

## Economic consequence and next action

Prospective cash-denominated predictors must be evaluated against *time-aligned observed broker cost/size and true product payoff* rather than signed per-trade bps. Preserve all asset classes, Forex and H1 without outcome-driven pruning; a >80 EUR necessary margin result is not proof that a larger position is safe, and a <=80 EUR result is not proof of positive expectancy. Use suitable current broker-native observed costs and the same EUR200 equity path before any strategy promotion; do not rerun/invert closed models.

**No new alpha, no broker fills, no HARD21 certification, no Cloud acceptance or order authorization is claimed.**
