# TRIAD V4 exact numerical gate: BLOCKED

Starting LIVE HEAD: `e9a27a93f3e06cf30df3c38178e0443a3bb8f491`. Blocker checkpoint: `398cec8cb2fa28ecc4d2d85964e0bbb613dec4ed`. Final report commit and final LIVE branch identity are reported separately; the report does not embed its own Git hash.

Classification: `PREOUTCOME_BLOCKED_CANONICAL_PROJECTION_KERNEL_NOT_EQUIVALENT_UNCERTIFIED_UNTESTED_NOT_NULL`.

The complete frozen fixture gate failed. No kernel repair, new method, tolerance change, V5, actual predictor audit, daily-dependence architecture, Monte Carlo or market response followed the failure.

## Preservation and interpretation

All 64 inherited file SHA256 bindings were reverified after the blocker. GitHub starting-to-blocker comparison contains only additions under triad_v4 and the new V4 blocker; V1/V2/V3, protocol/supersession and selection V6 are unchanged.

- V1: `PREOUTCOME_BLOCKED_INCREMENTAL_ESTIMAND_NOT_IDENTIFIED_UNTESTED_NOT_NULL`; blocker SHA256 `4095666954df6f34aaf8b4d1057a7e66a5b7126f093a18cef02abf108a8b9f9c`.
- V2: `PREOUTCOME_BLOCKED_EXACT_DEPENDENCE_ENVELOPE_INCOMPLETE_CALIBRATION_UNCERTIFIED_UNTESTED_NOT_NULL`; blocker SHA256 `085d8e010b4e02611e3e87797678cf093037b152ae06694cb70e6893b518647e`.
- V3: `PREOUTCOME_BLOCKED_INHERITED_CURRENT_PROJECTION_ADAPTER_NOT_EQUIVALENT_UNCERTIFIED_UNTESTED_NOT_NULL`; blocker SHA256 `1c69c85fcda532e4600dec2f7cdbe1af141364bd84341bd8e130d865f970bad6`.

V4 is a separate prospective implementation/certification successor. Mathematical estimand preservation is distinct from numerical implementation equivalence: V2 partial-linear estimand, three controls, rolling matured/purged nuisance OLS, cohorts, horizons, two fixed halves and every single-target leave-out gate remain hash-bound and unchanged. V2 estimand-design SHA256: `39ccec246ed346f86cfd0cfeb74b83d48ec86425b32fd6ba9529b43b67f4b771`. Accepted archive ledger, 107-relation inventory and timestamp geometry remain immutable; no new archive response was read.

## Exact kernel and reference law

Finite binary64 X/D, exactly three controls; column RMS strictly >1e-12; normalize X by column RMS. Singular-value rank uses absolute >1e-12, requires rank 3 and n>=5. Pseudoinverse uses relative cutoff >1e-12*sigma_max. RD=D-Z*beta; max(abs(Z.T*RD)) must be <1e-9*max(1,norm(D)); RMS must be >=1e-10; normalize by RMS; no clipping.

Standalone C++17 one-sided Jacobi SVD rotates B=Z and V=I directly. Pair order (0,1),(0,2),(1,2); maximum 100 sweeps; convergence |dot(Bp,Bq)|<=8*IEEE binary64 epsilon*norm(Bp)*norm(Bq), checked after each complete sweep; overflow-safe tau rotation. Stable descending singular-value sort; largest absolute B component (first row on tie) positive sign. Nonconvergence fails closed as NUMERICAL_SUPPORT_FAILURE. No Gram inverse, determinant rank or normal-equation solve.

Compiler: g++ Ubuntu 13.3.0-6ubuntu2~24.04, version 13.3.0; flags `-O3 -std=c++17 -Wall -Wextra -ffp-contract=off`; no fast-math. Canonical Python uses NumPy 2.3.5; full NumPy build/config and compiler executable digest are frozen in TOOLCHAIN_BINDING_V1.json.

Projection kernel SHA256: `6f58d7c3bce92228bf8145c67366bf4387900f80608d3c8470c59ca13396f03b`. Binary SHA256: `3cfb11d93f817b2a0b2916681ea741072a44ea852b469fbabadba94dcb2ac2be`. Canonical Python SHA256: `7cc458c4d489e1b77a50acfcf3fe3f1f96fcd133fcbd581d817a84a329d44f35`.

## Complete deterministic result

537 fixtures: 24 historical (21 pass, 3 fail) and 513 adversarial (482 pass, 31 fail). Exact eligibility mismatches: 34, all Python rejects / C++ accepts; zero Python accepts / C++ rejects. All six historical normal-equations failures pass with V4. Frozen historical Python acceptance decisions remain unchanged.

Maximum normalized-RD difference where both accept: 2.7724116336003135e-09 (ceiling 1e-7). Maximum C++ orthogonality error among accepted fixtures: 2.2048054215684232e-09; every C++ accepted fixture meets its canonical relative gate. Maximum over all computed fixtures, including rejected ones: 0.00045636058718934169. RMS tolerance: absolute difference <=1e-9*max(reference RMS,1e-10); no accepted-by-both output/RMS gate failed.

New defect: replacing normal equations with SVD does not establish exact reference numerical eligibility. For n=11, epsilon=1e-7 and 1e-8, and n=23, epsilon=1e-8, frozen Python rejects while the new SVD kernel accepts. Small accepted-by-both output errors do not authorize widening canonical support. This is implementation/reference eligibility non-equivalence, not market evidence or a mathematical-estimand invalidation.

Actual predictor-only audit count: 0; actual eligibility mismatch count and maximum RD discrepancy: NOT MEASURED, not zero. Audit prohibited after fixture-gate failure. Runtime-only kernel execution timing: 0.025644041001214646 seconds for 537 deterministic fixtures, excluding compilation; no stochastic benchmark.

## Downstream status and limits

V4 worker, dual-layer A/B law, DAILY_AR025/050 proofs, joint-tensor/breadth/stability proofs, partial-null proofs, certification plan, exact trial-count derivation, effect grid, seed law, immutable trial manifest and chunk/resume/merge specification: NOT CREATED / NOT EXECUTED because the predecessor projection gate failed. Their SHA256 values and serial/chunk equivalence are therefore NOT AVAILABLE. No readiness authority and no statistical certification claim.

Full null Monte Carlo=0; full power Monte Carlo=0; real response openings=0; future real signed response computations=0; broker contacts=0; historical requests=0; new acquisition=0; candidate frozen count=0; orders=0; trading not authorized/not executed. Confirmation CLOSED; protected forward CLOSED; Runtime V2 READ_ONLY; depth PLAN_ONLY_NOT_AUTHORIZED; broader relational family OPEN. No source rerank.

Unresolved numerical limitation: exact eligibility equivalence is not achieved. Unresolved statistical limitations: dependence envelope/FWER/power have not been certified. Unresolved economic limitation: no relational market outcome or economic alpha exists. Population remains retained complete-clock observations; missing future clocks are not generalized to; historical reception latency is unobserved; t-10-minute availability is only a conservative research observation law. Infrastructure limitation: standalone compiler/NumPy host binding is frozen, but production worker/parallel/resume architecture remains unbuilt behind the failed gate.

## Durable checkpoints through blocker

