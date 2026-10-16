# Future issuer — DISABLED_NO_GO v1

This is a versioned inactive boundary, not an operational issuer or a bootstrap implementation. `issue_token`, `bootstrap`, and `accept_checkpoint` unconditionally raise. No network, signing, credential loading, staging environment, App key reference, OIDC or token minting is implemented here. Configuration drift is rejected. Changing the config cannot implement the missing real backend.

The previous synthetic transition model and its29 accepted tests remain at `research_core_v4/p0_transition_20261016/`; they are not rerun or promoted to a real trust root. Its synthetic signatures are not auditor receipts.

## Required future integration contract, not enabled

1. Freeze/review exact issuer source, dependencies, workflow and disabled-to-enabled config; bind their SHA256 and Git OIDs in independently accepted receipts. Select a dedicated issuer principal and repository installation explicitly. Staging App5343530 and its environment are not assigned to this authority.
2. Preserve OWNER1807 as the immutable historical baseline, never rewrite it. A future separately authorized bootstrap must bind repository ID1374181010, exact active ref, expected ABSENT state, candidate OID/tree, baseline OWNER OID/generation/manifest hash, policy/ruleset digests, principal/installation IDs, epoch, single-use intent, expiry, operation and source SHA. No wildcard or fallback authority.
3. Verify real OWNER and independent auditor approvals through separately controlled trust roots. This repository currently provisions neither auditor principal nor key. Refuse missing, expired, replayed, wrong-scope or revoked receipts. An acceptance of preparation/staging is never a real bootstrap approval.
4. Require a native atomic Git ref transaction with exact expected oldOID (or ABSENT for explicitly authorized creation), one parent equal to the accepted predecessor, fast-forward/linear history and unchanged effective policies. A GET followed by REST PATCH is not proof of atomic compare-and-swap. The earlier bare-Git synthetic CAS model is not a deployed GitHub transport.
5. Reconcile lost acknowledgement by GET only against the exact intent/candidate. No automatic retry, ref reconstruction, alternate release/tag/branch fallback or second writer. A readable release body or valid ciphertext alone cannot authorize acceptance.
6. Define repository-wide residual Contents-write exposure and historical consumer supersession before giving any issuer bypass on the exact rule. GitHub App Contents-write is not itself a per-ref credential scope. Ruleset25268790 currently has zero bypass and must remain so under this mandate. No administrative capability is delegated to issuer code.
7. Deliver durable sanitized receipts and encrypted confidential evidence before independent reception. Any future GO is a separate OWNER decision; this design grants none.

## Narrow proof machinery

Run38954973739, tested source7af72e8ec1bb761b322e18c44ee9a24c01d256ab: eight new inactive-boundary tests passed. OnePOST targeted only `refs/heads/mxm-o04-synthetic-deny-20261016-v1` under ruleset25268949, candidate tree containing solely SYNTHETIC_ONLY.json. HTTP422 rejected it; both refs stayed absent. The run is **failure** because the generic response did not satisfy the stricter rule-specific-message assertion. Do not reinterpret it as SUCCESS or rerun the POST to improve the label. Native update rejection was not tested.

The proof workflow is subsequently disabled with a literal false job condition. Its final disabled workflow is a configuration change, not the workflow version executed by that run. The inactive issuer module/config/tests are unchanged from tested source. No workflow invokes a future real issuer. See canonical report for limits and native evidence.
