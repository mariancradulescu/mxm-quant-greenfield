# MXM Quant Greenfield — Research Core V3 Project Contract V1

Status: **AUTHORITATIVE PROJECT OBJECTIVE AND HARD-CONSTRAINT ADDENDUM**  
Scope: Research Core V3 and all later certification / production work  
Relationship to V2: additive architectural law; does **not** rewrite or invalidate `RESEARCH_CONTRACT_V2.md`. Where both apply, preserve the stricter compatible interpretation.  
Purpose: define **what the project must ultimately achieve and what it must never violate**. This document is **not** a prescribed research workflow and does not dictate the order of operations.

## 1. Authority and Director autonomy

- LIVE GitHub is the authoritative durable state.
- Newer valid durable progress must always be preserved.
- Old chat text, screenshots, Work UI state, handoffs, memory, or unpersisted local work are not authoritative over LIVE GitHub.
- The Director owns research and engineering decisions inside the laws of this contract.
- The Director chooses the highest-information-gain scientifically justified continuation, including research order, evidence recovery, deterministic tooling, batching, mechanism exploration, frontier expansion, candidate design, portfolio architecture, and implementation strategy.
- The user defines the final objective and hard constraints; the user is not the routine GitHub operator and should not be asked to choose symbols, mechanisms, parameter regions, research branches, statistical methods, or implementation details that the Director can decide.
- Material progress is scientific/economic/production progress, not commit count, workflow count, epoch count, governance churn, or repeated infrastructure repair.
- Persist important durable progress often enough that a chat/session interruption does not erase meaningful work.
- Do not create governance/checkpoint churn for its own sake.

## 2. Final objective

Target broker and production environment:

- Pepperstone
- cTrader / cTrader Algo
- final production in cTrader Cloud
- one autonomous self-contained C#/.NET cBot

Initial strategy capital is **EUR200 exactly once**.

Capital is one continuous account path:

- no weekly reset
- no monthly reset
- no artificial restart of strategy equity for performance accounting

Primary objective:

> Maximize realizable, evidence-supported continuous-account compound equity growth under authentic Pepperstone/cTrader execution, capital, margin, cost, concurrency and survivability constraints.

Aggressive growth is allowed when authentic evidence supports it. The project is not required to optimize for conventional low volatility or arbitrary conservative return ceilings.

Forbidden shortcuts include:

- ignored transaction costs
- leverage fantasy
- hindsight
- future information
- retrospective favorable fills
- overfitting disguised as research
- ruin-prone sizing disguised as performance
- forcing trade frequency at the expense of expected value

## 3. Current broad research-universe law

The broad Pepperstone research frontier remains open beyond any current DEVELOPMENT subset.

Current accepted V3 frontier facts at the time this contract is introduced:

- eligible Pepperstone identities: 1576
- current primary DEVELOPMENT core: 145
- identities outside that core remain open unless valid evidence later changes their status

Laws:

- 145 is not the permanent research universe.
- The current gross-survivor symbol set is not the permanent research universe.
- Local null evidence does not close a mechanism family globally.
- LOW_POWER_INCONCLUSIVE remains open.
- DATA_INSUFFICIENT remains open.
- COST_UNRESOLVED remains open.
- Affordability is not evidence of edge.
- Frontier expansion should be driven by expected information gain, evidence quality, production relevance and data sufficiency rather than arbitrary quotas.

## 4. Research and evidence integrity

Research must remain causally live-equivalent.

At decision time T, only information genuinely available at or before T may affect:

- signal generation
- context/regime state
- candidate activation
- portfolio admission
- sizing
- execution
- exit / position management
- account state
- allocator decisions

Forbidden:

- future bars
- future normalization
- future regime knowledge
- later broker state
- hindsight parameter changes
- retrospective favorable execution
- synthetic missing bars used to manufacture continuity

Authentic time gaps must not be silently treated as adjacent market observations.

Discovery and confirmation remain separated. DEVELOPMENT evidence is never automatically confirmation.