| Component | HEAD |
|---|---|
| Declare separate TRIAD V4 successor and freeze unchanged inherited science | `fa2d0ffcab6089dbb3f0d7c686fb180db6a53647` |
| Freeze prospective TRIAD V4 Jacobi SVD law, adversarial suite and toolchain before execution | `ca119943b05b8715fee32e5ae50d8286be9b7d28` |
| Freeze standalone TRIAD V4 Jacobi SVD kernel and deterministic fixture executor before running fixtures | `f8dde0205e5ba61458865c379fb1db912ced3714` |
| Persist complete fixture raw before interpretation | `9b2be492eee14721a6b541bea307fbb30fd7c231` |
| Persist failed TRIAD V4 exact canonical projection equivalence gate and stop without repair | `398cec8cb2fa28ecc4d2d85964e0bbb613dec4ed` |

## All 24 historical outcomes

| Fixture | Python | C++ | Gate | Max normalized difference |
|---|---|---|---|---|
| V3_00_n5_eps1.0 | accept | accept | PASS | 2.220446049250313e-15 |
| V3_01_n5_eps0.01 | accept | accept | PASS | 3.0175861809311755e-13 |
| V3_02_n5_eps0.0001 | accept | accept | PASS | 1.1401990462900358e-11 |
| V3_03_n5_eps1e-06 | accept | accept | PASS | 2.065391635497349e-09 |
| V3_04_n5_eps1e-07 | reject | reject | PASS | N/A |
| V3_05_n5_eps1e-08 | reject | reject | PASS | N/A |
| V3_06_n10_eps1.0 | accept | accept | PASS | 8.881784197001252e-16 |
| V3_07_n10_eps0.01 | accept | accept | PASS | 1.1590728377086634e-13 |
| V3_08_n10_eps0.0001 | accept | accept | PASS | 4.880096327042338e-12 |
| V3_09_n10_eps1e-06 | accept | accept | PASS | 5.375371259219719e-10 |
| V3_10_n10_eps1e-07 | reject | reject | PASS | N/A |
| V3_11_n10_eps1e-08 | reject | reject | PASS | N/A |
| V3_12_n11_eps1.0 | accept | accept | PASS | 8.881784197001252e-16 |
| V3_13_n11_eps0.01 | accept | accept | PASS | 2.0872192862952943e-14 |
| V3_14_n11_eps0.0001 | accept | accept | PASS | 3.6846081741259695e-12 |
| V3_15_n11_eps1e-06 | accept | accept | PASS | 1.820190664858501e-10 |
| V3_16_n11_eps1e-07 | reject | accept | FAIL | N/A |
| V3_17_n11_eps1e-08 | reject | accept | FAIL | N/A |
| V3_18_n23_eps1.0 | accept | accept | PASS | 4.440892098500626e-16 |
| V3_19_n23_eps0.01 | accept | accept | PASS | 6.8833827526759706e-15 |
| V3_20_n23_eps0.0001 | accept | accept | PASS | 1.085798118083403e-12 |
| V3_21_n23_eps1e-06 | accept | accept | PASS | 6.795175533369502e-11 |
| V3_22_n23_eps1e-07 | accept | accept | PASS | 4.931437480593104e-10 |
| V3_23_n23_eps1e-08 | reject | accept | FAIL | N/A |

## All 513 prospective adversarial outcomes

The exact X/D matrices, scaled singular values, all canonical accepted outputs and all C++ outputs are preserved in PROJECTION_FIXTURE_RAW_V1.json.gz. This table does not remove rejected or failed fixtures.

