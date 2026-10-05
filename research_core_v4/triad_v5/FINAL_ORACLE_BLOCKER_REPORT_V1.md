# TRIAD V5 exact preoutcome numerical contract: BLOCKED

Starting LIVE HEAD: `4431164ac7b05999bb41230de1804aeeb8350200`. Blocker checkpoint: `f4ec23604f0a58f7fd291515594b4c292d86ab58`. Final report commit/LIVE equality are reported separately; no self-referential commit hash.

Classification: `PREOUTCOME_BLOCKED_IMPLEMENTATION_INDEPENDENT_PROJECTION_CONTRACT_UNCERTIFIED_UNTESTED_NOT_NULL`. Specific first failure: `NUMERICAL_ORACLE_AMBIGUOUS_EIGEN_RECONSTRUCTION`, first frozen fixture `V3_00_n5_eps1.0`.

## Scope and historical preservation

Project frontier 1576; accepted M5 surface145; mechanism-local75 FX;107 complete canonical currency relations.75 FX is NOT a new fixed project universe. No fixed pair, best triad, target, horizon or cohort was selected. The70 other accepted M5 identities and untested frontier remain untested by this currency mechanism, not exhausted or economically null. The FX subset is justified by currency relational algebra only.

All 78 inherited SHA256 bindings reverified after execution. V1/V2/V3/V4 files, science, blockers, protocol/supersession and selectionV6 unchanged. V5 is a new prospective numerical-contract successor, not historical rescue.

- V1: `PREOUTCOME_BLOCKED_INCREMENTAL_ESTIMAND_NOT_IDENTIFIED_UNTESTED_NOT_NULL`; blocker SHA256 `4095666954df6f34aaf8b4d1057a7e66a5b7126f093a18cef02abf108a8b9f9c`.
- V2: `PREOUTCOME_BLOCKED_EXACT_DEPENDENCE_ENVELOPE_INCOMPLETE_CALIBRATION_UNCERTIFIED_UNTESTED_NOT_NULL`; blocker SHA256 `085d8e010b4e02611e3e87797678cf093037b152ae06694cb70e6893b518647e`.
- V3: `PREOUTCOME_BLOCKED_INHERITED_CURRENT_PROJECTION_ADAPTER_NOT_EQUIVALENT_UNCERTIFIED_UNTESTED_NOT_NULL`; blocker SHA256 `1c69c85fcda532e4600dec2f7cdbe1af141364bd84341bd8e130d865f970bad6`.
- V4: `PREOUTCOME_BLOCKED_CANONICAL_PROJECTION_KERNEL_NOT_EQUIVALENT_UNCERTIFIED_UNTESTED_NOT_NULL`; blocker SHA256 `9d69a12670513e8c66e789972cb8f79bbee8f9967b1269154de94fb549e091e5`.

V2 estimand-design SHA256 `39ccec246ed346f86cfd0cfeb74b83d48ec86425b32fd6ba9529b43b67f4b771`: partial-linear incremental predictive information relative to declared common within-cohort/fixed-clock own-leg linear control span. Nuisance90-day chronological matured OLS, midnight updates, maturity/purge, scientific controls,75 FX/21 currencies/107 relations, frozen cohorts,15/30/60/240-minute horizons,12 paid two-sided leaves,105-day halves and leave-out breadth remain unchanged. Semantic PASS is preserved.

## Mathematical contract

Start from exact binary64 X/D values, lifted losslessly. Mathematical column RMS normalization; scale>1e-12; n>=5, exactly3 controls. Mathematical rank count(sigma>1e-12)==3. Pseudoinverse retains sigma>1e-12*sigma_max. RD=D-Z*pinv(Z)*D; RMS>=1e-10; normalizedRD=RD/RMS; no clipping. Finite-precision NumPy acceptance does not define this mathematical projection. Historical orthogonality assert is a numerical reliability check.

## Oracle, implementation and frozen reliability law

Library: Python3.12.14, decimal1.70, libmpdec4.0.0; `_decimal` built into frozen interpreter.100 and160 decimal digits, ROUND_HALF_EVEN. Inputs use Decimal.from_float, never high-precision formula regeneration. Independent symmetric3x3 Gram eigendecomposition occurs in arbitrary precision, with cyclic Jacobi rotations,128 maximum sweeps, eigenvector reconstruction certificate. No binary64 Gram inversion or kernel rewrite.

Stability requires identical rank, retained directions, eligibility, and singular/RMS relative-to-max(1,value) discrepancy<=1e-60; normalizedRD max discrepancy<=1e-60 when mathematically eligible. Frozen oracle criterion: off-diagonal convergence<=10^(-digits+20)*max(1,normG); reconstruction<=10^(-digits+15)*max(1,normG).

New defect in the V5 oracle specification/source: the stopping criterion is looser by a factor100000 than the later reconstruction threshold, so convergence alone cannot guarantee the certificate.30 oracle100 and86 oracle160 reconstructions fail, with116 distinct failed fixture certificates. The first well-conditioned fixture passes at100 digits but fails at160: reconstruction error8.610268769030275582e-142 exceeds its frozen160-digit reconstruction bound. This is failure of the oracle built in this task, not mathematical nonexistence. No oracle-source/specification repair or precision extension occurred after observing results.

On421 fixtures with both internal certificates,100-vs160 eligibility agrees. Maximum singular discrepancy: 3.09142277222806521916603570007776838951329299199540225905513240849217595521001493103919336564235689334328624042459091727221743041232815484131083397217755028711915623447149510836172E-99; maximum eligible normalizedRD discrepancy: 7.6704717195434958737276509662578650932796768902418951950615189912325769082308E-84. The whole oracle gate FAILS; the subset does not certify V5.

Binary64 law frozen before evaluation: u=2^-53; maximum300 rotations; K(n)=3n+6+300*(6n+32)+12n+30; gammaK=K*u/(1-K*u); prospective spectral error radius delta=gammaK*norm(Z,F). Arithmetic budget covers normalization, moments/rotations and projection reductions; its proposed normwise backward bound is checked against the oracle rather than asserted universally. Weyl gives singular perturbation<=delta conditional on the normwise error bound. A complete analytical proof for arbitrary production geometry remains unestablished behind failed oracle gate.

Ambiguity: union of candidate/oracle distances<=2delta from absolute rank threshold and<=2(1+1e-12)delta from relative cutoff; scale threshold has corresponding gamma_(2n+5) interval. Ambiguous geometries fail closed as NUMERICAL_SUPPORT_AMBIGUOUS_UNTESTED_NOT_NULL; ambiguity is never null evidence. Candidate/oracle singular discrepancy must be<=delta; accepted residual reconstructed from normalized*RMS must satisfy max(abs(Z.T*RD))<1e-9*max(1,normD); normalized forward error<=1e-7 and RMS error<=1e-9*max(oracleRMS,1e-10). No post-result tolerance changes.

Unchanged kernel SHA256 `6f58d7c3bce92228bf8145c67366bf4387900f80608d3c8470c59ca13396f03b`. Supplied task digest omitted its last hexadecimal character; this transcription was reconciled with durable source. All537 candidate reexecutions reproduce frozen V4 outputs bit-identically. Compiler g++13.3.0; flags -O3 -std=c++17 -Wall -Wextra -ffp-contract=off; no fast-math.