Protected-forward evidence remains protected until a scientifically valid gate allows its use. Once consumed, protected evidence cannot be relabeled as untouched.

## 5. Candidate identity and no-rescue law

A candidate's economic identity includes every material rule that can change its trades, economics or risk, including where applicable:

- symbol / universe
- mechanism family
- context or regime
- signal definition
- entry logic
- timing
- direction
- parameters
- exit logic
- maximum hold
- in-position management
- execution assumptions
- cost treatment
- activation logic
- portfolio admission logic if candidate-specific

A material post-outcome semantic change creates a new candidate/version and must be evaluated under the appropriate DEVELOPMENT / freeze / confirmation rules.

No allocator, exit manager, risk engine, sizing rule or portfolio layer may be used retrospectively to cosmetically rescue a fundamentally negative-edge primitive under the same identity.

## 6. Entry architecture: specialization is allowed, not forced

The final system must **not assume that one universal entry rule is optimal for every symbol or mechanism**.

The research architecture must permit entry logic and parameters to differ when justified by evidence across dimensions such as:

- symbol
- asset class
- mechanism family
- context
- regime
- session
- volatility state
- market structure

However:

- symbol-specific entry logic is **permitted, not mandatory**;
- family-shared or cross-symbol shared entry logic is equally valid when it generalizes better;
- do not force every symbol to have a unique entry rule merely because symbols differ;
- do not create per-symbol threshold spam or micro-tuning without robust evidence;
- insufficient sample size must not be hidden by excessive specialization;
- specialization must earn its complexity through robust net economic improvement;
- pooling / partial pooling / shared parameterization may be scientifically preferable where evidence is weak;
- any symbol/family/context-specific entry rule must be causal, reproducible, hash-bound when frozen, and subject to multiplicity / dependence-aware evidence.

The Director decides the appropriate level of entry specialization.

## 7. Exit and position-management architecture

Entry edge, exit logic and in-position management are distinct economically material problems.

The Director may research whether a prospectively specified exit or position-management mechanism improves:

- realizable net edge
- robustness
- drawdown
- survival
- turnover
- capital efficiency
- opportunity reuse
- compound growth

Possible research dimensions include, without prescribing any of them:

- time / maximum-hold exits
- signal invalidation exits
- state/regime-dependent exits
- volatility-aware exits
- protective stops
- profit-realization rules
- trailing logic
- break-even logic
- partial exits
- scale-out
- opposite-signal handling
- portfolio-driven reduction or closure

These are research possibilities, not mandatory mechanisms.

Exit/position-management laws:

- no hindsight-best exit;
- no future extrema;
- no retrospective favorable stop/target ordering;
- intrabar claims require data resolution capable of supporting the claimed execution semantics;
- material exit changes create a new candidate/version;
- complexity must earn robust net economic value after authentic costs;
- exit management may improve a promising mechanism but must not be used to disguise a negative primitive as positive.

Scale-in, pyramiding, averaging-in and partial exits are separate economic mechanisms and require prospective validation before production inclusion.

## 8. Authentic broker friction and execution reality

Economic certification must reflect authentic Pepperstone/cTrader reality where applicable, including:

- historical bid
- historical ask
- spread at relevant event/execution time
- commission
- swap
- minimum executable volume
- volume step
- symbol-specific margin
- execution delay
- slippage
- sessions
- holidays / trading-state restrictions
- rejected-order reality
- account/symbol applicability
- currency conversion where material

Missing evidence must remain explicitly unresolved.

Forbidden:

- current spread substituted for historical spread
- one generic spread for all symbols
- invented bid/ask
- invented commission
- missing cost treated as zero
- generic market data represented as Pepperstone execution evidence
- gross response described as net edge

## 9. Candidate freeze and confirmation

Candidate freeze remains closed until the candidate satisfies the required evidence gates, including at minimum:

- correct causal timing
- exact required dependency continuity
- robust materially positive gross evidence
- authentic execution/friction evidence or a scientifically defensible certified bound
- meaningful positive net edge
- chronological stability
- adequate event/date support
- acceptable dependence/multiplicity-aware evidence

