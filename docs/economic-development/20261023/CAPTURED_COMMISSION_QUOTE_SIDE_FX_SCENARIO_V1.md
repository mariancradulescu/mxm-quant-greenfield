# Captured commission components and quote-side USD/EUR conversion

OWNER B–E continuation, 23 October 2026. GitHub recovered at `e86508a6dc97d6f96d6be796d4995d997d730be2`, protected `39901849315` SUCCESS. Existing source, original custody and DEVELOPMENT exposure only.

## Material economic limitation
The original shared EUR200 C# replay used EUR0.10 commission per side and a fixed EUR-per-USD conversion of 1/1.10. Captured symbol specifications were authenticated in PR #134 but had not entered the modeled ledger. A constant symmetric conversion also treats USD gains and losses identically even though the original EURUSD BID/ASK spread offers different conversion sides.

## One prospective component scenario
The machine-readable `CAPTURED_COMPONENT_SCENARIO_V1.json` fixes one additional valuation alternative before its protected native result: same exact quote bytes, same Adaptive signal and ReverseOnly exits, same causal later-quote routing, same 1000 units, EUR50 assumed margin, slippage and estimated risk parameters. No parameter selection or new signal family. Each alternative starts with EUR200 once and runs continuously; cash is never reset within the path and alternatives are not combined into a portfolio return.

`MxmEurUsdCapturedCosts` requires explicit raw volume and fee fields. Check current-snapshot volume bounds and step; compute each entry and exit's commission from its precise native rate/type and minimum. USD-per-million uses modeled EUR turnover converted at its modeled execution price; USD-per-lot uses captured lot size; percentage rates remain percent. USD fees are funded by selling EUR at BID. An explicit EUR minimum is already in EUR and must not be converted again. Unknown/minimum-currency/lot semantics cannot silently fall back to zero or the old fixed fee.

For modeled realized PnL and terminal liquidation marks, positive USD is exchanged for EUR at ASK; a negative USD liability is funded at BID. Both conversion quotes must be the same accepted causal atomic snapshot. This is a declared executable-side scenario, **not the broker's actual conversion algorithm or debit**. The original fixed-term result remains a separate baseline; there is no retrospective change of its meaning.

The independent Python Decimal verifier reconstructs source quote groups, interprets raw snapshot fee units separately, recomputes every trade fee, signed gross PnL and continuous cash, then terminal equity/margin. It checks original quote SHA and captured term SHA and rejects fee, PnL, equity and snapshot changes. Actual C# synthetic fixtures include gains versus losses, USD-per-lot versus turnover fees, percent scaling, EUR minima, invalid volumes and a losing position mark. An additional artificial native-envelope stream forces C# entries/exits and is reconciled independently without credentials. Existing actual cTrader `.algo` and native controls remain required.

## Evidence boundaries
Captured metadata is from 21 October; quotes cover four hours on 9 September. Do **not** backdate those fees or volume rules. Broker money rounding, conversion fees, deposit-currency/account terms, financing, real liquidity, dynamic margin, actual stop execution and recoverability remain unresolved. The scenario therefore reports **captured cost components**, not full NET after every cost. Public receipt can show bounded alternative cash/equity/counts; detailed metadata and ledgers remain in the existing encrypted result.

No newly selected strategy, independent confirmation, V2/C033 identity/refund, OWNER checkpoint or active-authority mutation. No broker API request, order or Cloud activation. No positive-edge, HARD21 or final product reception claim is permitted from this component scenario, even if its displayed account value exceeds the baseline.

Protocol references: [ProtoOASymbol and commission types](https://help.ctrader.com/open-api/model-messages/#protooasymbol). Numeric scaling follows explicit protocol fields; broker-specific historical billing remains unverified.
