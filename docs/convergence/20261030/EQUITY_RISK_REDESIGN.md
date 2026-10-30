# Integrated risk redesign: OWNER authority, equity-relative capital and genuine economic sensitivity

**30 October 2026. Continuing OWNER B–E mandate after PR #274. Not a new project.**

## Authority correction and safe product boundary

OWNER has **not** endorsed the historical exact numerical 80 EUR ticket margin, 120 EUR fixed free margin, 2 EUR stop+friction ticket allowance, nor 1% stop-risk budget as permanent OWNER numeric limits. Those are **previously engineered DIRECTOR settings**, regardless of identifiers such as `MxmOwnerEntryEnvelope`, `FUNDED_OWNER_LIMITS`, or `REJECT_OWNER_...` in C# and Python. OWNER's binding strategic requirements include one initial continuous EUR200 account, robust after-cost advantage, weekly/monthly equity growth targets, actual systemic HARD21, native cTrader Cloud, no use of unauthorized sources and no operations LIVE/DEMO/Cloud or operational risk changes without distinct approval.

Existing operational cBot code, the active 80/120/2/1% rules, fail-closed order recovery, source/custody gates and all prior economic results remain **byte-for-byte untouched**. A research finding does not authorize new live account thresholds. Future release needs the exact OWNER decision on operational policy, independent risk/economic qualification and native Cloud reception. The research should not be stopped merely because those future decisions are not yet available.

## Material economic question

Can fixed absolute, EUR200-start risk allocation harm compounding or suppress otherwise genuine opportunities as equity changes? How do equity-relative margins, free reserves, risk budgets and broker minimum tickets respond to losing and winning trades, commissions, stop-only losses and gap shocks? Does changing risk policy create or simply conceal losses? These are questions, not established conclusions.

Evaluate existing genuine funded original run `41005510200` (head `7fc1926d6a9e9ed8d1e85bb87d337fecd3309721`, artifact `12954864256`) as **one separate exposed DEVELOPMENT risk-sensitivity source**. Only its already-entered original C# ENTRY/EXIT pairs and original entry quote metadata are read after exact cryptographic custody and independent prior-account reconciliation. Do **not** reevaluate the frozen model, reprice market bars, reopen OHLC, reproduce previous economic outcomes, fabricate additional entry opportunities or show private single trades. Original USD EUR conversion, minimum executable units, modeled margin, entry+exit commission and stop-risk estimates are retained.

The research-only C# console utility in `research_core_v4/laboratory/csharp/risk_research/` shares neither compilation nor runtime with the cTrader Robot. It consumes a strictly chronological and mutually non-overlapping tape of original complete entries, each with margin, stop estimate, cost and gross outcome. A rejected trade is omitted; its future strategy decisions **are not recomputed**. Subsequent decisions use *only* the synthetic continuously updated cash before each candidate entry, no future return/price lookahead in **risk admission**. Historical execution outcomes are frozen and therefore counterfactual risk paths are *conditional tape replay*, **not** valid backtests of new policies. Causal broker minimum-volume lattice is unchanged, no fractional ticket rescue is inferred. For a real portfolio the same policy must be evaluated on all potential entry signals and quote paths, including any gaps, stopouts and new orders.

Predeclared numerical **offline sensitivity hypotheses** (not optimized; no commercial permission):

| Research policy | Margin / current free | Minimum post-entry free | Stop+declared friction/current equity | Historic fixed caps |
|---|---:|---:|---:|---|
| HISTORICAL_DIRECTOR_CONFIG | 40% | >= EUR120 | 1% and <= EUR2 | Ticket <= EUR80 |
| ADAPTIVE_EQUITY_CONSERVATIVE | 25% | >=55% of current equity | 0.5% | None |
| ADAPTIVE_EQUITY_BALANCED | 60% | >=25% of current equity | 2% | None |

Each reserves the original **EUR0.40 round-trip research friction estimate** at entry for stop-risk budgeting. The alternative values are fixed research comparisons, not retrospectively selected profitable configurations. True current broker margin and execution costs, per-position correlated loss, actual stop/Cloud orders, event-order valuation and external account actors remain unproven.

For each candidate risk policy, run four **independent conditional EUR200 paths** with no deposits or resets:
1. `RECORDED_CSHARP` = exact original booked gross PnL and booked fees for accepted historical trades only.
2. `DOUBLE_COMMISSION` = same original gross, 2x booked commission, no claim of broker historical cost bounds.
3. `ALL_ESTIMATED_STOPS` = each admitted trade modeled gross = negative its original entry stop-risk estimate; booking fees separately.
4. `ALL_STOP_GAP_2X` = every admitted trade modeled gross = negative twice the entry stop-risk estimate and double commission, a deliberately adverse stress—not a true market upper bound.

Report accepted/omitted historical entries, cash, close-to-close drawdown, minimum close equity, pre-trade/post-entry free margin, and any model insolvency/reserve breaches. These stress outcomes are **not statistical risk-of-ruin probabilities**. With 56 previously exposed, dependent, already-selected closed episodes, a defensible real probability of ruin cannot be estimated. Intrabar mark, actual margin call, spread variability, financing and past/live fees remain unresolved. A positive result from rejecting historical losing trades would be an ex-post selection artifact, not independent alpha or permissible deployment evidence.

The protected workflow compiles the standalone C# study, checks synthetic economics/guards on PR, then on **one reviewed official push** downloads the previously verified original encrypted artifact. It cryptographically cold-checks the original journals and the original independent funded C# cash ledger; the historical DIRECTOR configuration must reproduce the **exact original EUR200 ending cash** on the full original accepted tape, or the entire run fails closed. It publishes public aggregate scenario results, and encrypts detailed analysis to the existing OWNER custody recipient; no new original market acquisition, source-provider API, broker request, strategy evaluation, Cloud activation or order. It does not change research partition status.

## Decision logic, subject to actual evidence

- If the unchanged historical policy does **not** reproduce original final cash and accepted count, treat the study as invalid and correct the data/estimate mismatch; do not hide the gap behind arbitrary tolerance.
- If the adaptive risk alternatives merely change the subset of an already negative signal, do not claim positive expected NET. If their money-management metrics improve conditionally, retain as exploratory only, not a reason to change operational settings.
- If stress scenarios show severe drawdown or capital exhaustion, prioritize capital survival / gap-aware exposure accounting and broker minimum-ticket feasibility, without pretending every trade must hit its stop in real markets.
- If no policy admits broker minimum-volume opportunities through declining equity, explicitly report the non-scalability at that equity; the starting EUR200 is not a fixed target equity and cannot be reset.
- Subsequent genuine product studies need new economically justified predictive mechanisms with authentic time-ordered source, actual chronological decisions, complete account-level cost/risk, equity-dependent sizing, and enough valid opportunities for **systemic** HARD21; no post-hoc unqualified positive subset, no pressure to trade merely to satisfy count.

Native cTrader Cloud cannot be declared safe for new exposure while the unknown in-flight request recovery dependency remains unresolved. Observation-only safety and all existing prohibitions remain intact.
