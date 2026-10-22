# C# single-instance multi-symbol portfolio — functional DEVELOPMENT, not economic qualification

Date: 2026-10-22. Current integration target: `mxm-remediation-p0-p4-20261015-v1`.

## Change in existing product (not a parallel bot)
The existing `MxmReferenceProductBot.cs` is now **one serialized cTrader Robot instance** with an explicit comma-separated broker-symbol roster, separate six-closed-bar causal kernels for each symbol, and `MarketData.GetBars(TimeFrame,name).BarClosed` subscriptions. The old chart `OnBar` order path is inactive, preventing the same instance from placing both chart-based and portfolio-based orders.

The single order entry/exit path reads **the same broker EUR account** and all positions sharing the existing MXM label on every trade decision; it applies actual symbol-normalized quantity, estimated symbol margin, account-global position limit, free-margin reserve, and aggregate estimated stop-loss exposure. Existing labelled positions on an unconfigured symbol cause an immediate safe-stop on startup, not abandonment of broker-owned risk. All strategies cold-start after startup/restart; an existing broker position is never fabricated or reentered from synthetic local state.

A new pure C# sequencer blocks reentrant same-instance events and replay of duplicate/stale bar timestamps. It does **not** make account reads and market orders atomic across separate cBots. Portfolio bar callbacks are processed sequentially as received, not as a certified globally timestamp-sorted tick backtest. No cross-instrument historical broker-fill or mark-to-market equity parity has been proved.

## Fail-closed and operational scope
- Empty, duplicate, excessive (>16), unknown or unconfigured symbol roster => no bot trading; invalid timeframe / family / exit mode => safe stop.
- Default `EnableDemoTrading=false`; `Account.IsLive` is explicitly denied. Cloud activation is NOT performed by this change.
- Backtesting is simulated and does not count as actual fills. Do not deploy concurrent instances with this shared label. **This source cannot detect/prove that an independent Cloud instance has not already made an opposing decision**.
- All parameters (instrument selection, stops, margins, exit policy, etc.) are engineering parameters, not permanent OWNER demands.
- The synthetic two-symbol fixture checks chronological deduplication, no same-instance overlapping admission, independent kernels and shared EUR200 capital/stop-risk constraints. It is **not** an economic experiment, Pepperstone history, Cloud integration test, broker cost certificate or HARD21 demonstration.

## Economic state
Existing 28,212 BID/ASK quote events are DEVELOPMENT-exposed, cover no complete ISO UTC week, and yielded no qualified executable edge. The 3,355,389 M5 bars include fragmented spans with no broker BID/ASK fill certification. Nothing in this PR modifies previously opened outcomes, the V2 registry, C033 identity, OWNER1807, active authority, market data, protected confirmation windows or trading access.

**Disposition:** FUNCTIONAL ENGINEERING ADVANCE ONLY. NO QUALIFIED EDGE; HARD21 unproved; no LIVE orders; no cTrader Cloud activation. Next meaningful demonstration is single-account multi-instrument chronological replay with authenticated native quote costs and sufficient full-week coverage, followed by DEMO operational recovery proof with independent cTrader events and a documented one-instance deployment rule.
