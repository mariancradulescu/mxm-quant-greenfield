# MXM R3 — consolidated implementation checkpoint, 20 October 2026

**Not operational acceptance. Not research-capability acceptance. No economic outcome, strategy trial, broker request or order initiated by this repair work.**

Source base: `18e50ab0109f6f7ab80480ead865c5e4ee667337`, existing candidate branch `mxm-p0-integrated-cache-successor-20261020`, existing draft PR #8. R2, OWNER1807, active authority, evidence branch and checkpoint20 have not been changed by this patch.

## 1. Defects repaired in source and locally checked

- A-01/A-02: empty and unilateral cache excluded by inspecting actual rows. Asynchronous bid/ask updates remain separate. Crossed observed books are unresolved. Full coverage/provenance certification remains open.
- A-03: native push distinguishes explicit stale-ref rejection from arbitrary exceptions. Verifier independently reads winner commit/parent/payload, unchanged state, native job and its log. A favorable JSON hash alone no longer suffices.
- A-04/A-05: completion requires exact terminal tasks and complete reason; result/journal identities are bijective. Worker seals global event count/head; cold process checks endpoint, ordering and result hashes. Native A-B-A remains unproven.
- A-06: orphan/closed/mismatched/duplicate financing is refused. Positive and negative financing conserve the account. Closed position IDs cannot be reopened under the same identity.
- A-07: adapter checks feature/decision/entry/exit clocks and observed quote/FX availability; eligible laboratory replay always enables separate strict engine provenance validation. Historical generic account API keeps an explicit compatibility option; it is not an eligible laboratory qualification path without strict mode.
- SEC-03/04: archive maximum sequence and matching receipt protect against ordinary forward-commit rollback; new receipts bind previous public-state hash. R3 admission checks rule properties rather than fixed update timestamps. This is not yet complete sender authentication.
- REC-01/04: filtered, paginated dispatch inventory; one independently proven preclaim-failure retry with stale-parent CAS invalidation. Missing protocol fails closed before legacy writer paths.
- DAT-01/02/03: same-ms side revisions preserved; new cache identities bind trust; general DSL checks bounded staleness. Native receipt trust and specialized DSL paths remain open.
- I-04/SEC-02: native run head must match persisted trigger SHA. Final verifier reads effective rules and source/writer bypass actors, rather than relying on branch `protected` flags alone.

## 2. Operational acceptance

**Not demonstrated.** No R3 workflow installation, checkpoint20 decryption/migration, native fault campaign or certificate was performed. Current rules are insufficient. `main` and execution branch returned empty applied-rule lists; R3 and evidence returned only deletion/non-fast-forward/linear-history. Native ACL, secret isolation, checkout provenance, interrupted-exposure resolution and authentic cold proof remain mandatory.

## 3. Research capability

**Not demonstrated.** No authenticated scale benchmark was possible in this repair environment. Release-backed history, coverage/session witnesses, complete chronological costs/margin/stop-out, shared EUR200 portfolio and deterministic C# parity remain open. Synthetic tests do not measure authentic corpus capacity.

## 4. Scientific/economic progress

**No new result.** Historic budgets, accounting and corpus were preserved. No artificial HARD21 entries, no new strategy family, no LIVE/competition/protected-forward action. Research stays held until both required receptions are proven.

## 5. Access limits and verification

- GitHub connector returned HTTP403 `Resource not accessible by integration` for `branches/main/protection`; its public fetch allowlist also rejected the applied-rules endpoint.
- Direct public authenticated-free GET successfully read `rules/branches/{branch}` and is recorded in `OWNER_CONSOLIDATED_EFFECTIVE_RULES.json`. This supplies observation, not administrative mutation authority.
- No administrative mutation capability for rulesets/environments/secrets is exposed by the connector. A browser fallback requires a separate tool-route permission; it must not be confused with a new B-E mandate or a request for the OWNER to operate GitHub manually.
- Candidate inventory covers 225 workflows, 14 with secret references, 10 without environment and six with contents-write declarations. These are source references, not a claim that the corresponding repository secrets exist or were exposed.
- Before patch: nine adversarial test methods produced 13 expected assertion failures on the audited code. After patch: **160/160 focused tests PASS** (all laboratory modules and account replay tests). Full names and raw results are retained beside this report.
- Broad historic suite: **2304 run; 61 failures, 91 errors, 14 skipped**, 371.179 seconds. Not green. The first immutable-binding failure was independently reproduced on the unmodified audited source; the full unmodified baseline also runs 2304 tests with exactly 61 failures, 91 errors and 14 skips (183.890 seconds). The 152 failing test identities are identical, with no candidate-only failure. Individual historic root causes remain open. No frozen hash has been rewritten to conceal failures.

`OWNER_CONSOLIDATED_REGISTER.json` is the single canonical issue register: 35 rows with aliases from both independent audits, separated into reproduced defects, static findings, risks and missing native evidence. CODE_VERIFIED means source/unit evidence, not full closure. Native proof and administrative acceptance remain outstanding.

## Native source CI evidence

Implementation commit `d971598ca967ee31e40427994706992310b9fb5e` has a successful push-event run [39390365675](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/39390365675), job `118520152533`, attempt 1. Checkout log independently reports that exact SHA; 160 tests passed in 0.855 seconds. The public anchor step confirms checkpoint20/R2/OWNER/active authority and explicitly reports operational acceptance false, R3 migration false and main/execution protected false. Separate PR-merge CI run `39390373684` also succeeded (job `118520175932`); it tests synthetic merge `f178de2f2d0ec1cc6e319d07a4c8877614b5f414`, not the push checkout. Evidence in OWNER_CONSOLIDATED_NATIVE_CI.json distinguishes them.

This documentation successor changes no laboratory or account source code. Native end-to-end deployment and authentic research-capability reception remain unproven.
