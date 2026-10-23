# Existing-position stop risk must use the current equity mark

B–E continued, 23 October 2026. Existing product, single shared EUR200 account; source after PR #135 `cfbbcca92219198fadf1ed658c69e60d9334865f`.

## Concrete product defect
The cBot compares aggregate estimated stop risk to a fraction of **Account.Equity**, which already includes floating PnL, but calculated an existing position's stop distance with `abs(entryPrice - stopLoss)`. This mixes risk bases. A profitable long with entry/stop 1.1000 and current BID 1.1050 reports zero entry-to-stop risk, despite 50 pips of potential drawdown from current equity to that stop. A stop moved above entry can still give back floating gains. For a losing position, the entry-based calculation also counts loss already included in equity.

## Actual adapter correction
A pure `MxmStopRiskGeometry` helper calculates long BID minus stop, or short stop minus ASK, divided by pip size. The actual cTrader adapter reads those liquidation-side quotes from each existing owned position's Symbol and passes the resulting distance and actual volume to its original `Symbol.AmountRisked`; the original common-account risk budget and friction reserves remain in place. No entry-price-based distance remains in that order path.

Crossed/invalid prices, invalid direction or pip size, and stops already touched or passed refuse **new admission**. A touched stop is unresolved execution, never zero risk or an invented close. The helper does not place/cancel orders or move a stop. Existing owned-position exit paths run before this new-entry admission check. Foreign exposure isolation and the no-LIVE/default-no-DEMO controls remain.

## Meaningful offline acceptance
The helper is compiled into both the actual cTrader `.algo` and the existing economic-reference binary's stop-risk fixture. Fixtures exercise long/short gains, a stop above/below original entry locking in profit, a losing position's remaining risk, touched/passed stops, crossed prices and invalid geometry. A joint-budget regression demonstrates that an artificial EUR200 equity / 2% risk budget would admit an extra order under the old zero-risk calculation but rejects it with the correct EUR5 current-equity-to-stop estimate (explicitly artificial EUR0.10 per pip).

Native CI must compile the actual existing product and run the same helper's fixtures. This is **not a native DEMO broker stop execution or recovery test**. Quote freshness, account snapshot races, actual stop activation method, broker conversion approximation, gaps, slippage and execution beyond the stop remain limitations. `AmountRisked` remains an estimate; no guaranteed loss cap is claimed.

No strategy parameter tuning, scientific candidate, economic trial or canonical ledger mutation; no new provider, broker request, order, Cloud activation, credential, authority or OWNER checkpoint change. Risk admission is an engineering component of the still-unqualified complete product. This change does not retrofit real stop behavior into the reference portfolio's explicitly hypothetical fixed-stop-risk scenario.
