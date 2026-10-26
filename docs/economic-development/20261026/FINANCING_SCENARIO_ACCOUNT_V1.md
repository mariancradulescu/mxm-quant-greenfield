# Financing cashflows in the existing continuous C# account

Recovery started at official `5b034fb4998f9ec2e4b6978c35f3dc2902519b0a`. PR182/183 are terminal; no later official change or active/queued run was found. Open drafts PR8/104 target the historical R3 source, not a pending new official economic execution; PR1 is historical. Active authority remains `07d1ddbe0b83753bbf189770af1911623fef8d6f`, OWNER1807 `a830c132521bd4348454653f713e04f6107484fe`. Neither is changed.

## Functional change and purpose

The existing C# shared account explicitly excluded financing. An evaluation that crosses a financing boundary needs those cashflows in the same balance, free margin, equity and drawdown path. Add one opt-in `FinancingScenarioSha256` and typed `MxmFinancingCashflow`, already denominated in EUR. No second account, deposit, strategy, rate calculator or broker adapter is introduced.

Each booking identifies the current open instrument, position entry time, direction, exact units, accrual interval, booking time, signed EUR amount and fixed scenario hash. Future, empty, overlapping, repeated and mismatched periods fail. Bookings can debit or credit cash; severe debits halt the same account. They neither execute nor count entries, change units/margin, refresh quotes nor consume a signal. Shared-USD mode still requires valid fresh funded marks; EUR amounts are never converted twice.

`FINANCING` ledger rows retain the complete typed event. Same-code/source/settings recovery reconstructs cash from the initial EUR200 and every entry, exit and financing row, checks position lifecycle and accrual continuity anchors, and restores duplicate protection without refund. The mode/scenario cannot be switched at restore. The existing capsule's assembly-identity pin remains: this is not a migration of older assemblies' live state or native cTrader LocalStorage recovery.

## Scope of the evidence

Local .NET8 compilation with warnings as errors, actual execution, 98 financing assertions, two artificial long/short cash paths crossing an ISO week, two shared-FX paths and six fresh OS recovery processes passed. Every event cut yields the same full report. Independent Python Decimal reconstruction checks every supplied financing/cash step, liquidation equity and free margin; nine tamper controls reject refunds, altered/omitted accruals, overlap, position substitution, phantom entries, double FX and historical promotion. The original full account fixture and its ten cold process recoveries also passed, along with ten relevant preserved-evidence tests.

Local SDK CLI/MSBuild could not inspect process metadata in this Work host. Direct invocation of the SDK's actual C# compiler and .NET runtime performed the local checks; standard project build and broader integration remain subject to native GitHub CI. No local result is called a GitHub run. Existing gateway CI now requires the compiled expanded fixture plus independent financing checker. Original PR181 proof remains byte-exact and is evaluated separately from current implementation applicability.

## Scientific limits and source decision

Amounts are explicit **SCENARIO cashflows**, not observed historical Pepperstone swaps. A supplied hash labels the frozen scenario; admission/custody must separately bind it to the actual assumptions. This API cannot authenticate a rates table, infer an absent booking as zero, certify calendar completeness, translate an uncertain current snapshot into historical costs, or justify material post-outcome fee changes. It conservatively rejects bookings after the matching position has closed; delayed broker postings are not implemented.

No economic strategy is evaluated or reopened by this change. The negative/censored EURUSD-to-GBPUSD W37 model stays closed. Existing simultaneous authentic EURUSD/GBPUSD support covers W37 only; existing EURUSD W35 and W37 are separated by W36. Broad M5 archives do not supply complete bilateral prices or independent confirmation. A missing chronological week is a concrete source limitation before a meaningful multi-week continuous-account evaluation; another model on the same paired week would not remove it.

The next data action is a bounded extension of the existing Pepperstone VIEW collector for **EURUSD ISO2026-W36**, filling the interval between existing W35 and W37 without recollecting either. Selection is by chronological adjacency and existing authenticated identity, not returns. It stays before the protected cutoff and in exposed DEVELOPMENT; it cannot become independent confirmation. Its native transport, source commitment and preservation require their own finite installation and evidence; this financing change dispatches no acquisition. No new provider, order, Cloud activation, formal V2/C033 mutation, robust edge, HARD21 or native operational reception is claimed.
