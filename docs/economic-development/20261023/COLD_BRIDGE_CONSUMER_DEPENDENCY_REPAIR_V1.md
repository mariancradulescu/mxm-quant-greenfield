# Repair both actual consumers of the cold native bridge

23 October 2026, OWNER B–E continuation. Actual integration failure, not a new scientific trial.

## Observed failure and scope
After PR #136 merged as `050c524eb0845be9345e59fa0e4aad37593c8720`, protected portfolio run `39906330384` succeeded, including captured commission/FX components and independent money checks. The separately triggered full-position lifecycle workflow `39906330328`, job `120259034141`, failed at decryption/export step before its evaluation: `ModuleNotFoundError: No module named 'research_core_v4.laboratory.captured_symbol_terms'`.

PR #134 added that relative import to the current bridge and installed the helper in the portfolio consumer. The lifecycle consumer copied only the bridge into the immutable old source checkout. It also lacked bridge/helper change triggers, so the break stayed dormant until a later product source change. Required CI compiled the product but had not reproduced that consumer's installed import closure. This was an omitted integration path, now corrected.

## Executed correction
Inventory every workflow invoking the bridge: two actual consumers. Install both current bridge and captured-symbol helper in each; retain original immutable decoder checkout and recipient. Add bridge/helper/durable-restoration/source-archive push dependencies to the lifecycle consumer. Replace its expiring source artifact download with the same pinned exact-byte Git restoration already verified by the portfolio route.

The required no-secret gateway now derives missing relative-module dependencies from the copied source AST and each actual workflow's copy commands, checks its change triggers and durable source contract, then installs those exact declared copies in the real sealed checkout and imports the installed package in a separate Python process without PYTHONPATH borrowing. No custody key or fake market source is needed. A negative regression removes the exact helper-copy line that caused the native failure; others remove its trigger or restoration contract. Tests must reject these before any custody key is accessible.

## Acceptance boundaries
Four local contract regressions pass. Native required CI must additionally import both actual installed packages with the sealed source's locked dependencies and compile the actual `.algo`. After protected merge, the corrected lifecycle workflow must perform its real original-ciphertext restoration/export/evaluation and encrypt the bounded result. Do not turn the original failure into SUCCESS by retrying unchanged code or rewriting its history.

This is a dependency/retention integration repair. It does not retune or select an exit policy, create another scientific trial or establish historical costs, execution, HARD21 or DEMO/Cloud recovery. The pre-existing exposed 216-cell exploratory comparison retains its original non-confirmatory classification. No new broker request, market order, provider, credentials, authority, economic identity or OWNER checkpoint change.
