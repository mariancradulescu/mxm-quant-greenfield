# OWNER reorientation — broker-native external cashflows (29 October 2026)

## Decision and scope

The final product remains ONE self-contained C# cBot for cTrader Cloud, EUR
Pepperstone Europe Razor, continuously funded from a single initial EUR200
starting point, adaptable to later OWNER-authorized deposits and withdrawals.
Net economic performance, weekly/monthly end equity and HARD21 still require
causal, broker-realistic certification. This change neither selects an unproven
strategy nor revises risk ceilings. No LIVE/DEMO order, Cloud instance,
credential, external service, protected research source or frozen experiment is
accessed or changed.

**PĂSTREAZĂ**: original broker deal inventory, durable Desktop checkpoint,
ledger, risk/order protections, authentic research/economic account.
**REPROIECTEAZĂ**: the assumption that local storage is the only native source
of account history. Cloud LocalStorage is not durable across starts. For cash
flows, cTrader Algo separately documents an account-native Transactions
collection (API since 5.2) with Id, Type, Amount, Time and Balance. The native
read-only adapter now ingests these original account transaction observations
without LocalStorage, in the SAME .algo Robot, including ObservationOnly mode.
This is a real broker-native data seam, not a second robot or replacement
trading path.

The shared deterministic MxmBrokerCashflowInventory records EUR deposit and
withdrawal facts, isolates account scope, deduplicates by transaction ID,
refuses conflicting copies, invalid types/clock/currency/amount, orders facts
by source time and creates an account-scoped digest. The reported observed
deposits/withdrawals and net external flow are NEVER classified as trading
returns. Native collection reads detect count changes and fail as UNAVAILABLE,
not as zero flow. The synthetic fixture covers duplication/order invariance,
account isolation, invalid observations, direction of signed raw amounts and
lack of certification or permission. Existing protected gateway CI additionally
executes the fixture and the native .algo compilation gate remains unchanged.

## Critical non-claims

The Transactions API documentation does not itself prove collection depth,
historical completeness, snapshots' atomicity, exact brokerage reception or
a trustworthy original EUR200 anchor. The current code intentionally marks
FullHistoryCoverageProven, OriginalCapitalAnchorProven and
CashflowNeutralStrategyNavProven FALSE. The current balance/equity is not
retrospectively transformed into strategy NAV from a potentially incomplete
transaction collection. No certified weekly/monthly results are produced here.

This fixes one architecture-level *information access* prerequisite (a
storage-independent broker-cashflow source). It does NOT repair the lost
before-send intent after Cloud restart, the possible late broker order after
a negative-looking history read, incomplete broker opening deals, stop
protection, native crash recovery, actual realized costs, HARD21 or NET edge.
Cloud entry stays refused. Current engineering evidence is not native Cloud
reception or economic evidence.

## Native technical dependency and next boundary

Official documentation:
- https://help.ctrader.com/ctrader-algo/references/Account/Transactions/Transactions/
- https://help.ctrader.com/ctrader-algo/references/Account/Transactions/Transaction/
- https://help.ctrader.com/ctrader-algo/references/Account/Transactions/TransactionType/
- https://help.ctrader.com/ctrader-algo/references/Localstorage/LocalStorage/SetString/
- https://help.ctrader.com/ctrader-algo/documentation/cbots/cloud-requirements/

The SDK-package compilation of these members MUST succeed in protected CI.
A genuine native, order-free instance would still be needed to establish what
transaction history Pepperstone exposes to this cBot and whether a complete
funding anchor is available. OWNER's current no-Cloud-start rule remains.
Even perfect cashflow history alone cannot establish a broker-side idempotent
entry protocol or safely authorize order retry. The next architecture decision
must specifically close the unknown-before-send / late-acknowledgement gap,
or preserve fail-closed behavior and report that the Cloud execution target is
not yet operationally receivable.

No new economic result, capital reset, re-tuning, PR-count success metric,
or risk-policy change is claimed.
