# Portfolio observed stop and shared exit policy V1

Engineering continuation after PR137. No new market data, economic selection,
confirmation opening, strategy optimization, budget refund, or ledger identity.
Existing captured-component result and finite 216-leaf experiment remain historical.
No authenticated-source outcome has been evaluated with this extension.

The multi-instrument EUR200 replay previously omitted stops and supported only
ReverseOnly. `StopDistanceQuote` now optionally freezes an absolute quote-currency
stop distance from the modeled entry. Long triggers on BID <= stop; short on ASK
>= stop. A gap exits at the first observed liquidation quote plus the declared
adverse slippage, never at a fictitious guaranteed stop price. Stops run without
bar intents and clear any pending intent, preventing same-quote reentry. Each exit
books signed converted PnL, one exit commission, and releases modeled margin.
Already touched entry stops are refused. Existing marked stop exposure uses the
current liquidation side and loss conversion, rather than the original risk.
Legacy quotes with no stop distance retain the previous explicitly incomplete model.

`MxmExitPolicy` is compiled into both actual cTrader bot and portfolio replay.
It retains contiguous warm neutral exits, Horizon12 measured from the position's
entry time, and reversal precedence. Only reversal permits entry on the consumed
intent. Horizon/neutral exits return without same-intent reentry. Product order
permissions and broker-native stops are unchanged. Replay default ReverseOnly and
null stop distance preserve the historical economic path.

Validation: native CI compiles the actual `.algo`; executable C# fixtures exercise
long/short gap stops without fresh bar signals, stop/spread conflict, horizon age
including a nonzero entry-second offset, neutral exits, and forbidden same-intent
reentry. Python Decimal independently reconstructs every cash movement in the
synthetic two-symbol stop ledger: EUR200 -> EUR193.12, two entries/two exits,
EUR0 used margin. This number is an artificial adversarial fixture, not a return.
Existing legacy/captured-component parity checks remain required.

Limitations: no broker stop trigger method, ACK, execution depth, partial fill,
latency or inter-symbol arrival proof. Stops can lose beyond their level; modeled
stop risk is not a loss guarantee. No financing, historical margin tiers, complete
weeks, continuous live-account recovery or robust after-cost edge is proven.
The extension must be prospectively specified and independently reconciled before
any new historical economic evaluation; these fixtures open zero scientific trials.