Frozen candidate identity must bind the material economic semantics and source evidence.

Confirmation must be genuinely disjoint and may not reuse DEVELOPMENT evidence as if untouched.

No retuning, semantic change, allocator change, exit redesign, or material risk-rule redesign may be smuggled into confirmation under the same frozen identity/version.

## 10. Dynamic candidate activation

A historically confirmed candidate need not be executed at every possible opportunity.

The final system may include prospectively validated candidate-activation logic using only causal current information.

Possible activation information may include:

- market/session state
- volatility
- regime/context
- current authentic execution costs
- broker trading state
- candidate-specific frozen activation rules

Laws:

- no hidden online parameter retuning;
- no retrospective regime relabeling;
- no future-return-dependent activation;
- material adaptive learning requires its own prospective validation;
- temporary inadmissibility does not erase the underlying confirmed candidate.

## 11. Dynamic executable universe

The final architecture must distinguish:

1. **research universe** — broad opportunity set used for discovery/confirmation;
2. **confirmed-edge universe** — candidates with accepted economic evidence;
3. **currently executable universe** — confirmed active opportunities that are feasible under current account/broker/portfolio state.

The currently executable universe may expand or contract as actual account state changes.

Activation into the executable universe may require:

- confirmed edge
- valid current activation state
- current broker tradability
- safe minimum volume
- sufficient free margin
- acceptable aggregate exposure
- acceptable correlation/common-factor exposure
- valid current execution/cost state

Affordability alone never establishes edge.

## 12. Dynamic portfolio allocator

A dynamic portfolio allocator is a required final-system capability once multiple confirmed opportunities exist.

Purpose:

> Among concurrently valid and executable positive-edge opportunities, decide which are admitted, rejected, deferred where economically defined, prioritized, and how scarce capital / margin / risk capacity is distributed.

The allocator does not create alpha and may not rescue negative-edge candidates.

The Director has autonomy to design and validate the allocator architecture. It may be ranking-based, rule-based, optimization-based, risk-budget based, marginal-growth based, state-machine based, or another scientifically justified design. No particular method is prescribed here.

The allocator may consider, if prospectively validated:

- current equity
- balance
- free margin
- used margin
- drawdown state
- candidate-specific expected net edge
- uncertainty
- authentic current execution costs
- minimum volume
- volume step
- symbol margin
- existing positions
- pending orders
- symbol exposure
- asset-class exposure
- directional exposure
- currency exposure
- correlation
- common-factor exposure
- causal volatility/regime state
- capital occupancy
- opportunity duration
- execution feasibility
- marginal portfolio risk
- marginal expected growth

Scarce-capital law:

- if the account cannot safely execute every valid opportunity, arbitrate; do not blindly execute all signals.

Correlation law:

- materially overlapping economic exposures must not be treated as independent merely because they come from different symbols or candidate IDs.

Family law:

- mechanism families may coexist when independently supported by evidence;
- family labels alone must not determine allocation weights.

Validation law:

- whole-account allocation must be evaluated on a continuous account path under concurrent opportunities, authentic margin and authentic execution;
- isolated strategy backtests may not simply be summed to claim portfolio performance;
- material allocator changes create a new system version.

## 13. Risk management

Risk management is mandatory in the final system.

Objective:

> Maximize realizable continuous-account compound growth while controlling catastrophic drawdown, margin failure, correlated concentration and risk of ruin under authentic broker constraints.

Aggressive is allowed. Uncontrolled is not.

Risk management must eventually cover, where relevant:

- per-position risk
- aggregate open risk
- equity state
- drawdown state
- free-margin reserve
- margin utilization
- minimum-volume feasibility
- symbol concentration
- direction concentration
- currency concentration
- asset-class concentration
- correlation/common-factor concentration
- concurrent opportunity interaction
- gap risk
- execution risk
- cost deterioration
- rejected-order reality
- risk-of-ruin / survival behavior
- recovery after drawdown

