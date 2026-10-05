# Triad relational state V2: preoutcome audit and blocker

Starting HEAD: `7e18a6a1176ce8d795b0aded0fb6ac760313de85`.

**V2 is blocked, not READY_NOT_EXECUTED.** Identification passed within the declared partial-linear scope. Exact inference certification is incomplete because the frozen temporal stress envelope omitted the required daily dependence. This is not an observed FWER violation, low-power finding, archive failure or V1 rescue.

## Estimand and learning law

At each fixed cohort and UTC decision clock, X contains an intercept and canonical own-leg 5-minute and 60-minute log changes, scaled by a fixed target prefix own-leg 60-minute RMS. Clock effects are absorbed by that clock's intercept. D averages the available canonical relational closure-change states within each target, using fixed accepted prefix relation RMS and clipping before projection. There is one equally weighted row per distinct target.

With Q=I−X X+, RD=QD and a=sqrt(mean RD²), the primary moment is mean[(RD/a)(Y_h−g_h(X))]. This identifies partial-linear incremental information relative to a **common coefficient span within each cohort and clock**. It is not conditional independence or a causal treatment effect. Arbitrary target-specific coefficients and nonlinear own-leg baselines are outside its claim.

The current predictor nuisance m uses only causally available predictors. It does not use Y or a future-selected subset. The outcome baseline g_h uses a fixed 90-day chronological rolling window, daily 00:00 UTC OLS updates in ten columns: intercept, two own-leg controls and seven clock dummies. Training requires at least 240 rows and rank 10; a full horizon must mature, followed by the 5-minute availability buffer and 240-minute purge, strictly before the update. The pseudoinverse cutoff is 1e-12. There is no regularization, random time cross-validation, hyperparameter search or fallback.

At a fixed clock, g_h lies in col(X), hence RDᵀg_h=0 for **any** finite learned coefficients, including their drift or estimation error. The same identity holds after each target omission. Eliding repeated g fitting in the synthetic worker is an exact score equivalence, not an oracle residual assumption. Current m was recomputed inside every started joint synthetic path. Complete stochastic certification, including this geometry, remains unachieved.

All 648 analytic control-only checks passed: stable, abrupt and gradual feature/control covariance changes; baseline and combined changes; positive and negative baselines; heterogeneous cohorts; horizon-dependent coefficients; and common-factor changes. Maximum absolute null moment: **2.1277665619772564e-14**. All 36 positive, negative and heterogeneous controls passed, with maximum error **9.853229343548264e-15**. All 12 chronological leakage checks passed; perturbing forbidden future labels changed earlier predictions by exactly zero. Maximum FWL discrepancy was 3.048736328348091e-14; direct OLS coefficient discrepancy was 4.388062268738017e-14.

## Archive, geometry and support

The preserved hash-verified archive contains 75 accepted FX identities and 21 currencies. All 107 canonical relations remain declared, with no response-based selection.

| Structural cohort | Relations | Distinct targets |
|---|---:|---:|
| G10 monetary | 56 | 23 |
| Managed extensions | 32 | 11 |
| Other extensions | 19 | 10 |

The four information horizons are **15, 30, 60 and 240 minutes**: 12 two-sided paid leaves. The original 210-day development calendar and fifteen 14-day calendar blocks are retained. Every timestamp-supported leaf has **148 valid days**, **15 supported blocks**, and temporal-third counts **48/50/50**.

The first three horizons retain 1,184 clocks per cohort. At 240 minutes, dropping the whole clock when any active target's required future path is missing excludes **3/3/4 clocks**, leaving **1,181/1,181/1,180**. There is no future-selected target subset, zero imputation or clock compression. The minimum matured rolling training counts are 11,385 for G10, 5,345 for managed and 4,957 for other extensions. Real development X/D numerical fits, real Y and real scores were not computed. Timestamp/count support is a necessary gate, not full numerical certification.

The frozen stability law requires the selected orientation in both fixed 105-day halves. Breadth requires every declared single-target omission to retain a valid projection and the same aggregate score orientation. A subset needs at least five rows, rank three and two residual degrees of freedom. No universal direction across cohorts, best-triad selection or free context/horizon choice is allowed.

## Required dependence envelope: failure

The preserved generic AR025/AR050 generator carries the **daily 12-leaf score vector** across days with rho 0.25/0.50 and a 128-day burn. The exact worker instead initializes its previous-return state anew on every day. Its causal features, overlapping labels and alternative innovations all lie within that independently drawn day. Current m is day-local; cross-day g estimation effects cancel exactly.

Conditional on the fixed prefix scales, masks and deterministic regime schedules, the worker therefore gives independent centered daily score vectors, with cross-day stochastic covariance zero. The persistent intraday case rho=0.5^(1/288) also stops at the day reset. It is **not equivalent to daily AR050**. No stronger-equivalence proof was prospectively frozen. The exact temporal-envelope coverage prerequisite is consequently unmet. The frozen plan was not repaired or expanded after execution, and no V3 was constructed.

All eight running workers were terminated through their owned execution sessions, each with exit code 130; a subsequent process inventory found zero remaining workers.

## Stochastic results: not certified

The frozen plan specified 6,144 trials for each of eleven null stress cases, each with four configurations: global null, G10 only, negative managed only, and heterogeneous G10/managed effects with the other cohort truly null. Null seed: 2026100522+1009×case. Common sign-bank seed: 2026100524, with 1,023 draws. Nominal family alpha remains 0.025; the FWER ceiling remains 0.05.

The gate required max(Wilson upper at z=3.5, exact Clopper–Pearson upper at alpha=0.05/88) ≤0.05, and a simultaneous complete-family support lower bound ≥0.95. These bounds were **not evaluated on partial runs**.

