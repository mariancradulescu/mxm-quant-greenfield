# MXM B–E — native EUR stop-plus-cost correction and source-authentic 1,576-account fee admission

## Why this is a change to economic *admission*, not another closed hypothesis

The original #290 first-only 88-trade scenario was **rejected**: 20/30 scenario stop exits lost over the existing EUR2 coded risk limit when the cash cost was added to the stop loss. It is not reopened, selected, inverted or retuned. This change repairs the **operational native C# pretrade path** against the same cost-accounting failure *before* a new order decision could be made.

Before this PR the single evolving operational bot called `MxmOwnerEntryEnvelope.Check` and `MxmStopRiskAdmission.Check` using the configured fixed friction floor (default EUR0.20), after checking the estimated BUY/SELL fee fit within the floor. That did **not explicitly add the observed BID/ASK spread cash value** to the same new-entry stop-risk budget.

### The actual operational C# implementation

Without modifying the pinned frozen historical source, add `MxmNativeEstimatedFrictionGuard.cs` (pure, decimal, overflow-checked) and `MxmNativeEstimatedFrictionObservation.cs` (current native cTrader `AmountRisked` on observed BID/ASK spread):

```
conservative_round_trip_reserve_eur =
    max(configured_existing_friction_floor_eur,
        2 * max(native_estimated_buy_commission_eur,
                native_estimated_sell_commission_eur)
        + native_current_spread_risk_eur
        + explicit_extra_slippage_cushion_eur)
```

An invalid quote/volume/PipSize, unknown commission FX, missing/invalid/spread-cost conversion, negative cost or overflow is **no new order**; **not** zero. The synthetic fixture also revealed a real extreme-value `decimal` precision case: adding a strictly positive small cost to an enormous amount can round to the unchanged original amount. The operational sum now requires every strictly positive fee/spread/slippage component to **strictly increase** the EUR budget; precision loss fails closed instead of being silently accepted. Default additional slippage cushion is EUR0.10 (new conservative parameter; a declared **scenario**, never a broker slippage ceiling). The spread may be conservatively double-counted with `AmountRisked` in some broker geometry; this is protective and not a predictor. Historical fee estimates and cTrader `AmountRisked` do **not** guarantee a real fill loss bound.

The **same** native spread-inclusive reserve is applied when searching the broker volume lattice, after writing the durable PREPARED intent when applying stop risk and the absolute entry envelope, and again on the final native quote/fee snapshot **before `MarkSubmitted`**. Each of those three points additionally checks **EUR free margin after estimated ticket margin AND the full observed round-trip cost reserve**, rather than relying solely on a fee-only deduction. The previous account/entry fee check is still executed independently; the additional free-margin gate can only reject more estimated entries. The final recheck fails closed if the observed cost floor has increased. The old configured fee-reserve check remains; it is **not relaxed**, and neither are the current 80/120/2 numeric runtime ceilings. Owner has explicitly clarified these are historical **DIRECTOR-designed current guards**, **not immutable OWNER numerical mandates**. No automatic relaxation or new orders are authorized by this change.

The observation-only mode also prints a source-native estimate of the *remaining maximum budget for a two-sided commission* after current minimum-ticket stop-pip risk, observed spread cash and declared slippage cushion under the current coded EUR2 stop+cost ceiling. It prints `UNKNOWN` for actual commissions, predicted NET and broker fills; an absent/unverified book never appears as cost zero. This is a **single existing cBot**, not a parallel product.

### Separately executed original-source EUR200 money scale (no model re-run)

Authentic original source: Pepperstone Europe **read-only dated September 22 2026** broker 5,324-symbol capture ZIP pinned SHA256 `9553fd3b60f4f5dc8428c30d19cde7d7a13cad12de18a27a93785836e97f5f77`, joined exactly by symbol ID / name / asset class to the distinct **1,576**-instrument M5 quality table contained in the accepted original DELTA archive. Code **exactly byte-reproduced** in `research_core_v4/laboratory/mxm_1576_account_eur_fee_capacity_20261031.py` (original local Git blob `67d66e0949724580baef76aa219104c7c805c175`); full original 29-class public report SHA256 `7d5c442dac8cc7a3da31fde711f99e1f97eb29b8b35d9a4ab53166b3fc62d6ae` saved separately in user-accessible artifact.

- 1,575/1,576 have *necessary only* broker min-ticket BUY+SELL margin under initial EUR200, in the dated capture.
- 1,530/1,576 also under current DIRECTOR 80 EUR per-ticket margin limit.
- Of that group, **873** have explicitly supported native commission type2 USD/lot and USD minimum fee, so a single declared conversion scenario can price both fees at minimum volume. The remaining **657 are NOT disqualified** and require another fee/asset-conversion pathway.
- Hypothetical USD-to-EUR 0.90: two-side fee **median EUR0.036**, **maximum EUR0.054** in the 873 supported instruments. Every one of 873 is within the current EUR0.20 *fee-only* floor.
- No actual historical EURUSD point-in-time conversion, observed BID/ASK spread, slippage bound, instrument multiplier, broker stop fill, financing, margin path or true-cash settlement was certified. Thus **not a profit forecast**. The point is that in this specific broad observed population the declared broker commission alone is *small*, while price/quote spread and complete stop exposure can dominate funding.

The original external zip and detailed protected price series are never uploaded to the public GitHub repository. No new price-based prediction or outcome evaluation, no relaunch of closed trials, no restricted 145/157 subset chosen as permanent scope.

### Independent tests and limits

A standalone source-blind C# fixture covers both commission sides, spread, extra cushion, preservation of larger configured reserve, negative and overflow safe failures, and one expected positive and negative EUR2 stop-plus-cost admission. The dedicated operational CI compiles the evolving native `.algo`, checks frozen source SHA256 registry unchanged, validates native observation purpose and order ambiguity fail-closed, and checks the added paths before merge.

**No** LIVE/DEMO orders, Cloud activation or protected source disclosure. The Cloud LocalStorage/restart-ambiguous-order limitation is unchanged. The resulting C# functional correctness remains offline/CI evidence; it does **not** prove actual broker executable prices or native Cloud recovery.

## B–E next economic bottleneck

The real blocker to NET qualification is now narrower: a causal predicted cash reward must exceed **time-aligned** real BID/ASK spread, commissions, funding, slippage and the aggregate shared-account stop risk on the actual broker contract geometry. No model is promotable until it proves that with a continuous EUR200 account and full broker-side execution evidence. Broker-confirmed HARD21 remains 0 in these read-only evaluations. No proprietary source beyond existing permissions is assumed.
