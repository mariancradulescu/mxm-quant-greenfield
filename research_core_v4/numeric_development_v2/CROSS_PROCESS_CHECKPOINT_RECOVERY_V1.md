# Cross-process checkpoint recovery V1

Exact source: `7006a86c4a3a97bb2193d3c4527251e34f769333`.
The machine proof uses only fabricated payloads with all1576 identities and
all three lags. Its56-bar-per-segment boundary fixture has352800 rows, compared
with655200 in the preserved earlier full synthetic run. It is a new bounded
recovery fixture, not a replay of the old campaign.

The first actual worker writes encrypted25/50-shard checkpoints and authenticated
remote receipts, marks interruption durably, then terminates with os._exit(75).
The next workers start from a fresh interpreter without an old engine object.
They fetch and validate the exact remote50-shard receipt and ciphertext, restore
every causal buffer/clock/weekly accumulator, and compete for one atomic recovery
claim. One must finish shards50 through99; the other must exit2.

A deterministic uninterrupted reference consumes the same fabricated fixture
without remote invocation. Complete canonical scientific state and complete
report must match byte for byte: all identity outputs, source bindings, buffers,
denominators, reasons, calendar vectors, covariances and four-week results.

Duplicate original and duplicate completed recovery must fail. The original
experiment identity is preserved. Recovery cannot replay durable completed
shards. All checkpoints, receipts, final report/state and proof use existing
approved encrypted release storage and mandatory remote plaintext readback.
The existing configured key is checked only on the runner; no authentic numeric
ciphertext is opened by this proof. No key material is published.

Proof status and measurements are in the guarded SYNTHETIC_SUCCESSOR_INTEGRATION_RESULT_V1.json,
run37913950839/job113765494378; this description by itself is not a PASS certificate.