## Independent V4 diagnosis and complete-suite results

The numerical-authority finding is independently supported on the certified subset:21 of the original34 Python-reject/Jacobi-accept mismatches are also accepted by stable100/160-digit oracle. The remaining original cases are not declared verified if an oracle certificate fails. In particular n11 epsilon1e-7 and1e-8 pass the new comparison; Python rejects them while oracle and Jacobi accept. V4 retains its permanently failed exact Python/C++ eligibility law.

Across421 internally certified fixtures, Python rejects100 oracle mathematically eligible cases (92 nonambiguous). This verifies at least some NumPy rejection is implementation behavior. A limited prospective definition supersession for V5 is persisted; production numerical authority is NOT granted.

Full537 fixture records preserved.116 oracle certificate failures;421 precision-certified records.202 conservative ambiguity rejections within those421;116 unresolved oracle records have no certified ambiguity classification. Raw Jacobi/mathematical-oracle eligibility disagreements79 among certified records;71 remain outside frozen ambiguity after wrapper. They are all candidate rejections of mathematically eligible nonambiguous oracle geometries, including n5 epsilon1e-7 and1e-8.187 fixtures fail at least one frozen gate:116 oracle certificate failures plus71 nonambiguous eligibility disagreements. These secondary diagnostics do not constitute a complete projection certificate.

Maximum production/oracle normalizedRD discrepancy for nonambiguous accepted candidate results with certified oracle: 15.6931178259417937378305753927331291509471830105528424201302449605622331620690734969300464330100818093836498218854440578855776342106114860578756231894347E-9 (target1e-7). No accepted-result forward-error gate failure rescues eligibility mismatches or unresolved oracle certificates.

## Actual geometry and downstream status

Actual predictor-only X/D audit count0; actual mismatches and numerical ambiguity count NOT MEASURED, not zero. Complete-family numerical support NOT RECOMPUTED. Actual audit prohibited because fixture/oracle gate failed.

V5 production numerical authority, V5 certification worker, layer-A exact-path implementation, layer-B DAILY_AR025/DAILY_AR050 law/static proofs, midnight/gap persistence/joint tensor/partial-null proofs, certification plan, null/power trial-count derivation, effect grid, SHA256 seed law, immutable trial manifest, chunk/resume/merge and serial/chunk equivalence: NOT CREATED/NOT EXECUTED; hashes unavailable. No READY authority. Desired layers remain requirements, not implemented claims.

Full null Monte Carlo0; full power Monte Carlo0; real response openings0; future real signed responses0; broker contacts0; historical requests0; new acquisition0; candidate frozen count0; orders0; trading NOT_AUTHORIZED_NOT_EXECUTED; confirmation CLOSED; protected-forward CLOSED; RuntimeV2 READ_ONLY. No source rerank, no depth selection, no same-task repair, no new mechanism.

Unresolved limitations: V5 oracle termination/reconstruction certification failure; candidate support mismatch on certified nonambiguous subset; unestablished complete binary64 backward-error proof; actual support unaudited; dual-layer dependence/FWER/power uncertified; runtime worker/resume architecture unbuilt; no market/economic result. Estimand population remains retained complete-clock observations; missing future paths are not assumed random; historical reception latency unobserved; t-10 availability is a conservative research observation law only.

## Checkpoints through blocker

| Component | HEAD |
|---|---|
| Declare separate TRIAD V5 prospective numerical-contract successor and preserve full universe accounting | `7a0b5128ccc4157308f18106f2aa132d7315ad8c` |
| Freeze TRIAD V5 mathematical projection contract, 100/160-digit oracle, prospective binary64 reliability law and all 537 exact inputs | `db08fa01a12f7cda5c496c328d3de68296df7ffb` |
| Freeze independent decimal oracle source and all-fixture executor before any TRIAD V5 evaluation | `59a866833e7b621642e07e50cc5bad5259edfa17` |
| Persist all 537 TRIAD V5 100/160-digit oracle and unchanged Jacobi raw results before interpretation | `51daaae8cd5578b6f139b8a9f5a711c45491ea08` |
| Persist TRIAD V5 oracle certificate blocker, full interpretation and limited prospective numerical-authority reconciliation without repair | `f4ec23604f0a58f7fd291515594b4c292d86ab58` |

## All537 frozen fixture comparisons

P/J/O denote historical Python, unchanged Jacobi, and oracle160 acceptance. O is authoritative only where both oracle certificates and precision stability pass. FAIL_ORACLE means no certified oracle decision. Numeric diagnostics, full singular values, per-fixture backward errors and exact input hashes are preserved in ORACLE_FIXTURE_RAW_V1.json.gz and ORACLE_FIXTURE_INTERPRETATION_V1.json.gz.

