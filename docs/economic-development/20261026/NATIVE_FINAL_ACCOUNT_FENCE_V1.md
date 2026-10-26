# Native cTrader final account-state fence — 26 October 2026

Continuation of B–E from official `893512bf7cf7ce1193765fb94f2e9d73cc6ec831`, after PR198–199. No restart or economic rerun.

## Reproduced code gap

The real `MxmReferenceProductBot` verifies the actual EUR account, full broker book, margin, estimated stop risk, two-sided commission and OWNER 80/120/2 ceilings before entry. PR199 rechecks commission/FX near order submission, but other estimates were taken earlier after the durable checkpoint. A later reduction in `Account.Equity` or `Account.FreeMargin`, increase in `Symbol.GetEstimatedMargin` or `Symbol.AmountRisked`, or change in an existing position stop/volume/other-symbol quote can invalidate earlier admission without changing the proposed symbol's BID/ASK or open position IDs.

## Integration

A pure C# `MxmNativeFinalAccountFence` checks strict monotonic re-admission immediately before the durable SUBMITTED marker: observed equity and free margin must not decrease, and estimated proposed margin and stop risk must not increase. It rejects missing, negative, zero/invalid account snapshots. The native product stores the original scalar account/fee/risk inputs (in one shared account), captures a typed identity/geometry/quote snapshot for all existing MXM positions before risk computation, verifies it after risk computation and again near submission, and recomputes the proposed `GetEstimatedMargin` and `AmountRisked` near submission. Any discrepancy is a hold, never an automatic retry or alternative ticket.

The original `MxmCapitalAdmission`, `MxmOwnerEntryEnvelope`, `MxmStopRiskAdmission`, `MxmNativeCommission.StillCovered`, broker intent lease, broker book identity, pending-order zero check and durable checkpoint continue as-is. The new monotonic requirement is **more restrictive** than reapplying a weaker fraction to a deteriorated account. It does not change exits, position cleanup or replay accounting.

## Limits and tests

The final check uses sampled, non-atomic native cTrader observations; broker state may still move between the check, durable MarkSubmitted and broker response. Position changes in the gap are not a distributed inter-robot lock. No broker stop gap, future FX, commission charge or historical broker fill is certified. Existing risks remain explicitly unproven: native Desktop callbacks and storage recovery, HARD21, robust after-cost edge, continuous authentic EUR200 funding.

The existing artificial multi-symbol C# fixture tests equality, improved capital, deteriorating free margin/equity, increased margin/risk, invalid/null snapshots and conservative rejection even if a changed account might still pass a weaker percent. CI compiles the actual net6 cBot and verifies that all three identity/finality checks precede `ExecuteMarketOrder`. No new Pepperstone source, provider, model trial, encrypted original, protected environment, LIVE/DEMO order or Cloud activation. Historical evidence and rejected hypotheses remain frozen. Further economic work requires a distinct prospectively admitted mechanism and real funding/cost/source support, not repeated artificial matrices.
