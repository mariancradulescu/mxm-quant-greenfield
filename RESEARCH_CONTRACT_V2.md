# MXM QUANT GREENFIELD V2 — RESEARCH CONTRACT

Status: FROZEN ARCHITECTURAL LAW
Date frozen: 2026-09-17

## 1. Clean room
V2 is a true fresh algorithmic start. Do not inherit or reconstruct A110–A118, BNY, PF01/PF02, Production Convergence, legacy experts/allocator, Qualification Engine, Attack Engine, legacy signals/exits/thresholds, old handoffs/collectors/governance. Legacy may contribute only validated broker truth, competition truth, execution semantics actually verified, reusable data with provenance, and contamination/prior-attempt accounting. Candidate namespace begins V2-C001.

## 2. Competition and capital
Target: Pepperstone LIVE, Razor, cTrader, cTrader Cloud. Initial strategy capital is EUR200 exactly once. Capital is continuous and never resets weekly/monthly. Primary objectives are maximum realizable weekly final equity and maximum realizable monthly final equity. Hard constraint: at least 21 actually executed entry trades in every certified UTC ISO competition week. Rejected/unaffordable/unfilled intents count zero; exits do not add trade count.

Future decisions use the actual causal capital/free-margin state. Scaling/compounding is allowed only under a prospectively certified rule. Deposits and withdrawals are external cashflows, not profit/loss; after broker confirmation they affect future capital/equity/free margin/sizing. Track broker balance/equity separately from cashflow-neutral strategy NAV. Certification must probe economically meaningful capital states around EUR80, EUR200, EUR350, EUR1000, EUR5000.

## 3. Production boundary
Final production is a self-contained C#/.NET cBot running autonomously in cTrader Cloud. Production must not require a phone, Pydroid, local PC, VPS, ChatGPT/OpenAI runtime, external Python, browser, required external HTTP service, or required external database. Research may use offline Python/AI/tools. No LIVE orders and no competition START without explicit user authorization.

## 4. Historical-live parity
Certification must execute history incrementally as a causal state machine exactly as if time were flowing live. At historical time T only information available at T may be used. Process chronologically market, broker, account, portfolio, strategy, execution, and competition state. No future bars, future normalization, hindsight, retrospective fills, later broker state, or future regime knowledge.

Architecture is SHARED DETERMINISTIC ECONOMIC CORE + HISTORICAL REPLAY ADAPTER + CTRADER LIVE ADAPTER. Adapters may differ mechanically only. For identical causal fixtures exact replay and C# core must agree on opportunity/no-op, instrument, direction, timing, entry, exit, size, admission/rejection, capital/PnL/position/HARD21 state, and deterministic strategy state. Material mismatch is failure.

## 5. Discovery versus certification
Discovery is cheap, broad, causal, DEVELOPMENT-only, cache-reusing, generic, vectorized where valid, and uses frozen conservative coarse costs. Certification is expensive and deep: incremental exact replay, broker-realistic bid/ask/costs, commission, swap, slippage/delay/gaps, sessions/holidays, continuous capital, margin/free margin, concurrency, stress, protected validation, C# parity, Cloud readiness. Discovery precedes Certification.

## 6. Evaluator integrity gate
Before V2-C001 economic outcome, deterministic synthetic fixtures with manually known outputs must pass completed-bar causality, decision timing, next-valid entry, indexing, market-closed delay, long/short PnL, volume normalization, commission, spread, swap, currency conversion, hold termination, same-timestamp ordering, missing bars/session boundaries. Expected event counts, timestamps, costs, PnL and net results must match.

## 7. Broker semantics
Centralize semantics once and classify each VERIFIED, CONSERVATIVE_BOUND, or UNRESOLVED. Import only conclusively demonstrated legacy facts. Discovery may use a frozen conservative bound only when it cannot falsely promote a failing system. If sign depends materially on uncertainty, classify COST_OR_EXECUTION_UNRESOLVED/COST_UNRESOLVED. Exact truth is mandatory before Certification promotion.

## 8. Data and evidence
Use one DATA_MANIFEST containing instrument, resolution, interval, source, environment, hash, completeness, and causal/session/timezone semantics. Reuse clean legacy data only with valid provenance/hash; never copy strategy code merely to obtain data; cache once and reuse.

All pre-V2 historical data is DEVELOPMENT by default. Track 16 legacy economic DEVELOPMENT attempts plus all V2 attempts. D017 opened no economic outcome. Do not recycle failed exact legacy identities as fresh tests; an identity failure does not close an entire symbol/market/asset class/mechanism family.

Before V2 economics, freeze V2_PROTECTED_FORWARD_START. Protected outcomes remain hidden from hypothesis generation, parameter selection, candidate ranking and Discovery iteration until final validation. Once opened, evidence is permanently consumed.

## 9. Hypothesis space and search budget
Before economics, freeze broad finite HYPOTHESIS_SPACE_V1 spanning materially distinct mechanisms, asset classes, resolutions, horizons, session structures, cross-sectional/time-series structures, relative value, cross-market information, regime/context, and causal ML where justified. Do not anchor to FX-G8/H1. Proxy is not universe; tested identity is not exhausted market.