| Fixture | Oracle100/160 certified | P | J | O | Ambiguity | Prospective eligibility match | Max normalizedRD error | Gate |
|---|---|---|---|---|---|---|---|---|
| V3_00_n5_eps1.0 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V3_01_n5_eps0.01 | True | True | True | True | False | True | 5.484073447e-14 | PASS |
| V3_02_n5_eps0.0001 | True | True | True | True | False | True | 2.554914659e-11 | PASS |
| V3_03_n5_eps1e-06 | True | True | True | True | False | True | 5.548193131e-10 | PASS |
| V3_04_n5_eps1e-07 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V3_05_n5_eps1e-08 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V3_06_n10_eps1.0 | True | True | True | True | False | True | 2.718781765e-16 | PASS |
| V3_07_n10_eps0.01 | True | True | True | True | False | True | 1.270609032e-14 | PASS |
| V3_08_n10_eps0.0001 | True | True | True | True | False | True | 9.418274404e-13 | PASS |
| V3_09_n10_eps1e-06 | True | True | True | True | False | True | 1.386908887e-10 | PASS |
| V3_10_n10_eps1e-07 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V3_11_n10_eps1e-08 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V3_12_n11_eps1.0 | True | True | True | True | False | True | 3.593650744e-16 | PASS |
| V3_13_n11_eps0.01 | True | True | True | True | False | True | 4.315972539e-15 | PASS |
| V3_14_n11_eps0.0001 | True | True | True | True | False | True | 8.639357161e-13 | PASS |
| V3_15_n11_eps1e-06 | True | True | True | True | False | True | 1.838158565e-11 | PASS |
| V3_16_n11_eps1e-07 | True | False | True | True | False | True | 5.093376633e-10 | PASS |
| V3_17_n11_eps1e-08 | True | False | True | True | False | True | 1.356989119e-09 | PASS |
| V3_18_n23_eps1.0 | True | True | True | True | False | True | 4.337669114e-16 | PASS |
| V3_19_n23_eps0.01 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V3_20_n23_eps0.0001 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V3_21_n23_eps1e-06 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V3_22_n23_eps1e-07 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V3_23_n23_eps1e-08 | False | False | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n5_eps1.0_base | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n5_eps1.0_reverse_rows | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n5_eps1.0_control_signs_1_minus1_minus1 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n5_eps1.0_raw_scales_1e-6_1e6_3 | True | True | True | True | False | True | 5.549422597e-16 | PASS |
| V4_n5_eps1.0_D_sign_flip | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n5_eps1.0_D_plus_X_times_0.3_minus0.7_0.2 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n5_eps0.01_base | True | True | True | True | False | True | 5.484073447e-14 | PASS |
| V4_n5_eps0.01_reverse_rows | True | True | True | True | False | True | 5.64036126e-14 | PASS |
| V4_n5_eps0.01_control_signs_1_minus1_minus1 | True | True | True | True | False | True | 5.484073447e-14 | PASS |
| V4_n5_eps0.01_raw_scales_1e-6_1e6_3 | True | True | True | True | False | True | 4.225671975e-14 | PASS |
| V4_n5_eps0.01_D_sign_flip | True | True | True | True | False | True | 5.484073447e-14 | PASS |
| V4_n5_eps0.01_D_plus_X_times_0.3_minus0.7_0.2 | True | True | True | True | False | True | 8.706295107e-14 | PASS |
| V4_n5_eps0.0001_base | True | True | True | True | False | True | 2.554914659e-11 | PASS |
| V4_n5_eps0.0001_reverse_rows | True | True | True | True | False | True | 6.679188825e-12 | PASS |
| V4_n5_eps0.0001_control_signs_1_minus1_minus1 | True | True | True | True | False | True | 2.554914659e-11 | PASS |
| V4_n5_eps0.0001_raw_scales_1e-6_1e6_3 | True | True | True | True | False | True | 2.065188711e-11 | PASS |
| V4_n5_eps0.0001_D_sign_flip | True | True | True | True | False | True | 2.554914659e-11 | PASS |
| V4_n5_eps0.0001_D_plus_X_times_0.3_minus0.7_0.2 | True | True | True | True | False | True | 1.458677142e-11 | PASS |
| V4_n5_eps1e-06_base | True | True | True | True | False | True | 5.548193131e-10 | PASS |
| V4_n5_eps1e-06_reverse_rows | True | True | True | True | False | True | 5.548195351e-10 | PASS |
| V4_n5_eps1e-06_control_signs_1_minus1_minus1 | True | True | True | True | False | True | 5.548193131e-10 | PASS |
| V4_n5_eps1e-06_raw_scales_1e-6_1e6_3 | True | True | True | True | False | True | 2.727043854e-10 | PASS |
| V4_n5_eps1e-06_D_sign_flip | True | True | True | True | False | True | 5.548193131e-10 | PASS |
| V4_n5_eps1e-06_D_plus_X_times_0.3_minus0.7_0.2 | True | True | True | True | False | True | 5.846999569e-10 | PASS |
| V4_n5_eps1e-07_base | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n5_eps1e-07_reverse_rows | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n5_eps1e-07_control_signs_1_minus1_minus1 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n5_eps1e-07_raw_scales_1e-6_1e6_3 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n5_eps1e-07_D_sign_flip | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n5_eps1e-07_D_plus_X_times_0.3_minus0.7_0.2 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n5_eps1e-08_base | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n5_eps1e-08_reverse_rows | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n5_eps1e-08_control_signs_1_minus1_minus1 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n5_eps1e-08_raw_scales_1e-6_1e6_3 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n5_eps1e-08_D_sign_flip | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n5_eps1e-08_D_plus_X_times_0.3_minus0.7_0.2 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n5_eps1e-10_base | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n5_eps1e-10_reverse_rows | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n5_eps1e-10_control_signs_1_minus1_minus1 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n5_eps1e-10_raw_scales_1e-6_1e6_3 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n5_eps1e-10_D_sign_flip | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n5_eps1e-10_D_plus_X_times_0.3_minus0.7_0.2 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n5_eps1e-12_base | True | False | False | False | True | True | N/A | PASS |
| V4_n5_eps1e-12_reverse_rows | True | False | False | False | True | True | N/A | PASS |
| V4_n5_eps1e-12_control_signs_1_minus1_minus1 | True | False | False | False | True | True | N/A | PASS |
| V4_n5_eps1e-12_raw_scales_1e-6_1e6_3 | True | False | False | False | True | True | N/A | PASS |
| V4_n5_eps1e-12_D_sign_flip | True | False | False | False | True | True | N/A | PASS |
| V4_n5_eps1e-12_D_plus_X_times_0.3_minus0.7_0.2 | True | False | False | False | True | True | N/A | PASS |
| V4_n5_eps1e-13_base | True | False | False | False | True | True | N/A | PASS |
| V4_n5_eps1e-13_reverse_rows | True | False | False | False | True | True | N/A | PASS |
| V4_n5_eps1e-13_control_signs_1_minus1_minus1 | True | False | False | False | True | True | N/A | PASS |
| V4_n5_eps1e-13_raw_scales_1e-6_1e6_3 | True | False | False | False | True | True | N/A | PASS |
| V4_n5_eps1e-13_D_sign_flip | True | False | False | False | True | True | N/A | PASS |
| V4_n5_eps1e-13_D_plus_X_times_0.3_minus0.7_0.2 | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n5_s2e-12_base | True | False | False | True | True | True | N/A | PASS |
| V4_spectrum_n5_s2e-12_reverse_rows | True | False | False | True | True | True | N/A | PASS |
| V4_spectrum_n5_s2e-12_raw_scales_1e-6_1e6_3 | True | False | False | True | True | True | N/A | PASS |
| V4_spectrum_n5_s2e-12_D_sign_flip | True | False | False | True | True | True | N/A | PASS |
| V4_spectrum_n5_s1.01e-12_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n5_s1.01e-12_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n5_s1.01e-12_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n5_s1.01e-12_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n5_s9.9e-13_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n5_s9.9e-13_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n5_s9.9e-13_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n5_s9.9e-13_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n5_s5e-13_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n5_s5e-13_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n5_s5e-13_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n5_s5e-13_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n5_s1e-13_base | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n5_s1e-13_reverse_rows | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n5_s1e-13_raw_scales_1e-6_1e6_3 | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n5_s1e-13_D_sign_flip | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n5_s0.0_base | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n5_s0.0_reverse_rows | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n5_s0.0_raw_scales_1e-6_1e6_3 | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n5_s0.0_D_sign_flip | True | False | False | False | True | True | N/A | PASS |
| V4_n6_eps1.0_base | True | True | True | True | False | True | 9.298598516e-16 | PASS |
| V4_n6_eps1.0_reverse_rows | True | True | True | True | False | True | 5.421387061e-16 | PASS |
| V4_n6_eps1.0_control_signs_1_minus1_minus1 | True | True | True | True | False | True | 9.298598516e-16 | PASS |
| V4_n6_eps1.0_raw_scales_1e-6_1e6_3 | True | True | True | True | False | True | 5.041918811e-16 | PASS |
| V4_n6_eps1.0_D_sign_flip | True | True | True | True | False | True | 9.298598516e-16 | PASS |
| V4_n6_eps1.0_D_plus_X_times_0.3_minus0.7_0.2 | True | True | True | True | False | True | 2.36312129e-15 | PASS |
| V4_n6_eps1.0_leave_last_target_out_if_n_gt5 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n6_eps0.01_base | True | True | True | True | False | True | 1.100191752e-13 | PASS |
| V4_n6_eps0.01_reverse_rows | True | True | True | True | False | True | 8.052857945e-14 | PASS |
| V4_n6_eps0.01_control_signs_1_minus1_minus1 | True | True | True | True | False | True | 1.100191752e-13 | PASS |
| V4_n6_eps0.01_raw_scales_1e-6_1e6_3 | True | True | True | True | False | True | 1.505225675e-13 | PASS |
| V4_n6_eps0.01_D_sign_flip | True | True | True | True | False | True | 1.100191752e-13 | PASS |
| V4_n6_eps0.01_D_plus_X_times_0.3_minus0.7_0.2 | True | True | True | True | False | True | 1.474079579e-13 | PASS |
| V4_n6_eps0.01_leave_last_target_out_if_n_gt5 | True | True | True | True | False | True | 5.484073447e-14 | PASS |
| V4_n6_eps0.0001_base | True | True | True | True | False | True | 6.209672474e-12 | PASS |
| V4_n6_eps0.0001_reverse_rows | True | True | True | True | False | True | 1.409634296e-11 | PASS |
| V4_n6_eps0.0001_control_signs_1_minus1_minus1 | True | True | True | True | False | True | 6.209672474e-12 | PASS |
| V4_n6_eps0.0001_raw_scales_1e-6_1e6_3 | True | True | True | True | False | True | 3.204504375e-12 | PASS |
| V4_n6_eps0.0001_D_sign_flip | True | True | True | True | False | True | 6.209672474e-12 | PASS |
| V4_n6_eps0.0001_D_plus_X_times_0.3_minus0.7_0.2 | True | True | True | True | False | True | 8.024037267e-12 | PASS |
| V4_n6_eps0.0001_leave_last_target_out_if_n_gt5 | True | True | True | True | False | True | 2.554914659e-11 | PASS |
| V4_n6_eps1e-06_base | True | True | True | True | False | True | 5.918149766e-10 | PASS |
| V4_n6_eps1e-06_reverse_rows | True | False | True | True | False | True | 8.616584783e-10 | PASS |
| V4_n6_eps1e-06_control_signs_1_minus1_minus1 | True | True | True | True | False | True | 5.918149766e-10 | PASS |
| V4_n6_eps1e-06_raw_scales_1e-6_1e6_3 | True | True | True | True | False | True | 7.965531325e-10 | PASS |
| V4_n6_eps1e-06_D_sign_flip | True | True | True | True | False | True | 5.918149766e-10 | PASS |
| V4_n6_eps1e-06_D_plus_X_times_0.3_minus0.7_0.2 | True | False | True | True | False | True | 3.988570191e-10 | PASS |
| V4_n6_eps1e-06_leave_last_target_out_if_n_gt5 | True | True | True | True | False | True | 5.548193131e-10 | PASS |
| V4_n6_eps1e-07_base | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n6_eps1e-07_reverse_rows | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n6_eps1e-07_control_signs_1_minus1_minus1 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n6_eps1e-07_raw_scales_1e-6_1e6_3 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n6_eps1e-07_D_sign_flip | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n6_eps1e-07_D_plus_X_times_0.3_minus0.7_0.2 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n6_eps1e-07_leave_last_target_out_if_n_gt5 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n6_eps1e-08_base | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n6_eps1e-08_reverse_rows | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n6_eps1e-08_control_signs_1_minus1_minus1 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n6_eps1e-08_raw_scales_1e-6_1e6_3 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n6_eps1e-08_D_sign_flip | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n6_eps1e-08_D_plus_X_times_0.3_minus0.7_0.2 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n6_eps1e-08_leave_last_target_out_if_n_gt5 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n6_eps1e-10_base | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n6_eps1e-10_reverse_rows | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n6_eps1e-10_control_signs_1_minus1_minus1 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n6_eps1e-10_raw_scales_1e-6_1e6_3 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n6_eps1e-10_D_sign_flip | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n6_eps1e-10_D_plus_X_times_0.3_minus0.7_0.2 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n6_eps1e-10_leave_last_target_out_if_n_gt5 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n6_eps1e-12_base | True | False | False | False | True | True | N/A | PASS |
| V4_n6_eps1e-12_reverse_rows | True | False | False | False | True | True | N/A | PASS |
| V4_n6_eps1e-12_control_signs_1_minus1_minus1 | True | False | False | False | True | True | N/A | PASS |
| V4_n6_eps1e-12_raw_scales_1e-6_1e6_3 | True | False | False | False | True | True | N/A | PASS |
| V4_n6_eps1e-12_D_sign_flip | True | False | False | False | True | True | N/A | PASS |
| V4_n6_eps1e-12_D_plus_X_times_0.3_minus0.7_0.2 | True | False | False | False | True | True | N/A | PASS |
| V4_n6_eps1e-12_leave_last_target_out_if_n_gt5 | True | False | False | False | True | True | N/A | PASS |
| V4_n6_eps1e-13_base | True | False | False | False | True | True | N/A | PASS |
| V4_n6_eps1e-13_reverse_rows | True | False | False | False | True | True | N/A | PASS |
| V4_n6_eps1e-13_control_signs_1_minus1_minus1 | True | False | False | False | True | True | N/A | PASS |
| V4_n6_eps1e-13_raw_scales_1e-6_1e6_3 | True | False | False | False | True | True | N/A | PASS |
| V4_n6_eps1e-13_D_sign_flip | True | False | False | False | True | True | N/A | PASS |
| V4_n6_eps1e-13_D_plus_X_times_0.3_minus0.7_0.2 | True | False | False | False | True | True | N/A | PASS |
| V4_n6_eps1e-13_leave_last_target_out_if_n_gt5 | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n6_s2e-12_base | True | False | False | True | True | True | N/A | PASS |
| V4_spectrum_n6_s2e-12_reverse_rows | True | False | False | True | True | True | N/A | PASS |
| V4_spectrum_n6_s2e-12_raw_scales_1e-6_1e6_3 | True | False | False | True | True | True | N/A | PASS |
| V4_spectrum_n6_s2e-12_D_sign_flip | True | False | False | True | True | True | N/A | PASS |
| V4_spectrum_n6_s1.01e-12_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n6_s1.01e-12_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n6_s1.01e-12_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n6_s1.01e-12_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n6_s9.9e-13_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n6_s9.9e-13_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n6_s9.9e-13_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n6_s9.9e-13_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n6_s5e-13_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n6_s5e-13_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n6_s5e-13_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n6_s5e-13_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n6_s1e-13_base | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n6_s1e-13_reverse_rows | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n6_s1e-13_raw_scales_1e-6_1e6_3 | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n6_s1e-13_D_sign_flip | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n6_s0.0_base | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n6_s0.0_reverse_rows | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n6_s0.0_raw_scales_1e-6_1e6_3 | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n6_s0.0_D_sign_flip | True | False | False | False | True | True | N/A | PASS |
| V4_n10_eps1.0_base | True | True | True | True | False | True | 2.718781765e-16 | PASS |
| V4_n10_eps1.0_reverse_rows | True | True | True | True | False | True | 2.357424804e-16 | PASS |
| V4_n10_eps1.0_control_signs_1_minus1_minus1 | True | True | True | True | False | True | 2.718781765e-16 | PASS |
| V4_n10_eps1.0_raw_scales_1e-6_1e6_3 | True | True | True | True | False | True | 3.603832088e-16 | PASS |
| V4_n10_eps1.0_D_sign_flip | True | True | True | True | False | True | 2.718781765e-16 | PASS |
| V4_n10_eps1.0_D_plus_X_times_0.3_minus0.7_0.2 | True | True | True | True | False | True | 4.710072157e-16 | PASS |
| V4_n10_eps1.0_leave_last_target_out_if_n_gt5 | True | True | True | True | False | True | 3.990658465e-16 | PASS |
| V4_n10_eps0.01_base | True | True | True | True | False | True | 1.270609032e-14 | PASS |
| V4_n10_eps0.01_reverse_rows | True | True | True | True | False | True | 1.155996021e-14 | PASS |
| V4_n10_eps0.01_control_signs_1_minus1_minus1 | True | True | True | True | False | True | 1.270609032e-14 | PASS |
| V4_n10_eps0.01_raw_scales_1e-6_1e6_3 | True | True | True | True | False | True | 1.366783238e-14 | PASS |
| V4_n10_eps0.01_D_sign_flip | True | True | True | True | False | True | 1.270609032e-14 | PASS |
| V4_n10_eps0.01_D_plus_X_times_0.3_minus0.7_0.2 | True | True | True | True | False | True | 1.383910811e-14 | PASS |
| V4_n10_eps0.01_leave_last_target_out_if_n_gt5 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n10_eps0.0001_base | True | True | True | True | False | True | 9.418274404e-13 | PASS |
| V4_n10_eps0.0001_reverse_rows | True | True | True | True | False | True | 6.266280646e-13 | PASS |
| V4_n10_eps0.0001_control_signs_1_minus1_minus1 | True | True | True | True | False | True | 9.418274404e-13 | PASS |
| V4_n10_eps0.0001_raw_scales_1e-6_1e6_3 | True | True | True | True | False | True | 1.506314813e-12 | PASS |
| V4_n10_eps0.0001_D_sign_flip | True | True | True | True | False | True | 9.418274404e-13 | PASS |
| V4_n10_eps0.0001_D_plus_X_times_0.3_minus0.7_0.2 | True | True | True | True | False | True | 8.240612797e-13 | PASS |
| V4_n10_eps0.0001_leave_last_target_out_if_n_gt5 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n10_eps1e-06_base | True | True | True | True | False | True | 1.386908887e-10 | PASS |
| V4_n10_eps1e-06_reverse_rows | True | True | True | True | False | True | 1.728336365e-10 | PASS |
| V4_n10_eps1e-06_control_signs_1_minus1_minus1 | True | True | True | True | False | True | 1.386908887e-10 | PASS |
| V4_n10_eps1e-06_raw_scales_1e-6_1e6_3 | True | True | True | True | False | True | 1.837825203e-10 | PASS |
| V4_n10_eps1e-06_D_sign_flip | True | True | True | True | False | True | 1.386908887e-10 | PASS |
| V4_n10_eps1e-06_D_plus_X_times_0.3_minus0.7_0.2 | True | True | True | True | False | True | 5.291720916e-11 | PASS |
| V4_n10_eps1e-06_leave_last_target_out_if_n_gt5 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n10_eps1e-07_base | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n10_eps1e-07_reverse_rows | True | False | True | True | False | True | 1.119324351e-09 | PASS |
| V4_n10_eps1e-07_control_signs_1_minus1_minus1 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n10_eps1e-07_raw_scales_1e-6_1e6_3 | True | False | True | True | False | True | 7.383557725e-10 | PASS |
| V4_n10_eps1e-07_D_sign_flip | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n10_eps1e-07_D_plus_X_times_0.3_minus0.7_0.2 | True | False | True | True | False | True | 1.709057067e-09 | PASS |
| V4_n10_eps1e-07_leave_last_target_out_if_n_gt5 | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n10_eps1e-08_base | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n10_eps1e-08_reverse_rows | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n10_eps1e-08_control_signs_1_minus1_minus1 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n10_eps1e-08_raw_scales_1e-6_1e6_3 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n10_eps1e-08_D_sign_flip | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n10_eps1e-08_D_plus_X_times_0.3_minus0.7_0.2 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n10_eps1e-08_leave_last_target_out_if_n_gt5 | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n10_eps1e-10_base | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n10_eps1e-10_reverse_rows | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n10_eps1e-10_control_signs_1_minus1_minus1 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n10_eps1e-10_raw_scales_1e-6_1e6_3 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n10_eps1e-10_D_sign_flip | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n10_eps1e-10_D_plus_X_times_0.3_minus0.7_0.2 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n10_eps1e-10_leave_last_target_out_if_n_gt5 | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n10_eps1e-12_base | True | True | True | True | True | True | N/A | PASS |
| V4_n10_eps1e-12_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_n10_eps1e-12_control_signs_1_minus1_minus1 | True | True | True | True | True | True | N/A | PASS |
| V4_n10_eps1e-12_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_n10_eps1e-12_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_n10_eps1e-12_D_plus_X_times_0.3_minus0.7_0.2 | True | True | True | True | True | True | N/A | PASS |
| V4_n10_eps1e-12_leave_last_target_out_if_n_gt5 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n10_eps1e-13_base | True | False | False | False | True | True | N/A | PASS |
| V4_n10_eps1e-13_reverse_rows | True | False | False | False | True | True | N/A | PASS |
| V4_n10_eps1e-13_control_signs_1_minus1_minus1 | True | False | False | False | True | True | N/A | PASS |
| V4_n10_eps1e-13_raw_scales_1e-6_1e6_3 | True | False | False | False | True | True | N/A | PASS |
| V4_n10_eps1e-13_D_sign_flip | True | False | False | False | True | True | N/A | PASS |
| V4_n10_eps1e-13_D_plus_X_times_0.3_minus0.7_0.2 | True | False | False | False | True | True | N/A | PASS |
| V4_n10_eps1e-13_leave_last_target_out_if_n_gt5 | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_spectrum_n10_s2e-12_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n10_s2e-12_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n10_s2e-12_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n10_s2e-12_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n10_s1.01e-12_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n10_s1.01e-12_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n10_s1.01e-12_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n10_s1.01e-12_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n10_s9.9e-13_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n10_s9.9e-13_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n10_s9.9e-13_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n10_s9.9e-13_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n10_s5e-13_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n10_s5e-13_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n10_s5e-13_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n10_s5e-13_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n10_s1e-13_base | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n10_s1e-13_reverse_rows | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n10_s1e-13_raw_scales_1e-6_1e6_3 | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n10_s1e-13_D_sign_flip | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n10_s0.0_base | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n10_s0.0_reverse_rows | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n10_s0.0_raw_scales_1e-6_1e6_3 | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n10_s0.0_D_sign_flip | True | False | False | False | True | True | N/A | PASS |
| V4_n11_eps1.0_base | True | True | True | True | False | True | 3.593650744e-16 | PASS |
| V4_n11_eps1.0_reverse_rows | True | True | True | True | False | True | 2.307878019e-16 | PASS |
| V4_n11_eps1.0_control_signs_1_minus1_minus1 | True | True | True | True | False | True | 3.593650744e-16 | PASS |
| V4_n11_eps1.0_raw_scales_1e-6_1e6_3 | True | True | True | True | False | True | 1.952802127e-16 | PASS |
| V4_n11_eps1.0_D_sign_flip | True | True | True | True | False | True | 3.593650744e-16 | PASS |
| V4_n11_eps1.0_D_plus_X_times_0.3_minus0.7_0.2 | True | True | True | True | False | True | 8.444196557e-16 | PASS |
| V4_n11_eps1.0_leave_last_target_out_if_n_gt5 | True | True | True | True | False | True | 2.718781765e-16 | PASS |
| V4_n11_eps0.01_base | True | True | True | True | False | True | 4.315972539e-15 | PASS |
| V4_n11_eps0.01_reverse_rows | True | True | True | True | False | True | 1.429392675e-15 | PASS |
| V4_n11_eps0.01_control_signs_1_minus1_minus1 | True | True | True | True | False | True | 4.315972539e-15 | PASS |
| V4_n11_eps0.01_raw_scales_1e-6_1e6_3 | True | True | True | True | False | True | 3.785480848e-15 | PASS |
| V4_n11_eps0.01_D_sign_flip | True | True | True | True | False | True | 4.315972539e-15 | PASS |
| V4_n11_eps0.01_D_plus_X_times_0.3_minus0.7_0.2 | True | True | True | True | False | True | 4.083041784e-15 | PASS |
| V4_n11_eps0.01_leave_last_target_out_if_n_gt5 | True | True | True | True | False | True | 1.270609032e-14 | PASS |
| V4_n11_eps0.0001_base | True | True | True | True | False | True | 8.639357161e-13 | PASS |
| V4_n11_eps0.0001_reverse_rows | True | True | True | True | False | True | 1.018093554e-12 | PASS |
| V4_n11_eps0.0001_control_signs_1_minus1_minus1 | True | True | True | True | False | True | 8.639357161e-13 | PASS |
| V4_n11_eps0.0001_raw_scales_1e-6_1e6_3 | True | True | True | True | False | True | 8.397442087e-13 | PASS |
| V4_n11_eps0.0001_D_sign_flip | True | True | True | True | False | True | 8.639357161e-13 | PASS |
| V4_n11_eps0.0001_D_plus_X_times_0.3_minus0.7_0.2 | True | True | True | True | False | True | 8.864193859e-13 | PASS |
| V4_n11_eps0.0001_leave_last_target_out_if_n_gt5 | True | True | True | True | False | True | 9.418274404e-13 | PASS |
| V4_n11_eps1e-06_base | True | True | True | True | False | True | 1.838158565e-11 | PASS |
| V4_n11_eps1e-06_reverse_rows | True | True | True | True | False | True | 2.836647305e-11 | PASS |
| V4_n11_eps1e-06_control_signs_1_minus1_minus1 | True | True | True | True | False | True | 1.838158565e-11 | PASS |
| V4_n11_eps1e-06_raw_scales_1e-6_1e6_3 | True | True | True | True | False | True | 1.370323204e-11 | PASS |
| V4_n11_eps1e-06_D_sign_flip | True | True | True | True | False | True | 1.838158565e-11 | PASS |
| V4_n11_eps1e-06_D_plus_X_times_0.3_minus0.7_0.2 | True | True | True | True | False | True | 2.056584811e-11 | PASS |
| V4_n11_eps1e-06_leave_last_target_out_if_n_gt5 | True | True | True | True | False | True | 1.386908887e-10 | PASS |
| V4_n11_eps1e-07_base | True | False | True | True | False | True | 5.093376633e-10 | PASS |
| V4_n11_eps1e-07_reverse_rows | True | False | True | True | False | True | 1.191297747e-09 | PASS |
| V4_n11_eps1e-07_control_signs_1_minus1_minus1 | True | False | True | True | False | True | 5.093376633e-10 | PASS |
| V4_n11_eps1e-07_raw_scales_1e-6_1e6_3 | True | False | True | True | False | True | 3.096070039e-10 | PASS |
| V4_n11_eps1e-07_D_sign_flip | True | False | True | True | False | True | 5.093376633e-10 | PASS |
| V4_n11_eps1e-07_D_plus_X_times_0.3_minus0.7_0.2 | True | True | True | True | False | True | 5.286784766e-10 | PASS |
| V4_n11_eps1e-07_leave_last_target_out_if_n_gt5 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n11_eps1e-08_base | True | False | True | True | False | True | 1.356989119e-09 | PASS |
| V4_n11_eps1e-08_reverse_rows | True | False | True | True | False | True | 1.344360002e-08 | PASS |
| V4_n11_eps1e-08_control_signs_1_minus1_minus1 | True | False | True | True | False | True | 1.356989119e-09 | PASS |
| V4_n11_eps1e-08_raw_scales_1e-6_1e6_3 | True | False | True | True | False | True | 1.569311783e-08 | PASS |
| V4_n11_eps1e-08_D_sign_flip | True | False | True | True | False | True | 1.356989119e-09 | PASS |
| V4_n11_eps1e-08_D_plus_X_times_0.3_minus0.7_0.2 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n11_eps1e-08_leave_last_target_out_if_n_gt5 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n11_eps1e-10_base | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n11_eps1e-10_reverse_rows | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n11_eps1e-10_control_signs_1_minus1_minus1 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n11_eps1e-10_raw_scales_1e-6_1e6_3 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n11_eps1e-10_D_sign_flip | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n11_eps1e-10_D_plus_X_times_0.3_minus0.7_0.2 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n11_eps1e-10_leave_last_target_out_if_n_gt5 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n11_eps1e-12_base | True | True | True | True | True | True | N/A | PASS |
| V4_n11_eps1e-12_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_n11_eps1e-12_control_signs_1_minus1_minus1 | True | True | True | True | True | True | N/A | PASS |
| V4_n11_eps1e-12_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_n11_eps1e-12_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_n11_eps1e-12_D_plus_X_times_0.3_minus0.7_0.2 | True | True | True | True | True | True | N/A | PASS |
| V4_n11_eps1e-12_leave_last_target_out_if_n_gt5 | True | True | True | True | True | True | N/A | PASS |
| V4_n11_eps1e-13_base | True | False | False | False | True | True | N/A | PASS |
| V4_n11_eps1e-13_reverse_rows | True | False | False | False | True | True | N/A | PASS |
| V4_n11_eps1e-13_control_signs_1_minus1_minus1 | True | False | False | False | True | True | N/A | PASS |
| V4_n11_eps1e-13_raw_scales_1e-6_1e6_3 | True | False | False | False | True | True | N/A | PASS |
| V4_n11_eps1e-13_D_sign_flip | True | False | False | False | True | True | N/A | PASS |
| V4_n11_eps1e-13_D_plus_X_times_0.3_minus0.7_0.2 | True | False | False | False | True | True | N/A | PASS |
| V4_n11_eps1e-13_leave_last_target_out_if_n_gt5 | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n11_s2e-12_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n11_s2e-12_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n11_s2e-12_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n11_s2e-12_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n11_s1.01e-12_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n11_s1.01e-12_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n11_s1.01e-12_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n11_s1.01e-12_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n11_s9.9e-13_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n11_s9.9e-13_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n11_s9.9e-13_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n11_s9.9e-13_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n11_s5e-13_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n11_s5e-13_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n11_s5e-13_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n11_s5e-13_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n11_s1e-13_base | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n11_s1e-13_reverse_rows | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n11_s1e-13_raw_scales_1e-6_1e6_3 | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n11_s1e-13_D_sign_flip | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n11_s0.0_base | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n11_s0.0_reverse_rows | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n11_s0.0_raw_scales_1e-6_1e6_3 | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n11_s0.0_D_sign_flip | True | False | False | False | True | True | N/A | PASS |
| V4_n22_eps1.0_base | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1.0_reverse_rows | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1.0_control_signs_1_minus1_minus1 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1.0_raw_scales_1e-6_1e6_3 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1.0_D_sign_flip | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1.0_D_plus_X_times_0.3_minus0.7_0.2 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1.0_leave_last_target_out_if_n_gt5 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps0.01_base | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps0.01_reverse_rows | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps0.01_control_signs_1_minus1_minus1 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps0.01_raw_scales_1e-6_1e6_3 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps0.01_D_sign_flip | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps0.01_D_plus_X_times_0.3_minus0.7_0.2 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps0.01_leave_last_target_out_if_n_gt5 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps0.0001_base | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps0.0001_reverse_rows | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps0.0001_control_signs_1_minus1_minus1 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps0.0001_raw_scales_1e-6_1e6_3 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps0.0001_D_sign_flip | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps0.0001_D_plus_X_times_0.3_minus0.7_0.2 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps0.0001_leave_last_target_out_if_n_gt5 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-06_base | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-06_reverse_rows | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-06_control_signs_1_minus1_minus1 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-06_raw_scales_1e-6_1e6_3 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-06_D_sign_flip | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-06_D_plus_X_times_0.3_minus0.7_0.2 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-06_leave_last_target_out_if_n_gt5 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-07_base | False | False | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-07_reverse_rows | False | False | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-07_control_signs_1_minus1_minus1 | False | False | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-07_raw_scales_1e-6_1e6_3 | False | False | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-07_D_sign_flip | False | False | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-07_D_plus_X_times_0.3_minus0.7_0.2 | False | False | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-07_leave_last_target_out_if_n_gt5 | False | False | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-08_base | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-08_reverse_rows | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-08_control_signs_1_minus1_minus1 | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-08_raw_scales_1e-6_1e6_3 | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-08_D_sign_flip | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-08_D_plus_X_times_0.3_minus0.7_0.2 | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-08_leave_last_target_out_if_n_gt5 | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-10_base | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-10_reverse_rows | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-10_control_signs_1_minus1_minus1 | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-10_raw_scales_1e-6_1e6_3 | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-10_D_sign_flip | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-10_D_plus_X_times_0.3_minus0.7_0.2 | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-10_leave_last_target_out_if_n_gt5 | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-12_base | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-12_reverse_rows | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-12_control_signs_1_minus1_minus1 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-12_raw_scales_1e-6_1e6_3 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-12_D_sign_flip | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-12_D_plus_X_times_0.3_minus0.7_0.2 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-12_leave_last_target_out_if_n_gt5 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-13_base | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-13_reverse_rows | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-13_control_signs_1_minus1_minus1 | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-13_raw_scales_1e-6_1e6_3 | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-13_D_sign_flip | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-13_D_plus_X_times_0.3_minus0.7_0.2 | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n22_eps1e-13_leave_last_target_out_if_n_gt5 | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_spectrum_n22_s2e-12_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n22_s2e-12_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n22_s2e-12_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n22_s2e-12_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n22_s1.01e-12_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n22_s1.01e-12_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n22_s1.01e-12_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n22_s1.01e-12_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n22_s9.9e-13_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n22_s9.9e-13_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n22_s9.9e-13_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n22_s9.9e-13_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n22_s5e-13_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n22_s5e-13_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n22_s5e-13_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n22_s5e-13_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n22_s1e-13_base | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n22_s1e-13_reverse_rows | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n22_s1e-13_raw_scales_1e-6_1e6_3 | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n22_s1e-13_D_sign_flip | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n22_s0.0_base | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n22_s0.0_reverse_rows | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n22_s0.0_raw_scales_1e-6_1e6_3 | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n22_s0.0_D_sign_flip | True | False | False | False | True | True | N/A | PASS |
| V4_n23_eps1.0_base | True | True | True | True | False | True | 4.337669114e-16 | PASS |
| V4_n23_eps1.0_reverse_rows | True | True | True | True | False | True | 4.287147631e-16 | PASS |
| V4_n23_eps1.0_control_signs_1_minus1_minus1 | True | True | True | True | False | True | 4.337669114e-16 | PASS |
| V4_n23_eps1.0_raw_scales_1e-6_1e6_3 | True | True | True | True | False | True | 3.532495135e-16 | PASS |
| V4_n23_eps1.0_D_sign_flip | True | True | True | True | False | True | 4.337669114e-16 | PASS |
| V4_n23_eps1.0_D_plus_X_times_0.3_minus0.7_0.2 | True | True | True | True | False | True | 5.614395708e-16 | PASS |
| V4_n23_eps1.0_leave_last_target_out_if_n_gt5 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps0.01_base | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps0.01_reverse_rows | True | True | True | True | False | True | 5.713583985e-16 | PASS |
| V4_n23_eps0.01_control_signs_1_minus1_minus1 | True | True | True | True | False | True | 1.693575103e-15 | PASS |
| V4_n23_eps0.01_raw_scales_1e-6_1e6_3 | True | True | True | True | False | True | 1.375999666e-15 | PASS |
| V4_n23_eps0.01_D_sign_flip | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps0.01_D_plus_X_times_0.3_minus0.7_0.2 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps0.01_leave_last_target_out_if_n_gt5 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps0.0001_base | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps0.0001_reverse_rows | True | True | True | True | False | True | 2.019004664e-13 | PASS |
| V4_n23_eps0.0001_control_signs_1_minus1_minus1 | True | True | True | True | False | True | 3.834091121e-13 | PASS |
| V4_n23_eps0.0001_raw_scales_1e-6_1e6_3 | True | True | True | True | False | True | 2.997547859e-13 | PASS |
| V4_n23_eps0.0001_D_sign_flip | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps0.0001_D_plus_X_times_0.3_minus0.7_0.2 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps0.0001_leave_last_target_out_if_n_gt5 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-06_base | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-06_reverse_rows | True | True | True | True | False | True | 5.889283754e-11 | PASS |
| V4_n23_eps1e-06_control_signs_1_minus1_minus1 | True | True | True | True | False | True | 1.59814964e-11 | PASS |
| V4_n23_eps1e-06_raw_scales_1e-6_1e6_3 | True | True | True | True | False | True | 1.561738018e-11 | PASS |
| V4_n23_eps1e-06_D_sign_flip | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-06_D_plus_X_times_0.3_minus0.7_0.2 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-06_leave_last_target_out_if_n_gt5 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-07_base | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-07_reverse_rows | True | False | True | True | False | True | 7.336732193e-10 | PASS |
| V4_n23_eps1e-07_control_signs_1_minus1_minus1 | True | True | True | True | False | True | 6.708256033e-10 | PASS |
| V4_n23_eps1e-07_raw_scales_1e-6_1e6_3 | True | True | True | True | False | True | 4.792107089e-10 | PASS |
| V4_n23_eps1e-07_D_sign_flip | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-07_D_plus_X_times_0.3_minus0.7_0.2 | False | False | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-07_leave_last_target_out_if_n_gt5 | False | False | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-08_base | False | False | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-08_reverse_rows | True | False | True | True | False | True | 7.395646872e-10 | PASS |
| V4_n23_eps1e-08_control_signs_1_minus1_minus1 | True | False | True | True | False | True | 6.508225427e-10 | PASS |
| V4_n23_eps1e-08_raw_scales_1e-6_1e6_3 | True | False | True | True | False | True | 2.568916538e-09 | PASS |
| V4_n23_eps1e-08_D_sign_flip | False | False | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-08_D_plus_X_times_0.3_minus0.7_0.2 | False | False | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-08_leave_last_target_out_if_n_gt5 | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-10_base | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-10_reverse_rows | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n23_eps1e-10_control_signs_1_minus1_minus1 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n23_eps1e-10_raw_scales_1e-6_1e6_3 | True | False | False | True | False | False | N/A | NONAMBIGUOUS_PRODUCTION_ORACLE_ELIGIBILITY_MISMATCH |
| V4_n23_eps1e-10_D_sign_flip | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-10_D_plus_X_times_0.3_minus0.7_0.2 | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-10_leave_last_target_out_if_n_gt5 | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-12_base | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-12_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_n23_eps1e-12_control_signs_1_minus1_minus1 | True | True | True | True | True | True | N/A | PASS |
| V4_n23_eps1e-12_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_n23_eps1e-12_D_sign_flip | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-12_D_plus_X_times_0.3_minus0.7_0.2 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-12_leave_last_target_out_if_n_gt5 | False | True | True | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-13_base | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-13_reverse_rows | True | False | False | False | True | True | N/A | PASS |
| V4_n23_eps1e-13_control_signs_1_minus1_minus1 | True | False | False | False | True | True | N/A | PASS |
| V4_n23_eps1e-13_raw_scales_1e-6_1e6_3 | True | False | False | False | True | True | N/A | PASS |
| V4_n23_eps1e-13_D_sign_flip | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-13_D_plus_X_times_0.3_minus0.7_0.2 | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_n23_eps1e-13_leave_last_target_out_if_n_gt5 | False | False | False | UNRESOLVED | UNRESOLVED | UNRESOLVED | N/A | NUMERICAL_ORACLE_AMBIGUOUS |
| V4_spectrum_n23_s2e-12_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n23_s2e-12_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n23_s2e-12_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n23_s2e-12_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n23_s1.01e-12_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n23_s1.01e-12_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n23_s1.01e-12_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n23_s1.01e-12_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n23_s9.9e-13_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n23_s9.9e-13_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n23_s9.9e-13_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n23_s9.9e-13_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n23_s5e-13_base | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n23_s5e-13_reverse_rows | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n23_s5e-13_raw_scales_1e-6_1e6_3 | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n23_s5e-13_D_sign_flip | True | True | True | True | True | True | N/A | PASS |
| V4_spectrum_n23_s1e-13_base | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n23_s1e-13_reverse_rows | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n23_s1e-13_raw_scales_1e-6_1e6_3 | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n23_s1e-13_D_sign_flip | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n23_s0.0_base | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n23_s0.0_reverse_rows | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n23_s0.0_raw_scales_1e-6_1e6_3 | True | False | False | False | True | True | N/A | PASS |
| V4_spectrum_n23_s0.0_D_sign_flip | True | False | False | False | True | True | N/A | PASS |