| Fixture | Python | C++ | Gate | Max normalized difference |
|---|---|---|---|---|
| V4_n5_eps1.0_base | accept | accept | PASS | 2.220446049250313e-15 |
| V4_n5_eps1.0_reverse_rows | accept | accept | PASS | 3.552713678800501e-15 |
| V4_n5_eps1.0_control_signs_1_minus1_minus1 | accept | accept | PASS | 2.220446049250313e-15 |
| V4_n5_eps1.0_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 3.1086244689504383e-15 |
| V4_n5_eps1.0_D_sign_flip | accept | accept | PASS | 2.220446049250313e-15 |
| V4_n5_eps1.0_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 5.329070518200751e-15 |
| V4_n5_eps0.01_base | accept | accept | PASS | 3.0175861809311755e-13 |
| V4_n5_eps0.01_reverse_rows | accept | accept | PASS | 9.880984919163893e-14 |
| V4_n5_eps0.01_control_signs_1_minus1_minus1 | accept | accept | PASS | 3.0175861809311755e-13 |
| V4_n5_eps0.01_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 1.1857181902996672e-13 |
| V4_n5_eps0.01_D_sign_flip | accept | accept | PASS | 3.0175861809311755e-13 |
| V4_n5_eps0.01_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 1.6253665080512292e-13 |
| V4_n5_eps0.0001_base | accept | accept | PASS | 1.1401990462900358e-11 |
| V4_n5_eps0.0001_reverse_rows | accept | accept | PASS | 2.050271064035769e-11 |
| V4_n5_eps0.0001_control_signs_1_minus1_minus1 | accept | accept | PASS | 1.1401990462900358e-11 |
| V4_n5_eps0.0001_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 3.31452643109742e-11 |
| V4_n5_eps0.0001_D_sign_flip | accept | accept | PASS | 1.1401990462900358e-11 |
| V4_n5_eps0.0001_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 2.0180412896309008e-11 |
| V4_n5_eps1e-06_base | accept | accept | PASS | 2.065391635497349e-09 |
| V4_n5_eps1e-06_reverse_rows | accept | accept | PASS | 5.162572591643766e-10 |
| V4_n5_eps1e-06_control_signs_1_minus1_minus1 | accept | accept | PASS | 2.065391635497349e-09 |
| V4_n5_eps1e-06_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 4.019100607877135e-10 |
| V4_n5_eps1e-06_D_sign_flip | accept | accept | PASS | 2.065391635497349e-09 |
| V4_n5_eps1e-06_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 1.5926373553298845e-09 |
| V4_n5_eps1e-07_base | reject | reject | PASS | N/A |
| V4_n5_eps1e-07_reverse_rows | reject | reject | PASS | N/A |
| V4_n5_eps1e-07_control_signs_1_minus1_minus1 | reject | reject | PASS | N/A |
| V4_n5_eps1e-07_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_n5_eps1e-07_D_sign_flip | reject | reject | PASS | N/A |
| V4_n5_eps1e-07_D_plus_X_times_0.3_minus0.7_0.2 | reject | reject | PASS | N/A |
| V4_n5_eps1e-08_base | reject | reject | PASS | N/A |
| V4_n5_eps1e-08_reverse_rows | reject | reject | PASS | N/A |
| V4_n5_eps1e-08_control_signs_1_minus1_minus1 | reject | reject | PASS | N/A |
| V4_n5_eps1e-08_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_n5_eps1e-08_D_sign_flip | reject | reject | PASS | N/A |
| V4_n5_eps1e-08_D_plus_X_times_0.3_minus0.7_0.2 | reject | reject | PASS | N/A |
| V4_n5_eps1e-10_base | reject | reject | PASS | N/A |
| V4_n5_eps1e-10_reverse_rows | reject | reject | PASS | N/A |
| V4_n5_eps1e-10_control_signs_1_minus1_minus1 | reject | reject | PASS | N/A |
| V4_n5_eps1e-10_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_n5_eps1e-10_D_sign_flip | reject | reject | PASS | N/A |
| V4_n5_eps1e-10_D_plus_X_times_0.3_minus0.7_0.2 | reject | reject | PASS | N/A |
| V4_n5_eps1e-12_base | reject | reject | PASS | N/A |
| V4_n5_eps1e-12_reverse_rows | reject | reject | PASS | N/A |
| V4_n5_eps1e-12_control_signs_1_minus1_minus1 | reject | reject | PASS | N/A |
| V4_n5_eps1e-12_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_n5_eps1e-12_D_sign_flip | reject | reject | PASS | N/A |
| V4_n5_eps1e-12_D_plus_X_times_0.3_minus0.7_0.2 | reject | reject | PASS | N/A |
| V4_n5_eps1e-13_base | reject | reject | PASS | N/A |
| V4_n5_eps1e-13_reverse_rows | reject | reject | PASS | N/A |
| V4_n5_eps1e-13_control_signs_1_minus1_minus1 | reject | reject | PASS | N/A |
| V4_n5_eps1e-13_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_n5_eps1e-13_D_sign_flip | reject | reject | PASS | N/A |
| V4_n5_eps1e-13_D_plus_X_times_0.3_minus0.7_0.2 | reject | reject | PASS | N/A |
| V4_spectrum_n5_s2e-12_base | reject | reject | PASS | N/A |
| V4_spectrum_n5_s2e-12_reverse_rows | reject | reject | PASS | N/A |
| V4_spectrum_n5_s2e-12_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_spectrum_n5_s2e-12_D_sign_flip | reject | reject | PASS | N/A |
| V4_spectrum_n5_s1.01e-12_base | accept | accept | PASS | 4.718447854656915e-16 |
| V4_spectrum_n5_s1.01e-12_reverse_rows | accept | accept | PASS | 4.718447854656915e-16 |
| V4_spectrum_n5_s1.01e-12_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n5_s1.01e-12_D_sign_flip | accept | accept | PASS | 4.718447854656915e-16 |
| V4_spectrum_n5_s9.9e-13_base | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n5_s9.9e-13_reverse_rows | accept | accept | PASS | 1.6653345369377348e-16 |
| V4_spectrum_n5_s9.9e-13_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n5_s9.9e-13_D_sign_flip | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n5_s5e-13_base | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n5_s5e-13_reverse_rows | accept | accept | PASS | 6.661338147750939e-16 |
| V4_spectrum_n5_s5e-13_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 6.38378239159465e-16 |
| V4_spectrum_n5_s5e-13_D_sign_flip | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n5_s1e-13_base | reject | reject | PASS | N/A |
| V4_spectrum_n5_s1e-13_reverse_rows | reject | reject | PASS | N/A |
| V4_spectrum_n5_s1e-13_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_spectrum_n5_s1e-13_D_sign_flip | reject | reject | PASS | N/A |
| V4_spectrum_n5_s0.0_base | reject | reject | PASS | N/A |
| V4_spectrum_n5_s0.0_reverse_rows | reject | reject | PASS | N/A |
| V4_spectrum_n5_s0.0_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_spectrum_n5_s0.0_D_sign_flip | reject | reject | PASS | N/A |
| V4_n6_eps1.0_base | accept | accept | PASS | 9.645062526431047e-16 |
| V4_n6_eps1.0_reverse_rows | accept | accept | PASS | 1.2212453270876722e-15 |
| V4_n6_eps1.0_control_signs_1_minus1_minus1 | accept | accept | PASS | 9.645062526431047e-16 |
| V4_n6_eps1.0_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 1.4432899320127035e-15 |
| V4_n6_eps1.0_D_sign_flip | accept | accept | PASS | 9.645062526431047e-16 |
| V4_n6_eps1.0_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 2.3314683517128287e-15 |
| V4_n6_eps1.0_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 2.220446049250313e-15 |
| V4_n6_eps0.01_base | accept | accept | PASS | 1.999511667349907e-13 |
| V4_n6_eps0.01_reverse_rows | accept | accept | PASS | 1.193212195715887e-13 |
| V4_n6_eps0.01_control_signs_1_minus1_minus1 | accept | accept | PASS | 1.999511667349907e-13 |
| V4_n6_eps0.01_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 2.6290081223123707e-13 |
| V4_n6_eps0.01_D_sign_flip | accept | accept | PASS | 1.999511667349907e-13 |
| V4_n6_eps0.01_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 2.8255175976710234e-13 |
| V4_n6_eps0.01_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 3.0175861809311755e-13 |
| V4_n6_eps0.0001_base | accept | accept | PASS | 1.3492797157343972e-11 |
| V4_n6_eps0.0001_reverse_rows | accept | accept | PASS | 7.05353137009368e-12 |
| V4_n6_eps0.0001_control_signs_1_minus1_minus1 | accept | accept | PASS | 1.3492797157343972e-11 |
| V4_n6_eps0.0001_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 9.290679336970697e-12 |
| V4_n6_eps0.0001_D_sign_flip | accept | accept | PASS | 1.3492797157343972e-11 |
| V4_n6_eps0.0001_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 1.9871972123386428e-11 |
| V4_n6_eps0.0001_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 1.1401990462900358e-11 |
| V4_n6_eps1e-06_base | accept | accept | PASS | 1.6261185453725346e-09 |
| V4_n6_eps1e-06_reverse_rows | reject | accept | FAIL | N/A |
| V4_n6_eps1e-06_control_signs_1_minus1_minus1 | accept | accept | PASS | 1.6261185453725346e-09 |
| V4_n6_eps1e-06_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 9.371834419624747e-10 |
| V4_n6_eps1e-06_D_sign_flip | accept | accept | PASS | 1.6261185453725346e-09 |
| V4_n6_eps1e-06_D_plus_X_times_0.3_minus0.7_0.2 | reject | accept | FAIL | N/A |
| V4_n6_eps1e-06_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 2.065391635497349e-09 |
| V4_n6_eps1e-07_base | reject | reject | PASS | N/A |
| V4_n6_eps1e-07_reverse_rows | reject | reject | PASS | N/A |
| V4_n6_eps1e-07_control_signs_1_minus1_minus1 | reject | reject | PASS | N/A |
| V4_n6_eps1e-07_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_n6_eps1e-07_D_sign_flip | reject | reject | PASS | N/A |
| V4_n6_eps1e-07_D_plus_X_times_0.3_minus0.7_0.2 | reject | reject | PASS | N/A |
| V4_n6_eps1e-07_leave_last_target_out_if_n_gt5 | reject | reject | PASS | N/A |
| V4_n6_eps1e-08_base | reject | reject | PASS | N/A |
| V4_n6_eps1e-08_reverse_rows | reject | reject | PASS | N/A |
| V4_n6_eps1e-08_control_signs_1_minus1_minus1 | reject | reject | PASS | N/A |
| V4_n6_eps1e-08_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_n6_eps1e-08_D_sign_flip | reject | reject | PASS | N/A |
| V4_n6_eps1e-08_D_plus_X_times_0.3_minus0.7_0.2 | reject | reject | PASS | N/A |
| V4_n6_eps1e-08_leave_last_target_out_if_n_gt5 | reject | reject | PASS | N/A |
| V4_n6_eps1e-10_base | reject | reject | PASS | N/A |
| V4_n6_eps1e-10_reverse_rows | reject | reject | PASS | N/A |
| V4_n6_eps1e-10_control_signs_1_minus1_minus1 | reject | reject | PASS | N/A |
| V4_n6_eps1e-10_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_n6_eps1e-10_D_sign_flip | reject | reject | PASS | N/A |
| V4_n6_eps1e-10_D_plus_X_times_0.3_minus0.7_0.2 | reject | reject | PASS | N/A |
| V4_n6_eps1e-10_leave_last_target_out_if_n_gt5 | reject | reject | PASS | N/A |
| V4_n6_eps1e-12_base | reject | reject | PASS | N/A |
| V4_n6_eps1e-12_reverse_rows | reject | reject | PASS | N/A |
| V4_n6_eps1e-12_control_signs_1_minus1_minus1 | reject | reject | PASS | N/A |
| V4_n6_eps1e-12_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_n6_eps1e-12_D_sign_flip | reject | reject | PASS | N/A |
| V4_n6_eps1e-12_D_plus_X_times_0.3_minus0.7_0.2 | reject | reject | PASS | N/A |
| V4_n6_eps1e-12_leave_last_target_out_if_n_gt5 | reject | reject | PASS | N/A |
| V4_n6_eps1e-13_base | reject | reject | PASS | N/A |
| V4_n6_eps1e-13_reverse_rows | reject | reject | PASS | N/A |
| V4_n6_eps1e-13_control_signs_1_minus1_minus1 | reject | reject | PASS | N/A |
| V4_n6_eps1e-13_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_n6_eps1e-13_D_sign_flip | reject | reject | PASS | N/A |
| V4_n6_eps1e-13_D_plus_X_times_0.3_minus0.7_0.2 | reject | reject | PASS | N/A |
| V4_n6_eps1e-13_leave_last_target_out_if_n_gt5 | reject | reject | PASS | N/A |
| V4_spectrum_n6_s2e-12_base | reject | reject | PASS | N/A |
| V4_spectrum_n6_s2e-12_reverse_rows | reject | reject | PASS | N/A |
| V4_spectrum_n6_s2e-12_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_spectrum_n6_s2e-12_D_sign_flip | reject | reject | PASS | N/A |
| V4_spectrum_n6_s1.01e-12_base | accept | accept | PASS | 1.1102230246251565e-16 |
| V4_spectrum_n6_s1.01e-12_reverse_rows | accept | accept | PASS | 3.3306690738754696e-16 |
| V4_spectrum_n6_s1.01e-12_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 5.551115123125783e-17 |
| V4_spectrum_n6_s1.01e-12_D_sign_flip | accept | accept | PASS | 1.1102230246251565e-16 |
| V4_spectrum_n6_s9.9e-13_base | accept | accept | PASS | 3.885780586188048e-16 |
| V4_spectrum_n6_s9.9e-13_reverse_rows | accept | accept | PASS | 1.1102230246251565e-16 |
| V4_spectrum_n6_s9.9e-13_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 4.996003610813204e-16 |
| V4_spectrum_n6_s9.9e-13_D_sign_flip | accept | accept | PASS | 3.885780586188048e-16 |
| V4_spectrum_n6_s5e-13_base | accept | accept | PASS | 1.1102230246251565e-16 |
| V4_spectrum_n6_s5e-13_reverse_rows | accept | accept | PASS | 2.7755575615628914e-16 |
| V4_spectrum_n6_s5e-13_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 3.3306690738754696e-16 |
| V4_spectrum_n6_s5e-13_D_sign_flip | accept | accept | PASS | 1.1102230246251565e-16 |
| V4_spectrum_n6_s1e-13_base | reject | reject | PASS | N/A |
| V4_spectrum_n6_s1e-13_reverse_rows | reject | reject | PASS | N/A |
| V4_spectrum_n6_s1e-13_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_spectrum_n6_s1e-13_D_sign_flip | reject | reject | PASS | N/A |
| V4_spectrum_n6_s0.0_base | reject | reject | PASS | N/A |
| V4_spectrum_n6_s0.0_reverse_rows | reject | reject | PASS | N/A |
| V4_spectrum_n6_s0.0_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_spectrum_n6_s0.0_D_sign_flip | reject | reject | PASS | N/A |
| V4_n10_eps1.0_base | accept | accept | PASS | 8.881784197001252e-16 |
| V4_n10_eps1.0_reverse_rows | accept | accept | PASS | 4.440892098500626e-16 |
| V4_n10_eps1.0_control_signs_1_minus1_minus1 | accept | accept | PASS | 8.881784197001252e-16 |
| V4_n10_eps1.0_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 8.881784197001252e-16 |
| V4_n10_eps1.0_D_sign_flip | accept | accept | PASS | 8.881784197001252e-16 |
| V4_n10_eps1.0_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 7.771561172376096e-16 |
| V4_n10_eps1.0_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 2.220446049250313e-16 |
| V4_n10_eps0.01_base | accept | accept | PASS | 1.1590728377086634e-13 |
| V4_n10_eps0.01_reverse_rows | accept | accept | PASS | 1.3367085216486885e-13 |
| V4_n10_eps0.01_control_signs_1_minus1_minus1 | accept | accept | PASS | 1.1590728377086634e-13 |
| V4_n10_eps0.01_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 1.156852391659413e-13 |
| V4_n10_eps0.01_D_sign_flip | accept | accept | PASS | 1.1590728377086634e-13 |
| V4_n10_eps0.01_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 1.4477308241112041e-13 |
| V4_n10_eps0.01_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 5.4511950509095186e-14 |
| V4_n10_eps0.0001_base | accept | accept | PASS | 4.880096327042338e-12 |
| V4_n10_eps0.0001_reverse_rows | accept | accept | PASS | 4.7798431879186865e-12 |
| V4_n10_eps0.0001_control_signs_1_minus1_minus1 | accept | accept | PASS | 4.880096327042338e-12 |
| V4_n10_eps0.0001_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 3.1599167726881205e-12 |
| V4_n10_eps0.0001_D_sign_flip | accept | accept | PASS | 4.880096327042338e-12 |
| V4_n10_eps0.0001_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 4.32898161761841e-12 |
| V4_n10_eps0.0001_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 5.182188012042843e-12 |
| V4_n10_eps1e-06_base | accept | accept | PASS | 5.375371259219719e-10 |
| V4_n10_eps1e-06_reverse_rows | accept | accept | PASS | 6.534826013648853e-10 |
| V4_n10_eps1e-06_control_signs_1_minus1_minus1 | accept | accept | PASS | 5.375371259219719e-10 |
| V4_n10_eps1e-06_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 4.2956493917500893e-10 |
| V4_n10_eps1e-06_D_sign_flip | accept | accept | PASS | 5.375371259219719e-10 |
| V4_n10_eps1e-06_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 5.110982748135484e-10 |
| V4_n10_eps1e-06_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 4.3019510176378617e-10 |
| V4_n10_eps1e-07_base | reject | reject | PASS | N/A |
| V4_n10_eps1e-07_reverse_rows | reject | accept | FAIL | N/A |
| V4_n10_eps1e-07_control_signs_1_minus1_minus1 | reject | reject | PASS | N/A |
| V4_n10_eps1e-07_raw_scales_1e-6_1e6_3 | reject | accept | FAIL | N/A |
| V4_n10_eps1e-07_D_sign_flip | reject | reject | PASS | N/A |
| V4_n10_eps1e-07_D_plus_X_times_0.3_minus0.7_0.2 | reject | accept | FAIL | N/A |
| V4_n10_eps1e-07_leave_last_target_out_if_n_gt5 | reject | reject | PASS | N/A |
| V4_n10_eps1e-08_base | reject | reject | PASS | N/A |
| V4_n10_eps1e-08_reverse_rows | reject | reject | PASS | N/A |
| V4_n10_eps1e-08_control_signs_1_minus1_minus1 | reject | reject | PASS | N/A |
| V4_n10_eps1e-08_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_n10_eps1e-08_D_sign_flip | reject | reject | PASS | N/A |
| V4_n10_eps1e-08_D_plus_X_times_0.3_minus0.7_0.2 | reject | reject | PASS | N/A |
| V4_n10_eps1e-08_leave_last_target_out_if_n_gt5 | reject | reject | PASS | N/A |
| V4_n10_eps1e-10_base | reject | reject | PASS | N/A |
| V4_n10_eps1e-10_reverse_rows | reject | reject | PASS | N/A |
| V4_n10_eps1e-10_control_signs_1_minus1_minus1 | reject | reject | PASS | N/A |
| V4_n10_eps1e-10_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_n10_eps1e-10_D_sign_flip | reject | reject | PASS | N/A |
| V4_n10_eps1e-10_D_plus_X_times_0.3_minus0.7_0.2 | reject | reject | PASS | N/A |
| V4_n10_eps1e-10_leave_last_target_out_if_n_gt5 | reject | reject | PASS | N/A |
| V4_n10_eps1e-12_base | accept | accept | PASS | 4.440892098500626e-16 |
| V4_n10_eps1e-12_reverse_rows | accept | accept | PASS | 4.440892098500626e-16 |
| V4_n10_eps1e-12_control_signs_1_minus1_minus1 | accept | accept | PASS | 4.440892098500626e-16 |
| V4_n10_eps1e-12_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 4.440892098500626e-16 |
| V4_n10_eps1e-12_D_sign_flip | accept | accept | PASS | 4.440892098500626e-16 |
| V4_n10_eps1e-12_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 6.661338147750939e-16 |
| V4_n10_eps1e-12_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 2.220446049250313e-16 |
| V4_n10_eps1e-13_base | reject | reject | PASS | N/A |
| V4_n10_eps1e-13_reverse_rows | reject | reject | PASS | N/A |
| V4_n10_eps1e-13_control_signs_1_minus1_minus1 | reject | reject | PASS | N/A |
| V4_n10_eps1e-13_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_n10_eps1e-13_D_sign_flip | reject | reject | PASS | N/A |
| V4_n10_eps1e-13_D_plus_X_times_0.3_minus0.7_0.2 | reject | reject | PASS | N/A |
| V4_n10_eps1e-13_leave_last_target_out_if_n_gt5 | reject | reject | PASS | N/A |
| V4_spectrum_n10_s2e-12_base | accept | accept | PASS | 1.1102230246251565e-16 |
| V4_spectrum_n10_s2e-12_reverse_rows | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n10_s2e-12_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n10_s2e-12_D_sign_flip | accept | accept | PASS | 1.1102230246251565e-16 |
| V4_spectrum_n10_s1.01e-12_base | accept | accept | PASS | 1.1102230246251565e-16 |
| V4_spectrum_n10_s1.01e-12_reverse_rows | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n10_s1.01e-12_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n10_s1.01e-12_D_sign_flip | accept | accept | PASS | 1.1102230246251565e-16 |
| V4_spectrum_n10_s9.9e-13_base | accept | accept | PASS | 6.661338147750939e-16 |
| V4_spectrum_n10_s9.9e-13_reverse_rows | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n10_s9.9e-13_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 6.661338147750939e-16 |
| V4_spectrum_n10_s9.9e-13_D_sign_flip | accept | accept | PASS | 6.661338147750939e-16 |
| V4_spectrum_n10_s5e-13_base | accept | accept | PASS | 0.0 |
| V4_spectrum_n10_s5e-13_reverse_rows | accept | accept | PASS | 0.0 |
| V4_spectrum_n10_s5e-13_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 3.3306690738754696e-16 |
| V4_spectrum_n10_s5e-13_D_sign_flip | accept | accept | PASS | 0.0 |
| V4_spectrum_n10_s1e-13_base | reject | reject | PASS | N/A |
| V4_spectrum_n10_s1e-13_reverse_rows | reject | reject | PASS | N/A |
| V4_spectrum_n10_s1e-13_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_spectrum_n10_s1e-13_D_sign_flip | reject | reject | PASS | N/A |
| V4_spectrum_n10_s0.0_base | reject | reject | PASS | N/A |
| V4_spectrum_n10_s0.0_reverse_rows | reject | reject | PASS | N/A |
| V4_spectrum_n10_s0.0_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_spectrum_n10_s0.0_D_sign_flip | reject | reject | PASS | N/A |
| V4_n11_eps1.0_base | accept | accept | PASS | 8.881784197001252e-16 |
| V4_n11_eps1.0_reverse_rows | accept | accept | PASS | 4.440892098500626e-16 |
| V4_n11_eps1.0_control_signs_1_minus1_minus1 | accept | accept | PASS | 8.881784197001252e-16 |
| V4_n11_eps1.0_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 4.440892098500626e-16 |
| V4_n11_eps1.0_D_sign_flip | accept | accept | PASS | 8.881784197001252e-16 |
| V4_n11_eps1.0_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 1.3322676295501878e-15 |
| V4_n11_eps1.0_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 8.881784197001252e-16 |
| V4_n11_eps0.01_base | accept | accept | PASS | 2.0872192862952943e-14 |
| V4_n11_eps0.01_reverse_rows | accept | accept | PASS | 1.0658141036401503e-14 |
| V4_n11_eps0.01_control_signs_1_minus1_minus1 | accept | accept | PASS | 2.0872192862952943e-14 |
| V4_n11_eps0.01_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 1.942890293094024e-14 |
| V4_n11_eps0.01_D_sign_flip | accept | accept | PASS | 2.0872192862952943e-14 |
| V4_n11_eps0.01_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 2.220446049250313e-14 |
| V4_n11_eps0.01_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 1.1590728377086634e-13 |
| V4_n11_eps0.0001_base | accept | accept | PASS | 3.6846081741259695e-12 |
| V4_n11_eps0.0001_reverse_rows | accept | accept | PASS | 1.3767875728376566e-12 |
| V4_n11_eps0.0001_control_signs_1_minus1_minus1 | accept | accept | PASS | 3.6846081741259695e-12 |
| V4_n11_eps0.0001_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 1.7961188092385783e-12 |
| V4_n11_eps0.0001_D_sign_flip | accept | accept | PASS | 3.6846081741259695e-12 |
| V4_n11_eps0.0001_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 3.6637359812630166e-12 |
| V4_n11_eps0.0001_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 4.880096327042338e-12 |
| V4_n11_eps1e-06_base | accept | accept | PASS | 1.820190664858501e-10 |
| V4_n11_eps1e-06_reverse_rows | accept | accept | PASS | 6.17319528828375e-11 |
| V4_n11_eps1e-06_control_signs_1_minus1_minus1 | accept | accept | PASS | 1.820190664858501e-10 |
| V4_n11_eps1e-06_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 2.600837323285532e-10 |
| V4_n11_eps1e-06_D_sign_flip | accept | accept | PASS | 1.820190664858501e-10 |
| V4_n11_eps1e-06_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 1.9649548654854243e-10 |
| V4_n11_eps1e-06_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 5.375371259219719e-10 |
| V4_n11_eps1e-07_base | reject | accept | FAIL | N/A |
| V4_n11_eps1e-07_reverse_rows | reject | accept | FAIL | N/A |
| V4_n11_eps1e-07_control_signs_1_minus1_minus1 | reject | accept | FAIL | N/A |
| V4_n11_eps1e-07_raw_scales_1e-6_1e6_3 | reject | accept | FAIL | N/A |
| V4_n11_eps1e-07_D_sign_flip | reject | accept | FAIL | N/A |
| V4_n11_eps1e-07_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 2.7724116336003135e-09 |
| V4_n11_eps1e-07_leave_last_target_out_if_n_gt5 | reject | reject | PASS | N/A |
| V4_n11_eps1e-08_base | reject | accept | FAIL | N/A |
| V4_n11_eps1e-08_reverse_rows | reject | accept | FAIL | N/A |
| V4_n11_eps1e-08_control_signs_1_minus1_minus1 | reject | accept | FAIL | N/A |
| V4_n11_eps1e-08_raw_scales_1e-6_1e6_3 | reject | accept | FAIL | N/A |
| V4_n11_eps1e-08_D_sign_flip | reject | accept | FAIL | N/A |
| V4_n11_eps1e-08_D_plus_X_times_0.3_minus0.7_0.2 | reject | reject | PASS | N/A |
| V4_n11_eps1e-08_leave_last_target_out_if_n_gt5 | reject | reject | PASS | N/A |
| V4_n11_eps1e-10_base | reject | reject | PASS | N/A |
| V4_n11_eps1e-10_reverse_rows | reject | reject | PASS | N/A |
| V4_n11_eps1e-10_control_signs_1_minus1_minus1 | reject | reject | PASS | N/A |
| V4_n11_eps1e-10_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_n11_eps1e-10_D_sign_flip | reject | reject | PASS | N/A |
| V4_n11_eps1e-10_D_plus_X_times_0.3_minus0.7_0.2 | reject | reject | PASS | N/A |
| V4_n11_eps1e-10_leave_last_target_out_if_n_gt5 | reject | reject | PASS | N/A |
| V4_n11_eps1e-12_base | accept | accept | PASS | 2.220446049250313e-16 |
| V4_n11_eps1e-12_reverse_rows | accept | accept | PASS | 2.220446049250313e-16 |
| V4_n11_eps1e-12_control_signs_1_minus1_minus1 | accept | accept | PASS | 2.220446049250313e-16 |
| V4_n11_eps1e-12_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 2.220446049250313e-16 |
| V4_n11_eps1e-12_D_sign_flip | accept | accept | PASS | 2.220446049250313e-16 |
| V4_n11_eps1e-12_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 4.440892098500626e-16 |
| V4_n11_eps1e-12_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 4.440892098500626e-16 |
| V4_n11_eps1e-13_base | reject | reject | PASS | N/A |
| V4_n11_eps1e-13_reverse_rows | reject | reject | PASS | N/A |
| V4_n11_eps1e-13_control_signs_1_minus1_minus1 | reject | reject | PASS | N/A |
| V4_n11_eps1e-13_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_n11_eps1e-13_D_sign_flip | reject | reject | PASS | N/A |
| V4_n11_eps1e-13_D_plus_X_times_0.3_minus0.7_0.2 | reject | reject | PASS | N/A |
| V4_n11_eps1e-13_leave_last_target_out_if_n_gt5 | reject | reject | PASS | N/A |
| V4_spectrum_n11_s2e-12_base | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n11_s2e-12_reverse_rows | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n11_s2e-12_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n11_s2e-12_D_sign_flip | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n11_s1.01e-12_base | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n11_s1.01e-12_reverse_rows | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n11_s1.01e-12_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 3.3306690738754696e-16 |
| V4_spectrum_n11_s1.01e-12_D_sign_flip | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n11_s9.9e-13_base | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n11_s9.9e-13_reverse_rows | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n11_s9.9e-13_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n11_s9.9e-13_D_sign_flip | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n11_s5e-13_base | accept | accept | PASS | 3.3306690738754696e-16 |
| V4_spectrum_n11_s5e-13_reverse_rows | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n11_s5e-13_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n11_s5e-13_D_sign_flip | accept | accept | PASS | 3.3306690738754696e-16 |
| V4_spectrum_n11_s1e-13_base | reject | reject | PASS | N/A |
| V4_spectrum_n11_s1e-13_reverse_rows | reject | reject | PASS | N/A |
| V4_spectrum_n11_s1e-13_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_spectrum_n11_s1e-13_D_sign_flip | reject | reject | PASS | N/A |
| V4_spectrum_n11_s0.0_base | reject | reject | PASS | N/A |
| V4_spectrum_n11_s0.0_reverse_rows | reject | reject | PASS | N/A |
| V4_spectrum_n11_s0.0_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_spectrum_n11_s0.0_D_sign_flip | reject | reject | PASS | N/A |
| V4_n22_eps1.0_base | accept | accept | PASS | 2.220446049250313e-16 |
| V4_n22_eps1.0_reverse_rows | accept | accept | PASS | 4.440892098500626e-16 |
| V4_n22_eps1.0_control_signs_1_minus1_minus1 | accept | accept | PASS | 2.220446049250313e-16 |
| V4_n22_eps1.0_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 2.220446049250313e-16 |
| V4_n22_eps1.0_D_sign_flip | accept | accept | PASS | 2.220446049250313e-16 |
| V4_n22_eps1.0_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 1.1102230246251565e-15 |
| V4_n22_eps1.0_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 6.661338147750939e-16 |
| V4_n22_eps0.01_base | accept | accept | PASS | 6.356026815979021e-15 |
| V4_n22_eps0.01_reverse_rows | accept | accept | PASS | 2.886579864025407e-15 |
| V4_n22_eps0.01_control_signs_1_minus1_minus1 | accept | accept | PASS | 6.356026815979021e-15 |
| V4_n22_eps0.01_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 2.4424906541753444e-14 |
| V4_n22_eps0.01_D_sign_flip | accept | accept | PASS | 6.356026815979021e-15 |
| V4_n22_eps0.01_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 8.659739592076221e-15 |
| V4_n22_eps0.01_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 5.551115123125783e-15 |
| V4_n22_eps0.0001_base | accept | accept | PASS | 1.9051427102567686e-13 |
| V4_n22_eps0.0001_reverse_rows | accept | accept | PASS | 9.245659793322147e-13 |
| V4_n22_eps0.0001_control_signs_1_minus1_minus1 | accept | accept | PASS | 1.9051427102567686e-13 |
| V4_n22_eps0.0001_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 1.9315660182428473e-12 |
| V4_n22_eps0.0001_D_sign_flip | accept | accept | PASS | 1.9051427102567686e-13 |
| V4_n22_eps0.0001_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 3.276268145668837e-13 |
| V4_n22_eps0.0001_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 7.667200208061331e-13 |
| V4_n22_eps1e-06_base | accept | accept | PASS | 1.7310641808876426e-10 |
| V4_n22_eps1e-06_reverse_rows | accept | accept | PASS | 8.958611630305313e-11 |
| V4_n22_eps1e-06_control_signs_1_minus1_minus1 | accept | accept | PASS | 1.7310641808876426e-10 |
| V4_n22_eps1e-06_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 2.339162197273481e-10 |
| V4_n22_eps1e-06_D_sign_flip | accept | accept | PASS | 1.7310641808876426e-10 |
| V4_n22_eps1e-06_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 1.5557677368605027e-10 |
| V4_n22_eps1e-06_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 5.793887591920566e-11 |
| V4_n22_eps1e-07_base | reject | accept | FAIL | N/A |
| V4_n22_eps1e-07_reverse_rows | reject | accept | FAIL | N/A |
| V4_n22_eps1e-07_control_signs_1_minus1_minus1 | reject | accept | FAIL | N/A |
| V4_n22_eps1e-07_raw_scales_1e-6_1e6_3 | reject | accept | FAIL | N/A |
| V4_n22_eps1e-07_D_sign_flip | reject | accept | FAIL | N/A |
| V4_n22_eps1e-07_D_plus_X_times_0.3_minus0.7_0.2 | reject | accept | FAIL | N/A |
| V4_n22_eps1e-07_leave_last_target_out_if_n_gt5 | reject | accept | FAIL | N/A |
| V4_n22_eps1e-08_base | reject | reject | PASS | N/A |
| V4_n22_eps1e-08_reverse_rows | reject | reject | PASS | N/A |
| V4_n22_eps1e-08_control_signs_1_minus1_minus1 | reject | reject | PASS | N/A |
| V4_n22_eps1e-08_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_n22_eps1e-08_D_sign_flip | reject | reject | PASS | N/A |
| V4_n22_eps1e-08_D_plus_X_times_0.3_minus0.7_0.2 | reject | reject | PASS | N/A |
| V4_n22_eps1e-08_leave_last_target_out_if_n_gt5 | reject | reject | PASS | N/A |
| V4_n22_eps1e-10_base | reject | reject | PASS | N/A |
| V4_n22_eps1e-10_reverse_rows | reject | reject | PASS | N/A |
| V4_n22_eps1e-10_control_signs_1_minus1_minus1 | reject | reject | PASS | N/A |
| V4_n22_eps1e-10_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_n22_eps1e-10_D_sign_flip | reject | reject | PASS | N/A |
| V4_n22_eps1e-10_D_plus_X_times_0.3_minus0.7_0.2 | reject | reject | PASS | N/A |
| V4_n22_eps1e-10_leave_last_target_out_if_n_gt5 | reject | reject | PASS | N/A |
| V4_n22_eps1e-12_base | accept | accept | PASS | 2.498001805406602e-16 |
| V4_n22_eps1e-12_reverse_rows | accept | accept | PASS | 2.220446049250313e-16 |
| V4_n22_eps1e-12_control_signs_1_minus1_minus1 | accept | accept | PASS | 2.498001805406602e-16 |
| V4_n22_eps1e-12_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 2.220446049250313e-16 |
| V4_n22_eps1e-12_D_sign_flip | accept | accept | PASS | 2.498001805406602e-16 |
| V4_n22_eps1e-12_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 2.220446049250313e-16 |
| V4_n22_eps1e-12_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 2.220446049250313e-16 |
| V4_n22_eps1e-13_base | reject | reject | PASS | N/A |
| V4_n22_eps1e-13_reverse_rows | reject | reject | PASS | N/A |
| V4_n22_eps1e-13_control_signs_1_minus1_minus1 | reject | reject | PASS | N/A |
| V4_n22_eps1e-13_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_n22_eps1e-13_D_sign_flip | reject | reject | PASS | N/A |
| V4_n22_eps1e-13_D_plus_X_times_0.3_minus0.7_0.2 | reject | reject | PASS | N/A |
| V4_n22_eps1e-13_leave_last_target_out_if_n_gt5 | reject | reject | PASS | N/A |
| V4_spectrum_n22_s2e-12_base | accept | accept | PASS | 2.7755575615628914e-17 |
| V4_spectrum_n22_s2e-12_reverse_rows | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n22_s2e-12_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n22_s2e-12_D_sign_flip | accept | accept | PASS | 2.7755575615628914e-17 |
| V4_spectrum_n22_s1.01e-12_base | accept | accept | PASS | 1.1102230246251565e-16 |
| V4_spectrum_n22_s1.01e-12_reverse_rows | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n22_s1.01e-12_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n22_s1.01e-12_D_sign_flip | accept | accept | PASS | 1.1102230246251565e-16 |
| V4_spectrum_n22_s9.9e-13_base | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n22_s9.9e-13_reverse_rows | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n22_s9.9e-13_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n22_s9.9e-13_D_sign_flip | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n22_s5e-13_base | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n22_s5e-13_reverse_rows | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n22_s5e-13_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n22_s5e-13_D_sign_flip | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n22_s1e-13_base | reject | reject | PASS | N/A |
| V4_spectrum_n22_s1e-13_reverse_rows | reject | reject | PASS | N/A |
| V4_spectrum_n22_s1e-13_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_spectrum_n22_s1e-13_D_sign_flip | reject | reject | PASS | N/A |
| V4_spectrum_n22_s0.0_base | reject | reject | PASS | N/A |
| V4_spectrum_n22_s0.0_reverse_rows | reject | reject | PASS | N/A |
| V4_spectrum_n22_s0.0_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_spectrum_n22_s0.0_D_sign_flip | reject | reject | PASS | N/A |
| V4_n23_eps1.0_base | accept | accept | PASS | 4.440892098500626e-16 |
| V4_n23_eps1.0_reverse_rows | accept | accept | PASS | 6.661338147750939e-16 |
| V4_n23_eps1.0_control_signs_1_minus1_minus1 | accept | accept | PASS | 4.440892098500626e-16 |
| V4_n23_eps1.0_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 4.440892098500626e-16 |
| V4_n23_eps1.0_D_sign_flip | accept | accept | PASS | 4.440892098500626e-16 |
| V4_n23_eps1.0_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 1.5543122344752192e-15 |
| V4_n23_eps1.0_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 2.220446049250313e-16 |
| V4_n23_eps0.01_base | accept | accept | PASS | 6.8833827526759706e-15 |
| V4_n23_eps0.01_reverse_rows | accept | accept | PASS | 5.745404152435185e-15 |
| V4_n23_eps0.01_control_signs_1_minus1_minus1 | accept | accept | PASS | 6.8833827526759706e-15 |
| V4_n23_eps0.01_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 6.106226635438361e-15 |
| V4_n23_eps0.01_D_sign_flip | accept | accept | PASS | 6.8833827526759706e-15 |
| V4_n23_eps0.01_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 7.993605777301127e-15 |
| V4_n23_eps0.01_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 6.356026815979021e-15 |
| V4_n23_eps0.0001_base | accept | accept | PASS | 1.085798118083403e-12 |
| V4_n23_eps0.0001_reverse_rows | accept | accept | PASS | 3.4477976029734236e-13 |
| V4_n23_eps0.0001_control_signs_1_minus1_minus1 | accept | accept | PASS | 1.085798118083403e-12 |
| V4_n23_eps0.0001_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 2.2648549702353193e-13 |
| V4_n23_eps0.0001_D_sign_flip | accept | accept | PASS | 1.085798118083403e-12 |
| V4_n23_eps0.0001_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 1.231501012277647e-12 |
| V4_n23_eps0.0001_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 1.9051427102567686e-13 |
| V4_n23_eps1e-06_base | accept | accept | PASS | 6.795175533369502e-11 |
| V4_n23_eps1e-06_reverse_rows | accept | accept | PASS | 1.0804512839968083e-10 |
| V4_n23_eps1e-06_control_signs_1_minus1_minus1 | accept | accept | PASS | 6.795175533369502e-11 |
| V4_n23_eps1e-06_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 1.1291456658568677e-10 |
| V4_n23_eps1e-06_D_sign_flip | accept | accept | PASS | 6.795175533369502e-11 |
| V4_n23_eps1e-06_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 5.771914890484453e-11 |
| V4_n23_eps1e-06_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 1.7310641808876426e-10 |
| V4_n23_eps1e-07_base | accept | accept | PASS | 4.931437480593104e-10 |
| V4_n23_eps1e-07_reverse_rows | reject | accept | FAIL | N/A |
| V4_n23_eps1e-07_control_signs_1_minus1_minus1 | accept | accept | PASS | 4.931437480593104e-10 |
| V4_n23_eps1e-07_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 2.1266166605471426e-10 |
| V4_n23_eps1e-07_D_sign_flip | accept | accept | PASS | 4.931437480593104e-10 |
| V4_n23_eps1e-07_D_plus_X_times_0.3_minus0.7_0.2 | reject | accept | FAIL | N/A |
| V4_n23_eps1e-07_leave_last_target_out_if_n_gt5 | reject | accept | FAIL | N/A |
| V4_n23_eps1e-08_base | reject | accept | FAIL | N/A |
| V4_n23_eps1e-08_reverse_rows | reject | accept | FAIL | N/A |
| V4_n23_eps1e-08_control_signs_1_minus1_minus1 | reject | accept | FAIL | N/A |
| V4_n23_eps1e-08_raw_scales_1e-6_1e6_3 | reject | accept | FAIL | N/A |
| V4_n23_eps1e-08_D_sign_flip | reject | accept | FAIL | N/A |
| V4_n23_eps1e-08_D_plus_X_times_0.3_minus0.7_0.2 | reject | accept | FAIL | N/A |
| V4_n23_eps1e-08_leave_last_target_out_if_n_gt5 | reject | reject | PASS | N/A |
| V4_n23_eps1e-10_base | reject | reject | PASS | N/A |
| V4_n23_eps1e-10_reverse_rows | reject | reject | PASS | N/A |
| V4_n23_eps1e-10_control_signs_1_minus1_minus1 | reject | reject | PASS | N/A |
| V4_n23_eps1e-10_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_n23_eps1e-10_D_sign_flip | reject | reject | PASS | N/A |
| V4_n23_eps1e-10_D_plus_X_times_0.3_minus0.7_0.2 | reject | reject | PASS | N/A |
| V4_n23_eps1e-10_leave_last_target_out_if_n_gt5 | reject | reject | PASS | N/A |
| V4_n23_eps1e-12_base | accept | accept | PASS | 2.220446049250313e-16 |
| V4_n23_eps1e-12_reverse_rows | accept | accept | PASS | 2.220446049250313e-16 |
| V4_n23_eps1e-12_control_signs_1_minus1_minus1 | accept | accept | PASS | 2.220446049250313e-16 |
| V4_n23_eps1e-12_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 2.220446049250313e-16 |
| V4_n23_eps1e-12_D_sign_flip | accept | accept | PASS | 2.220446049250313e-16 |
| V4_n23_eps1e-12_D_plus_X_times_0.3_minus0.7_0.2 | accept | accept | PASS | 4.440892098500626e-16 |
| V4_n23_eps1e-12_leave_last_target_out_if_n_gt5 | accept | accept | PASS | 2.498001805406602e-16 |
| V4_n23_eps1e-13_base | reject | reject | PASS | N/A |
| V4_n23_eps1e-13_reverse_rows | reject | reject | PASS | N/A |
| V4_n23_eps1e-13_control_signs_1_minus1_minus1 | reject | reject | PASS | N/A |
| V4_n23_eps1e-13_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_n23_eps1e-13_D_sign_flip | reject | reject | PASS | N/A |
| V4_n23_eps1e-13_D_plus_X_times_0.3_minus0.7_0.2 | reject | reject | PASS | N/A |
| V4_n23_eps1e-13_leave_last_target_out_if_n_gt5 | reject | reject | PASS | N/A |
| V4_spectrum_n23_s2e-12_base | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n23_s2e-12_reverse_rows | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n23_s2e-12_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 1.1102230246251565e-16 |
| V4_spectrum_n23_s2e-12_D_sign_flip | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n23_s1.01e-12_base | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n23_s1.01e-12_reverse_rows | accept | accept | PASS | 3.3306690738754696e-16 |
| V4_spectrum_n23_s1.01e-12_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n23_s1.01e-12_D_sign_flip | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n23_s9.9e-13_base | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n23_s9.9e-13_reverse_rows | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n23_s9.9e-13_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 3.3306690738754696e-16 |
| V4_spectrum_n23_s9.9e-13_D_sign_flip | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n23_s5e-13_base | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n23_s5e-13_reverse_rows | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n23_s5e-13_raw_scales_1e-6_1e6_3 | accept | accept | PASS | 4.440892098500626e-16 |
| V4_spectrum_n23_s5e-13_D_sign_flip | accept | accept | PASS | 2.220446049250313e-16 |
| V4_spectrum_n23_s1e-13_base | reject | reject | PASS | N/A |
| V4_spectrum_n23_s1e-13_reverse_rows | reject | reject | PASS | N/A |
| V4_spectrum_n23_s1e-13_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_spectrum_n23_s1e-13_D_sign_flip | reject | reject | PASS | N/A |
| V4_spectrum_n23_s0.0_base | reject | reject | PASS | N/A |
| V4_spectrum_n23_s0.0_reverse_rows | reject | reject | PASS | N/A |
| V4_spectrum_n23_s0.0_raw_scales_1e-6_1e6_3 | reject | reject | PASS | N/A |
| V4_spectrum_n23_s0.0_D_sign_flip | reject | reject | PASS | N/A |

