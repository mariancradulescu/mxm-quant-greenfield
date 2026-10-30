# MXM B–E — original-derived H1 economic capacity ceiling (2026-10-30)

## Decision / purpose

**RESEARCH CAPACITY LIMIT — NOT A NEW STRATEGY, NOT AN ALPHA CLAIM, NOT A TRADING RELEASE.** After the closed-negative #283/#284 studies, stop inventing successive rules against the same eight Forex hours. Instead test the necessary *amplitude and frequency capacity* of the exact previously authenticated annual historical tape, before consuming additional capital-model or Cloud development work.

This retrospective bound deliberately gives an impossible advantage to a hypothetical oracle: it sees the **future** and selects the optimal *pair, direction and number of episodes* subject to one nonoverlapping one-hour opportunity at most per UTC hour. No real causal model can do better within these exact options at the same fixed per-entry fee (and any extra execution/margin constraints only lower achievable results). This is not a tradable backtest, historical brokerage performance, broker feasibility proof or strategy promotion.

## Source / computation / reproducibility

- Private input: OWNER existing PRIMARY145_NATIVE_H1_CSHARP_INPUT_PRIVATE.json, SHA256 **7157db48811ed1f1e4583ab567c6e04c876a4c4738c4bd242f182632fff54ebb**, previously authenticated from two PRIMARY145 original Pepperstone M5 ZIP archives SHA256 **09d999a595436de73c5edbb3d4a84002dc8b8779dc94393473d43afe1c3d9259** and **37a47cb9ff8bc9cce50aee830c1bd286b9db359df1200d4e4b9a0ce35f8fd12e**.
- Input has 32,607 genuine complete-H1 source events and separate future M5 open-price lookups. Source original/next-price observations are not published. These eight pre-existing identity-selected Forex instruments are **not** an outcome-selected winning cohort, and **not** the authorized full Pepperstone universe.
- Original, frozen-before-outcome executed script local SHA256 **ef320e0298689bce30eb073e350be80d38cb35f7f00b9ebea66e1c11262b8aaf**; repo Git blob **5a520349bf86f094268ec8a1256e17e68ab51539**, verified byte-for-byte identical to the executed file. The source-blind selftest passed before first input evaluation. Script: research_core_v4/laboratory/h1_hindsight_capacity_oracle_20261030.py.
- Input timeline is 35 complete weeks, 2025-W40 to 2026-W22. Fixed slots: each weekday hour **07 through 15 inclusive UTC**, at most one nonoverlapping modeled next-hour position per slot; entry at original M5 open **hour end +5 minutes**, exit at **hour end +60 minutes**. All eight fixed symbols have observed future settlement for 1,557 slots (12,456 instrument-slot outcomes); 18 slots fall outside actual observed calendar support, not forward-filled.
- At each slot, impossible oracle gross amplitude is maximum absolute signed percentage move in **bps** of the eight instruments. At any fixed hypothetical round-trip friction c bps, sort slot gross amplitudes descending and choose the **maximum net sum over all portfolio counts k >= 21**. Weekly ISO UTC results count 21 *hypothetical* completed episodes, never broker fills. No position-size, stop-out, conversion, swap, actual bid/ask, spread, commission or price impact; scenario cost is not a Pepperstone observation.
- All 35 original-derived week-level numeric outcomes and summary assertions are in docs/economic-development/20261030/H1_ECONOMIC_CAPACITY_ORACLE_PUBLIC.json; the full, more detailed local public receipt was independently hashed to SHA256 **ea5ab49ab37fb60acce2331d24ae8b5a17a57b2bc2e1d30c51d99f1fea65660b** and remains available from the owner session. The repo retains no raw series, keys, per-slot prices, prospective position selections or private episode ledger.

## Actual upper-envelope result (costs purely hypothetical)

| Hypothetical round-trip cost per episode | Weeks with >=21 *individually* cost-positive hindsight slots | Weeks with positive optimized hindsight net after >=21 entries | Sum of optimized per-week hindsight bps envelopes |
| --- | ---: | ---: | ---: |
| 0 bps | 35/35 | 35/35 | +22,855.78353 |
| 2 bps | 35/35 | 35/35 | +19,741.94883 |
| 5 bps | 35/35 | 35/35 | +15,157.03704 |
| 10 bps | 33/35 | 35/35 | +8,740.23249 |
| 20 bps | 1/35 | 19/35 | +675.32410 |
| 40 bps | 0/35 | 0/35 | −14,024.67590 |

A positive hindsight upper bound is *not* a promising backtest. It requires knowing outcomes in advance. The sums are across different percentage-return tickets and weeks; they are **not** a EUR200 funded-equity trajectory.

Independently recalculated **weekly highest permissible break-even friction** for positive net with at least 21 episodes: the mean of the **21 largest** weekly absolute next-hour movements, because the top-k mean cannot increase for k >= 21. Across 35 weeks its **minimum = 14.2148558661 bps** (2025-W52), **median = 20.4828743745 bps**, **maximum = 33.1050632715 bps**. Even an impossible perfect predictor therefore cannot make every observed week net positive if every transaction incurs >=14.2148558661 bps for this exact one-hour, eight-market setting. At 20 bps, **16/35 weeks** cannot be positive even under oracle knowledge; at 40 bps, **35/35** cannot. This does **not** prove economic impossibility for other instruments/horizons, variable broker costs, lower frequency, longer holds or real portfolio construction.

## Integrated B–E next decision

**Do not retune, invert or relaunch any closed #278/#282/#283/#284 model, and do not mistake oracle selection for predictive research.** The result makes a further eight-Forex, one-hour high-friction model sweep low-value. Higher-value economic work should seek a **prospectively chosen** class/time-horizon where source-backed likely move sizes materially exceed **authentic symbol-specific** effective entry/exit costs, minimum volume/margin and stop-risk on a single continuous EUR200 account. Use the already authenticated annual 145 and existing 13-week/1,576 width corpora where genuinely available; additional read-only broker capture only when it answers this economic feasibility question. Verify actual *net* predictive improvement in distinct temporal blocks before investing in native C# integration.

For operational B–E: retain one C# product, fail-closed broker ambiguity recovery, protected confirmation, Cloud safeguards, and the true 21 broker-confirmed executions per ISO week requirement. This capacity screen does not change any trading file, cBot parameter, market source authority, risk control or broker/Cloud state. **ZERO LIVE/DEMO orders; ZERO Cloud activations.** It does not resolve broker idempotency or cTrader Cloud persistence qualification.

This is a **single bounded economic falsification/cost calibration** and closure of the narrow hourly source geometry under high assumed friction; not an autonomous loop of tests or an infrastructure roadmap.
