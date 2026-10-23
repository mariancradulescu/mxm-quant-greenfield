# Broker stop / intent reconciliation V1

Continuation from official head bd19ec5f8a67c07e9a6f0b2c361b78fcf5e55c58 (PR138).
No restart, new authority, economic trial, external market feed or broker order.

## Finding

Confirmed material code defect, not a claimed observed broker incident. The old
adapter did not subscribe to Positions.Closed. A completed bar could publish a
nonzero intention while owned position P existed. A broker stop could remove P
before the strictly later quote. The queue still returned that direction, while
ApplyPortfolioDecision observed zero owned positions and could admit a market
entry if ordinary capital/risk checks allowed it. Those gates do not establish
that an old intention remains justified after a stopped position.
The optional portfolio replay instead clears its intent after an observed stop.
Existing synthetic stop tests therefore did not prove the product property.

## Product change

The actual compiled cBot subscribes/unsubscribes Positions.Closed. Events are
filtered by exact MXM label and configured symbol. An unexpected owned closure
(StopLoss, StopOut, TakeProfit, manual/other Closed, unknown reason) revokes that
symbol's queue AND increments its admission revision. It suppresses publications
for the observed current bar boundary; a genuinely later boundary can proceed.
No arbitrary foreign position/pending-order action is introduced.

A per-symbol fence is seeded with the actual recovered position identity, not
merely its count. Before publication, before consumption and immediately before
ExecuteMarketOrder, observed identity is reconciled. A missing or replacement
position invalidates the intent even if the closure event is delayed. A decision
already consumed is bound to an identity/revision lease and cannot survive an
observed closure before final admission. Other configured symbols keep their own
independent state. Cold restart contains no old intentions; multiple recovered
positions on a symbol are refused explicitly.

Deliberate reversal close is a narrow exception: the lease and ID must match an
explicit BeginReversal call; only the matching event with reason Closed can
acknowledge it. Successful close result with the same position ID AND empty book
must agree before one flat continuation can be issued. StopLoss, wrong ID,
failed result, still-open book, or absent/delayed event denies same-intent entry.
There is no tick retry or persistent block: a later new bar can decide again.
Neutral/horizon exits return as before. Native logs now identify symbol, close
reason, local revision and originating boundary without account/credential IDs.

## Verification and its limits

Native CI compiles the actual .algo against cTrader.Automate 1.0.21. The executable
C# fixture first reproduces the original queue counterexample, then enumerates
causal orders of publication, book removal, closure event and consumption. It
also exercises closure after consumption, replacement ID with unchanged count,
matching and contradictory reversal receipts, per-symbol isolation, cold state,
and next-boundary recovery. Product wiring and final-admission placement are
checked against the actual adapter source. Existing economic and custody
regressions remain required. All fixture evidence is explicitly SYNTHETIC.

Official API contracts consulted:
https://help.ctrader.com/ctrader-algo/references/Trading/Positions/Positions/Closed/
https://help.ctrader.com/ctrader-algo/references/Trading/Positions/PositionCloseReason/
They establish the event and reason interface, NOT a guaranteed relative order
between Tick, BarClosed, collection mutation and result callbacks.

No native broker-stop callback trace was obtained by this change. Actual cTrader
callback dispatch, a broker change invisible to both the local book and event
stream, the interval after the final check and before broker execution, account
recovery across disconnection, and cross-instance atomicity remain unproven.
An instrumented authorized native backtest/DEMO observation is still required;
compilation and interleaving fixtures do not substitute for that evidence. No
LIVE or Cloud activation is performed and no scientific acceptance is granted.

## Economic continuity

This repairs execution semantics and recovery admission, not a trading edge.
Continuous EUR200 accounting, source partitions, scientific budgets and canonical
economic identities are unchanged. The existing four-hour EURUSD BID/ASK source
is DEVELOPMENT exposed and proves no full ISO week. No result is promoted to
confirmation, no trade is added to manufacture HARD21, and no new economic
parameters are fitted in this intervention.
