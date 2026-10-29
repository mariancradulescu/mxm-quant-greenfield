# Cloud unknown-order frontier — OWNER technical decision, 29 Oct 2026

## Result: REPROIECTEAZĂ, but do not remove Cloud entry stop

Existing durable Desktop before-send checkpoint remains. Cloud LocalStorage.SetString retains values for the run only; Flush is a no-op and Reload leaves memory unchanged. The Cloud refusal in MxmNativeRunFence remains.

New broker-native HistoricalOrders observations (documented in cTrader Algo from 5.1, for Cloud/CLI/Desktop) are read in the SAME native C# cBot without local storage or broker secret, only as observational evidence. A shared deterministic canonical inventory deduplicates by broker order ID, checks account scope, time, type, quantities and conflicts, and correlates a still-known original client comment with both a broker historical order and an independently observed opening deal. Historical order status is a fact about an observed order, NOT a durable before-send client intent, a guaranteed complete history or a server-enforced idempotency key. Positive matches cannot release a pending request or authorize retry. No new trading path is created.

## Rigorous indistinguishability

Consider two causally possible worlds on an unreceived Cloud restart.

World A: the earlier process crashed BEFORE transmitting an original market order. Broker live positions, pending orders, historical orders and deals are all absent.
World B: the earlier process transmitted it and crashed before the response; the broker has not yet processed/advertised the in-flight request. At restart the SAME four broker collections are absent, but the original request executes afterwards.

The restarted bot also lacks the durable original pending-intent record because Cloud LocalStorage was memory-only. It therefore observes the SAME input in A and B. Blind retry may be economically desirable in A but can double-enter B. Neither more empty snapshots, a delay, an absence in historical orders, an error-looking status for another observed order, a random new comment, nor reusing the same non-idempotent comment establishes an authoritative FINAL negative acknowledgement of the missing request. The fixture explicitly checks that both indistinguishable restart prefixes remain NO_RETRY.

Consequently the currently evidenced primitive set does not permit proof of both guaranteed autonomous post-crash new entries and guaranteed duplicate-free reentry after arbitrary in-flight request interruption. This is a conditional impossibility of the current design, NOT proof that a broker could not provide a stronger documented primitive. A broker-side atomic idempotency key, documented bounded-finality negative/positive request status with an original durable ID, or an equivalently strong protocol is needed. Merely building a permanent log without broker-side idempotency/finality also does NOT solve the atomic send gap.

Technical next dependency: obtain exact authoritative Spotware/Pepperstone guarantee, if one exists, for broker-side idempotent order submission or final acknowledgement of originally ambiguous requests within Pepperstone Europe Cloud cBot. Without it, Cloud remains FAIL-CLOSED. No Cloud start or LIVE/DEMO order has been authorized, undertaken or claimed received.

## Authority and evidence

- Official HistoricalOrders API since 5.1 with FindAll, Id, Comment, Label, Status, SubmittedTime, broker order information:
  https://help.ctrader.com/ctrader-algo/references/Trading/HistoricalOrders/HistoricalOrders/
  https://help.ctrader.com/ctrader-algo/references/Trading/HistoricalOrders/HistoricalOrder/
  https://help.ctrader.com/ctrader-algo/references/Trading/HistoricalOrders/HistoricalOrderStatus/
- Vendor Cloud storage:
  https://help.ctrader.com/ctrader-algo/references/Localstorage/LocalStorage/SetString/
  https://help.ctrader.com/ctrader-algo/references/Localstorage/LocalStorage/Flush/
  https://help.ctrader.com/ctrader-algo/references/Localstorage/LocalStorage/Reload/
- Native API exposure and compile pass do not show complete broker history, broker latency bounds, or native Cloud operational acceptance. CI fixture is artificial causality verification, not broker execution.

## Economic/risk observations (NO parameter change)

Current 80 EUR maximum ticket margin, 120 EUR minimum post-entry free margin, 2 EUR estimated new-entry loss are immutable OWNER ceilings. Separate configured 40% margin fraction and 1% equity stop-risk reference remain cumulative guards. Under a hypothetical flat/no-fee account with free margin equal to equity, the necessary admission bound on a ticket is M <= min(80 EUR, 0.4 times free margin, free margin minus 120 EUR). This does not authorize an order or prove stop-fill costs.

| Equity EUR | Fixed 2 EUR as equity % | Fixed 80 EUR margin as equity % | Maximum margin before fees (EUR) |
|---:|---:|---:|---:|
| 80 | 2.50% | 100.00% | 0 |
| 200 | 1.00% | 40.00% | 80 |
| 350 | 0.57% | 22.86% | 80 |
| 1000 | 0.20% | 8.00% | 80 |
| 5000 | 0.04% | 1.60% | 80 |

A positive fee reduces the EUR200 max margin below 80 if EUR120 must remain. Fixed per-ticket limits can prevent proportional scaling when capital increases; this is a constraint sensitivity, NOT a risk recommendation or evidence of higher returns at increased risk. A scientifically credible optimal policy requires causal all-cost account paths with margin, broker volumes, loss streaks, drawdowns, ruin and actual HARD21 activity. No limit changes and no repeated closed experiment.

## Final boundaries

No protected historical economics, ledger, identity or source is changed. No new after-cost alpha, real continuous EUR200 weekly/monthly equity, HARD21, request idempotency or native Cloud receipt is certified. Orders ZERO. Follow-up effort should target the broker primitive/finality dependency and a separately source-admitted informative economic mechanism, not another generic local patch.