Hard laws:

- risk management cannot manufacture positive expected value from negative expected value;
- no uncontrolled full-Kelly;
- no martingale or loss-chasing merely because equity fell;
- no risk increase merely because the immediately preceding trade won;
- no forced minimum-volume trade when safe sizing requires less;
- correlated positions are not independent risk;
- margin affordability alone does not validate a trade;
- all risk decisions must be causal and live-replay reproducible.

The Director chooses the final risk architecture prospectively and may research aggressive risk levels when evidence supports them.

## 14. Dynamic scaling, de-scaling and compounding

Dynamic scale-up, de-scale and compounding are required final-system capabilities, but must not be prematurely optimized before confirmed economic edge exists.

Scale-up may occur only when prospectively validated and when account/broker/portfolio state permits.

Relevant state may include:

- equity
- free-margin reserve
- drawdown
- aggregate exposure
- common-factor/correlation exposure
- candidate activation
- execution/cost state
- broker feasibility

De-scale must be possible as equity, margin state, drawdown, correlation or execution conditions worsen.

Critical law:

> If broker minimum volume prevents sufficiently safe de-scaling, reject the trade rather than forcing minimum volume.

Recovery from drawdown may be gradual or hysteretic when prospectively justified.

Compounding must be part of the validated economic architecture, not bolted on after certification.

## 15. Portfolio interaction

Portfolio engineering occurs only after economically valid primitives/candidates exist.

Final portfolio logic must be able to account for:

- concurrent positions
- common factors
- correlation
- overlapping currency risk
- aggregate risk
- aggregate margin
- capital occupancy
- opportunity conflict
- opportunity priority

Portfolio engineering may improve whole-account deployment but cannot manufacture alpha from negative-edge primitives.

## 16. Continuous EUR200 live-like replay

After a confirmed executable candidate structure exists, the system must be evaluated on a continuous EUR200-equivalent account path with causal account state.

Replay must track at minimum:

- balance
- equity
- high-water mark
- drawdown
- used margin
- free margin
- open positions
- pending orders
- portfolio exposure
- executable universe
- candidate activation state
- orders
- fills
- bid/ask
- spread
- commission
- swap
- slippage
- delay
- sessions
- holidays
- gaps
- minimum volume
- volume step
- margin
- rejected orders
- concurrent opportunities

The final objective is whole-account realizable growth, not the arithmetic sum of isolated strategy returns.

## 17. Operational state and recovery

The final cTrader Cloud system must remain economically and operationally coherent across normal runtime interruptions and broker events.

It must have deterministic behavior for, where applicable:

- restart / redeployment
- reconnect
- positions already open at startup
- pending orders already present
- duplicate-order prevention
- rejected orders
- abnormal/partial execution where applicable
- market closed
- symbol trading-state changes
- stale/unavailable market state
- account equity / margin reconciliation
- candidate / allocator / portfolio state reconstruction
- safe fail-closed behavior when required state cannot be established

Recovery logic may preserve intended economic behavior but may not invent fills, duplicate exposure, silently reset strategy economics, or alter frozen candidate rules.

## 18. Final production architecture

Final production is one autonomous self-contained C#/.NET cBot in cTrader Cloud.

Conceptual responsibilities must exist even if implementation combines them internally:

- research/certification layer — discovers and certifies what has edge;
- signal/entry engine — where and when a valid opportunity exists;
- candidate activation engine — whether a confirmed candidate is currently active;
- executable-universe engine — what is feasible under current account/broker/portfolio state;
- portfolio allocator — which concurrent executable opportunities receive scarce capital/risk;
- risk/sizing engine — how much risk and executable volume;
- entry execution engine — realistic order submission/reconciliation;
- exit/position manager — how open positions are managed and exited;
- account/portfolio state engine — continuous balance/equity/drawdown/margin/exposure state;
- recovery/reconciliation engine — safe state reconstruction after interruptions.

This architecture is conceptual, not a mandate for separate classes/modules.

Production must not require:

- phone
- Pydroid
- local PC
- VPS
- ChatGPT/OpenAI runtime
- external Python
- browser
- required external HTTP service
- required external database

## 19. Historical / C# / live parity

Historical replay and final C# execution may differ mechanically only, never economically.

For identical causal fixtures they must agree on material behavior including:

- signal/opportunity
- candidate activation
- executable-universe membership
- portfolio admission/rejection
- allocation
- sizing
- entry timing
- exit timing
- position-management actions
- broker-volume normalization
- account state
- margin state
- portfolio state
- HARD21 state
- deterministic strategy state

Material mismatch is failure.

## 20. HARD21

HARD21 is a **final certification system constraint**, not a signal generator.

Required final condition:

- at least 21 actually executed entries per UTC ISO competition week in the certified production architecture

Forbidden:

- filler negative-EV trades
- threshold relaxation merely to hit frequency
- fake/unfilled/rejected intents counted as trades
- sacrificing edge quality solely to manufacture HARD21

Multiple independently positive-edge primitives may jointly satisfy HARD21.

## 21. Demo and live authorization

Shadow mode remains excluded.

Before live:

- run exactly one complete final demo week on the frozen production version;
- validate parity, orders, fills, costs, sizing, allocator behavior, account state, executable-universe behavior, scale-up/de-scale, margin and recovery behavior.

If demo evidence causes a material change to:

- signal logic
- candidate identity
- entry
- exit
- activation
- allocator
- sizing
- risk
- portfolio arbitration
- scaling/de-scaling
- executable-universe logic
- execution semantics

then the changed system is a new frozen version and requires a fresh complete demo week.

LIVE orders and competition start remain hard-blocked until explicit user authorization after an accepted final demo.

## 22. Compute and reasoning discipline

Use deterministic computation for large/repetitive loops.

Use direct GitHub for:

- reconciliation
- code/state inspection
- deterministic edits
- tests
- hashes
- packaging
- provenance
- persistence

Use higher-level AI reasoning for:

- research strategy
- hypothesis/mechanism design
- statistical design
- evidence interpretation
- information-gain decisions
- candidate certification
- allocator architecture
- risk architecture
- exit/position-management architecture
- production architecture

Do not use AI/provider calls per symbol, cell, event, horizon or quote window.

This is an efficiency principle, not a restriction on Director autonomy.

## 23. Current V3 durable checkpoint referenced by this contract

At the moment this contract is introduced, the independently verified durable V3 state is:

- research HEAD before this contract: `c2fe24e7dd0938603ad5fadcc5cc79651d38c483`
- main HEAD: `3be4365208a92277f58407457936af191bdf56b4`
- corrected DEVELOPMENT surface: 145 symbols / 7,975 cells
- corrected surface manifest SHA-256: `0ceb1f79080f8c9ef5cf6a13c0f56b279d02ffabc9644624f58230c705fcccbb`
- robust gross regions: 88 across 84 symbols
- region assessment SHA-256: `7ab0000e92bd39a28d3de3aafc328927eb25fdcf42e68240e31b1a800461026a`
- current friction-resolved regions: 0
- current frozen candidates: 0
- protected-forward opened: false

These are checkpoint facts, not permanent limits. Newer valid durable evidence supersedes them.

## 24. Amendments

This contract may receive future additive amendments when the user establishes a new durable objective or hard constraint, or when a proven scientific/production requirement must be preserved across sessions.

Amendments must:

- distinguish project law from tactical research choice;
- avoid prescribing research order unless a true dependency makes order scientifically mandatory;
- preserve valid prior evidence and provenance;
- never retroactively relabel contaminated evidence as independent confirmation.

## 25. Final law

The project must remain **goal-driven, evidence-driven and Director-autonomous**.

The contract defines the destination and non-negotiable scientific/production boundaries.

It does **not** prescribe the route.

The Director is expected to choose, test, reject, refine, expand and implement the most scientifically justified path toward the final objective while preserving causal validity, authentic broker reality, dependence-aware evidence, survival, provenance and production parity.