## V4 artifact SHA256 bindings

| Artifact | SHA256 |
|---|---|
| TRIAD_RELATIONAL_STATE_V4_PREOUTCOME_BLOCKER_V1.json | `9d69a12670513e8c66e789972cb8f79bbee8f9967b1269154de94fb549e091e5` |
| CHECKPOINTS_THROUGH_BLOCKER_V1.json | `be00709f5da38fe8725302de41c14f98016cbce91b6aa7f96412e262273284af` |
| INHERITED_IMMUTABLE_BINDINGS_V1.json | `458f5a6ecddec9ec8c394681bfbe8f7305f423129787333ae7ac55996a0f1f56` |
| NUMERICAL_KERNEL_SPEC_V1.json | `005fb827df4ce469fc3955c7172c056ec3b2dbb5eeeab6bd48568845eb4729c1` |
| PROJECTION_EQUIVALENCE_INTERPRETATION_V1.json.gz | `d600a3c0785db8acba22cb708013024e773498ecd049981fbe5ec5d4699a3cf9` |
| PROJECTION_EQUIVALENCE_PLAN_V1.json | `3a18a4efb46ee0b7cb5870aaa4bf6a5e1585cedc512eda03e56ef5d3d6b12ac2` |
| PROJECTION_FIXTURE_RAW_V1.json.gz | `13075ac0dc8fbb313438cc25d15f1ea7c69b833d40e231165985d1ac7fd0a8f5` |
| PROJECTION_GATE_SUMMARY_V1.json | `9db841103a0d5e33457ca737997b5e716398b2d0d20fd062e15e0c1ff4d199e6` |
| SUCCESSOR_DECLARATION_V1.json | `236d217212194c00a1b2026c4791aabe6452a2f74b33ee7c7f9125fd13960468` |
| TOOLCHAIN_BINDING_V1.json | `561f369622087563502ea15f0a519902176a2dadb15caa635e84cb3c28099504` |
| canonical_projection_jacobi_v1.cpp | `6f58d7c3bce92228bf8145c67366bf4387900f80608d3c8470c59ca13396f03b` |
| execute_projection_fixtures_v1.py | `d6dfdf25b47a8c53b0c2c9e1e09695cb2b65b2d4b6d99e299a578b02ce3b9a71` |
| interpret_projection_fixtures_v1.py | `400ebef4daeea088aca6d30d90afdfc59a3d58d3016031bb7ab5e8cf4d975f38` |
