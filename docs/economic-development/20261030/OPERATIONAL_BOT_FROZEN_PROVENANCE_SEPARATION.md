# MXM B–E — one evolving native C# product, historical research frozen; full broker universe source-first

## Architecture decision: immutable past, mutable singular future

The old **scientifically registered** `research_core_v4/native_tick_replay_v1/csharp/MxmReferenceProductBot.cs` and `MxmReferenceBot.csproj` remain byte-exact, together with all other historical implementation blobs pinned by `research_core_v4/laboratory/PORTFOLIO_PROGRAMME_20261030.json`. Their already closed economic outcomes stay closed. Do **not** update/relabel old evidence hashes or disable historical identity regression.

The **only newly evolving operational cBot build root** is `research_core_v4/native_tick_replay_v1/operational/MxmOperationalProductBot.csproj`. It compiles one cTrader robot named `MxmReferenceProductBot`, retaining all original shared C# kernels and guard classes by source link from the existing historical directory, plus a current working copy of the native adapter with **one new observation-only hook** and a read-only partial class implementation `MxmNativeEconomicObservation.cs`. This is not a second independently executing strategy or another live system. The old C# build root is a historical **non-published fixture**; the new one is the product's working HEAD. Both retain **AlgoPublish=false** and are only compiled in CI. No robot has been imported, activated, connected to a trading account or deployed.

This is deliberate version separation rather than modifying a frozen experiment, changing model parameters, eliminating CI checks or importing code from an unrelated provider. The new product can be changed by new engineering PRs without breaking the historical economic sample registry, subject to ordinary source and account-risk gates. The older bot remains a *read-only reproduction fixture*, not a second deployable production programme.

### Native observation now physically implemented in the evolving product

When the existing `NativeObservationOnly` run fence is already latched, every actual native completed-bar callback also calls `ReportNativeMinimumTicketAperture()`. The separate partial code requires valid locally observed two-sided native BID/ASK receipts no older than 5s, current native quote equality, noncrossed shape, exact broker minimum-volume lattice, a valid EUR account, native `GetEstimatedMargin(Buy/Sell, minUnits)`, `AmountRisked(minUnits, StopLossPips)` and read-only account equity/free margin. An invalid or absent input becomes an explicit `_UNAVAILABLE`, never a free or executable estimate.

The observable record reports **native snapshot spread in bps, minimum/step units, minimum BUY/SELL EUR margin, illustrative native stop-risk EUR, EUR equity/free margin and quote receipt age**. It explicitly reports **UNKNOWN** for actual round-trip commission, slippage, contract/payoff multiplier, estimated NET expectancy, broker fills and Cloud recovery.

The existing trading path, capital account gates, stop-loss protections, storage/unknown-order fail-closed logic and `MxmNativeRunFence` are unmodified. The extension contains **no order or trading mutation operations**. CI builds the true evolving `.algo` and its frozen historical reference with a dedicated separation/guard test. These are offline compilation checks **not native broker reception**, not actual tick acceptance or Cloud validation.

Cloud cannot be activated for orders based on these read-only receipts; Spotware Cloud LocalStorage is not restart-durable:
- https://help.ctrader.com/ctrader-algo/documentation/cbots/cloud-requirements/
- https://help.ctrader.com/ctrader-algo/references/Localstorage/LocalStorage/

## Economic universe: NOT PRIMARY145

A distinct, original authenticated Pepperstone Europe **read-only 2026-09-22 LIVE EUR200 account snapshot**, SHA256 `9553fd3b60f4f5dc8428c30d19cde7d7a13cad12de18a27a93785836e97f5f77`, contains **5,324 broker identities** over **36 broker asset classes**. Of these, **1,690** were accessible for new entries on capture in **31 asset classes**; source-native minimum-ticket necessary margin feasibility was **1,609 both BUY and SELL**, **40 BUY only**, **41 neither**; among the 1,609 both-direction necessary-feasible, **1,563** met the historical DIRECTOR EUR80 ticket limit, and **1,491** were below illustrative EUR40 ticket margin. **Eight accessible broker TEST symbols are explicitly unqualified for economic candidacy**, not counted as viable strategies.

These numbers are original-source **necessary feasibility snapshots**; no live historical spreads, slippage, commissions paid, multipliers, EUR/asset conversion, stop/aggregate risk, bid/ask time alignment, single EUR200 funded path or broker fills are thereby certified. The exact public 31-class aggregates are in `docs/economic-development/20261030/BROKER_FULL_UNIVERSE_EUR200_SOURCE_APERTURE.json` and a no-outcome private-input executable reader in `research_core_v4/laboratory/broker_full_universe_source_aperture_20261030.py`. Original broker ZIP stays in OWNER private Library, not in GitHub; this is **one source-only review**, no new price outcomes or repeated rejected strategy tests.

**Do not conflate these populations:** the project has a separate historic M5 corpus of approximately **1,576** instruments, PRIMARY145 annual M5, intermediate support panels and the **5,324-symbol** source-native broker account inventory. This work **does not assert a temporal economic join** from the broker 1,690 accessible symbols to historical M5 returns or fees. Such a join needs exact symbol identity, source-aligned clock, quote/cash conversion and current vs historical term conditions before any NET claim.

The existing DIRECTOR 80 EUR ticket margin / 120 EUR reserve / 2 EUR risk gates remain effective as coded, but they must not be reported as immutable OWNER mandates or universal evidence that all products above a cutoff are untradeable. Any later changes require demonstration of the SAME continuous EUR200 account constraints and no weakened fail-closed risk boundaries, not retrospective cherry-picking.

## B–E admissibility and next economic work

New **causally predeclared** predictive study should join symbol-ID and timestamp-supported authentic source history to executable **EUR per minimum ticket** broker costs, actual payoff multiplier, slippage and aggregate account/margin/stop risk **before economic-model promotion**, wherever evidence is genuinely present across the whole authorized venue. No required one-year data collection for all instruments; source coverage can vary and must be declared and censored correctly.

No historical strategy re-run, inversion or re-tuning. No claim of robust NET, full-account HARD21, actual broker order, Cloud native receipt or independent protected confirmation. Engineering result here is **one operational source tree that is allowed to evolve without falsifying the frozen scientific record** and a wider BROKER account geometry map, not completion of the eventual live product.