## Artifact SHA256 bindings

| Artifact | SHA256 |
|---|---|
| TRIAD_RELATIONAL_STATE_V5_PREOUTCOME_BLOCKER_V1.json | `3211db8d9246ab79578c4401841625f4e6ac7c9272e980036d056c74f006f2e4` |
| BINARY64_RELIABILITY_LAW_V1.json | `a7d39e862d5f8d4b8f0d9da7cfc911be867e1bc3a1167abb2d5105b2de1b1b43` |
| CHECKPOINTS_THROUGH_BLOCKER_V1.json | `7708933438f4914feb0ef00f0baa77c935541e8736a2afd3d637ace9c5ada2f3` |
| FROZEN_INPUT_MANIFEST_V1.json | `c405146305dd2de8fcf6f91b82eca6600791decc6862ea58199b34b914666f1c` |
| HIGH_PRECISION_ORACLE_SPEC_V1.json | `69e414eea12bc419112c6484bcad4bee9fec08c4e45807dee41a2d4dd09afb1c` |
| INHERITED_IMMUTABLE_BINDINGS_V1.json | `aecc0e86ed3d09fb8c32323f810c9372a86c40d4df9f31eb36a545fea73a57fa` |
| MATHEMATICAL_PROJECTION_CONTRACT_V1.json | `9854786a05190ec593e5ee1f94b9771ea3d59abdabb0ab6defaa9e7894c92c36` |
| NUMERICAL_AUTHORITY_GOVERNANCE_RECONCILIATION_V1.json | `fd1b21a10358415792e64f9be44dccdff763f9ce43583cf9a3007fb56006e74c` |
| ORACLE_FIXTURE_INTERPRETATION_V1.json.gz | `33d51a465354f903cb345eafc747c64df5db35ef0e0181fde1945f3dd5dbd711` |
| ORACLE_FIXTURE_RAW_V1.json.gz | `10e885f37229d2fe5ec68043f478cace88d0827215e87cfe6219a8631f662122` |
| ORACLE_GATE_SUMMARY_V1.json | `b6533cc6099ba652e2af644d1de51cdb3a3c09c6f46e609c309f843300e1bee9` |
| ORACLE_TOOLCHAIN_BINDING_V1.json | `2e59b652061c0fba880eeaf79153b96cf2f2f137cac632f586d8c3cb334de87b` |
| SUCCESSOR_DECLARATION_V1.json | `062448873ab8fe2080cbe26edf31969524bbf535d7441af8ffc890cd3182bbad` |
| UNCHANGED_CANDIDATE_BINDING_V1.json | `e119ea99071ffa6261680fd2bb7d51dedd3f47d25fd5b989a58c0d2fb68b8f80` |
| execute_frozen_fixture_oracles_v1.py | `c93990f3ff87d30639ae425a90c960f2fa24bb07d3593fd7046e668d15758a95` |
| high_precision_projection_oracle_v1.py | `545b72d88616dfd7f00b7b3653c3119e8ea2b3368e4de9411b8204dbdc3dc390` |
| interpret_oracle_fixture_gate_v1.py | `46690e057ce976cb2d2c9e9befa8a584097b33aac974a8fb671737c4ee117398` |