Power was prospectively specified at 2,048 trials for cases 0, 2, 7 and 10, using seed 2026100523+1009×case. Six localized positive/negative cohort alternatives and a heterogeneous alternative were planned on the grid 0/0.05/0.1/0.2/0.3/0.4/0.5/0.75/1, with Wilson uncertainty and an 80% lower-bound target. The standardized effect denotes the first future M5 innovation per current relational residual RMS, measured in fixed prefix own-leg 60-minute RMS units. It is not bps, profit or daily-score SD.

Cases 0–7 began but were interrupted; cases 8–10 and all power cases were not started. **Zero full stochastic cases completed.** Every global-null and partial-null FWER estimate, simultaneous bound, power curve and minimum detectable incremental effect is **unavailable**, not zero. Logged partial progress is not a certification denominator.

## Reporting corrections

Three reporting defects are explicitly preserved. The invariant JSON writer rejected a NumPy boolean after its numerical assertions passed; a serialization-only adapter saved the identical results, without changing the frozen code. The field `numerical_clock_failures` also includes 1,488 expected unavailable calendar clocks per trial; the known-mask contribution is separated without changing raw integers or support gates. The initial direct-signal report did not prove termination and made an unsupported causal attribution; a separate correction records verified session termination and zero remaining workers.

A computational scheduling amendment allowed concurrency before any full stochastic result. It preserved the estimator, code, seeds, trials, cutoffs and scientific envelope.

## Governance and unresolved limits

V1 remains `PREOUTCOME_BLOCKED_INCREMENTAL_ESTIMAND_NOT_IDENTIFIED_UNTESTED_NOT_NULL`, with blocker SHA256 `4095666954df6f34aaf8b4d1057a7e66a5b7126f093a18cef02abf108a8b9f9c`. V2 is a separate blocked exact law:

`PREOUTCOME_BLOCKED_EXACT_DEPENDENCE_ENVELOPE_INCOMPLETE_CALIBRATION_UNCERTIFIED_UNTESTED_NOT_NULL`.

Neither law may be rescued in this task. The broader relational source remains open. Protocol V2, its supersession, generic maxT framework and V6 remain unchanged. No source reranking occurred. This is development evidence, not confirmation.

The missing temporal stress, complete strong-FWER calibration, numerical support calibration, power and minimum detectable effect remain unresolved. Conditional mean-ignorability of retained future availability and real latency are unproven. Authentic current friction, slippage, conversion, margin and safe EUR200 economics are not certified; unknown cost is not zero. The machine-owned cTrader SCOPE_VIEW channel remains NOT_PROVEN, authentication readiness false, and depth a frozen unauthorized plan.

All task counters remain zero: real response openings, future real signed-response computations, broker contacts, historical requests, new acquisition, candidates and orders. Protected forward, confirmation and live trading remain closed. Runtime_V2 remains READ_ONLY.

The next boundary is independent governance of this exact blocker. There is no response, V2 rescue, V3, another source, depth probe, acquisition or trading authorized by this task.

All 65 history/governance regression tests passed. The exact-HEAD integrity validator checks historical bytes, SHA256 bindings, ancestry, saved arithmetic and zero response authority. It is not independent statistical certification.

## SHA256 bindings

- `TRIAD_V2_ESTIMAND_NUISANCE_DESIGN_V1.json`: `39ccec246ed346f86cfd0cfeb74b83d48ec86425b32fd6ba9529b43b67f4b771`
- `SEMANTIC_IDENTIFICATION_PLAN_V1.json`: `330113a0c3ad6249520a5228b3839ee11af9adeea0dfec3f8ca41648d8f1d341`
- `SEMANTIC_RAW_RESULT_V1.json`: `27474b0a330df0407a334c55c4e3affee78f5de7d1feb1e18cbea987eee712ab`
- `EXACT_STOCHASTIC_CERTIFICATION_PLAN_V1.json`: `a5d06569fb811db1173e4f9bc0e45e06deb0851f2dd104a5cc5cccf011a83739`
- `exact_geometry_worker_v1.cpp`: `b191ba890233bb3dd95c2bda927450685393dff0e690850abf6ff00b6a10d188`
- `stochastic_certification_driver_v1.py`: `41e134dcbd8694914697f939bc6f17e0633a6b02033a50dac7dfacad9c829ee3`
- `EXACT_DEPENDENCE_ENVELOPE_RAW_AUDIT_V1.json`: `b1dfc3418ab039983e14e8e5e94bf9656fd3477d1bac530f62466a149cf8becc`
- Final blocker: `085d8e010b4e02611e3e87797678cf093037b152ae06694cb70e6893b518647e`

## Completed checkpoint commits

- algebra_invariants: `e262f134ad0c1f403675f8dbd1319c880f7f1480`
- counter_label_audit: `45a28b3dd269513151dfe46cc745d155d0fbe035`
- dependence_coverage_raw: `88ab2f0ea6e7dee4da9cf67f56d252d955404c9e`
- estimand_design_freeze: `b17f83e56d4c07be2aa9b1929664667a53f81842`
- execution_scheduling: `7cda4db58a195b036c50136b4232efe91f01638a`
- pending_authority: `aafd52e51b1830d863d65b44bf0e468883bf41f2`
- semantic_pass: `73f67ce6be8478ed1d4429551797c9212aaae4a4`
- semantic_raw: `6d19ca2c964dcb59da22849a447b3e189afc9286`
- stochastic_plan_freeze: `8142eb5699d7a595727e9dd684816c64d3756ce7`
- timestamp_support_plan: `1296c0c62b5ffa7e61292ef4895cad19afde8504`
- timestamp_support_raw: `0870d13a3c4113652c7a7eeed537ef0826beef00`
- verified_interruption: `680f9f0ec5f0e9347877129df25e075d478a78db`
