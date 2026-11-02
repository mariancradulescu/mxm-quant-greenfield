# MXM operational isolation — reception gate 1

This branch isolates the execution **plane**, not the project or history. All
322 historical workflow definitions remain in the protected official branch
and full commit history. Only `.github/workflows/mxm-runtime.yml` is active on
this branch. The original code, Pepperstone read-only transport and protobuf,
encrypted custody helpers, native EUR200 C# engine and single cTrader Cloud bot
are reused without modification.

The first workflow is deliberately **source-blind**: no repository or environment
secrets are requested or read, no market data is collected, and no order or
Cloud action is possible. Failures require investigation before adding a
separate collection job to the *same* workflow. This validation does not reset
any historical `first-only` guard.

## Reception sequence

1. Verify this branch retains only one active workflow and the source-blind job
   runs (not merely YAML merger approval). Confirm local YAML parse and schema.
2. Introduce a per-operation immutable authorized JSON contract with a unique
   identity, bounded UTC window, one LIVE VIEW broker and capped requests. A
   repeated contract must be rejected before any secret is exposed.
3. Only after a passing preflight, add secret-gated read-only collection to this
   **same** workflow; preserve environment protections. Reuse the original
   transport, market decoders, encrypted original custody, shared-funded C#
   engine, cash ledger verifier, and audit SHA chain. Never write credentials
   to files, logs or code.
4. Prove original-to-C# event/ledger provenance; keep source reception distinct
   from economic alpha certification. Hold Cloud execution and all broker orders.

Operating limits: one EUR200 account, maximum 2 EUR entry risk, 80 EUR total
margin, 120 EUR reserve. HARD21 remains a *system-level* objective, not a
forced-entry requirement. No historical economic trial is reopened.