Freeze a finite V2 search budget before V2-C001 outcome, justified from effective hypothesis breadth, DEVELOPMENT evidence, parameter/ML/multiple-testing burden. Track 16 legacy attempts + every V2 identity. Never enlarge the budget merely because no winner appears.

## 10. Generic candidate engine
Use one generic declarative candidate engine and shared evaluator. Manifest fields include ID, mechanism, rationale, universe, data/resolution, causal availability, features, lookbacks, normalization/training, timing, direction, entry, exit, maximum hold, execution assumptions, filters, parameters, capital semantics, cost state, Cloud portability, no-rescue rule, specification hash, provenance. Material post-outcome semantic change creates a new candidate identity.

## 11. Discovery economics
Stage A tests primitive economic edge: events, gross result, conservative coarse net, cost burden, turnover, density, weekly distribution, hold/exposure, drawdown, market/session contribution. No sophisticated allocator or sizing rescue. Stage B only for Screen-A survivors: simple frozen EUR200 causal realization with continuous path, weekly/monthly final equity, occupancy, margin blockers, executed-trade distribution.

Historical costs use verified history where available, otherwise prospectively frozen conservative envelopes/scenarios. Gross-positive alone is insufficient. Sign-changing reasonable cost uncertainty => COST_UNRESOLVED.

## 12. Discovery waves
After hypothesis-space freeze select genuinely informative materially distinct candidates by orthogonality, shared-data efficiency and information value. No arbitrary candidate quota; no lookback grids, threshold spam, minor hold variants or cosmetic duplicates. Breadth precedes micro-tuning.

## 13. Required result reporting
Where applicable report event count, gross/coarse-net PnL and return, gross/net per event, cost burden, turnover, weekly events, active weeks, longest inactive gap, weekday/session distribution, hold duration, exposure, drawdown, symbol/direction/subperiod/regime contribution, EUR200 feasibility, cost confidence, data completeness, implementation validity. EUR200 realization additionally reports continuous capital, weekly/monthly final-equity distributions, capital occupancy, margin blockers, executed-trade distribution. Quantitative evidence first.

## 14. HARD21 and portfolio order
HARD21 is a system constraint, never a signal generator. No negative-EV filler, post-outcome threshold loosening, or fake frequency. Multiple positive-edge CORE primitives may jointly satisfy HARD21; measure natural opportunity/execution density early.

Required order: EDGE -> REALIZABILITY -> ROBUSTNESS -> PORTFOLIO INTERACTION -> SIZING/SCALING -> HARD21 ARCHITECTURE -> PROTECTED VALIDATION -> C# PARITY -> DEMO -> LIVE. Portfolio engineering cannot manufacture alpha from negative-edge primitives.

## 15. ML
ML is permitted but neither privileged nor automatically postponed. Require temporal training, no random temporal shuffle, no future normalization, frozen features/target/preprocessing/retraining schedule, purged/nested temporal procedures, attempt accounting, and Cloud-portable final representation. Complexity must earn economic value.

## 16. Acquisition and anti-loop law
One generic manifest-driven acquisition path: existing verified cache -> generic acquisition -> minimal generic extension -> user action only when unavoidable. The user is not tooling QA. Each autonomous run has one primary objective; one bounded side investigation only if a single material unknown blocks it. Unknowns that do not change decisions are marked UNKNOWN and work proceeds.

## 17. Economic result states
Use only: IMPLEMENTATION_INVALID, DATA_INSUFFICIENT, STRUCTURALLY_INFEASIBLE, GROSS_EDGE_FAIL, COARSE_NET_FAIL, COST_UNRESOLVED, DISCOVERY_SURVIVOR. Tool failure is not economic failure. A corrected rerun after proven implementation bug is not a new hypothesis.

## 18. Certification closure rule
Discovery survivor is not champion. Certification requires exact incremental replay, live-equivalent state semantics, exact costs/execution, continuous capital, margin/free margin, concurrency, stress, protected validation, C# deterministic-core parity. If exact replay cannot reproduce Discovery economics, candidate closes with no rescue under the same identity.

## 19. Bootstrap sequence
M0 clean repo + minimal skeleton; M1 bounded TRUTH_CAPSULE; M2 DATA_MANIFEST + central broker semantics + synthetic fixtures PASS; M3 generic Discovery engine/schema/hashing/ledger; M4 freeze HYPOTHESIS_SPACE_V1 + V2 search budget + Discovery cost model + V2_PROTECTED_FORWARD_START; M5 freeze first materially distinct wave before outcomes; M6 run Discovery Wave 01 immediately if data suffices, otherwise capture only minimum generic missing evidence.

## 20. Reporting law
At material checkpoints report engineering/methodological progress separately from economic/performance progress. Always report authoritative V2 HEAD, primary objective, V2 evaluated identities, legacy attempts=16, frozen V2 search budget, Discovery/Certification survivors, latest economic outcome, next economic action, user action required, and whether work since previous economic outcome was structural-only.
