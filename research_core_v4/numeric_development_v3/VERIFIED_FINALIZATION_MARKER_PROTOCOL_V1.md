# V3 authoritative finalization protocol

**BLOCKED — not yet accepted.** Run37917881441/job113778412491 stopped
fail-closed on the first cold finalization: a publication pathname was shadowed
by a bound-source loop variable. The frozen policy bytes are restored in a new
commit, and the pathname defect is corrected with a regression test. No complete
remote crash-boundary proof exists for the corrected source. No further campaign
is started in this task, following the material-drift stop rule. The protocol
below specifies intended ordering; it is not a successful machine-side verdict.

This operational successor closes the V2 Release-before-Git false-PASS window.
V1/V2, their candidate, numerical worker, design, cohort, data, lags, calendar,
estimands and historical evidence remain immutable. This is delivery engineering.

The sole authoritative state is an immutable `mxm-numeric-v3-complete-{mode}-{identity}`
Git ref **together with** successful `verify_complete()` verification of every
referenced remote byte. Release bodies and delivery status files are intermediate
NOT_PERSISTED records. A PASS-shaped prepared completion file without this ref is
not global PASS. A Release body or an Actions conclusion alone is never sufficient.

Ordering:

1. Persist/read back the encrypted finalization-input journal. It contains the
   exact already computed report, finished state, source/ARM/approval identities,
   original invocation/run and prefix receipt inventory. Anchor its ciphertext
   in the guarded pending Release body.
2. Idempotently persist/read back encrypted report, scientific state and final
   receipt. Check ciphertext, decrypted gzip, canonical plaintext and object
   equality. An existing asset name must match exact expected scientific bytes.
3. Publish the guarded pending Git delivery document; verify exact bytes at the
   returned immutable commit. Verify bound source bytes and parent ancestry.
4. Publish/read back the final guarded pending Release body. Persist/read back
   an encrypted attestation binding its exact byte SHA256, the Git commit/path/
   byte SHA256, report/state/final receipt and journal.
5. Reverify prior artifacts; publish/read back the prepared guarded completion
   document pointing to that attestation. Check finite resource limits.
6. Atomically create the immutable completion ref pointing to this verified
   completion commit. This is the linearization point. Read back the ref and
   run the complete independent-byte verifier before emitting success.

No process-local exception handler, finally block or producer acknowledgement
is necessary for safety. Before step6, global state is pending. If a process is
killed after step6 but before acknowledgement, the delivery is already complete;
the independent reader verifies it. If any artifact subsequently changes, the
reader fails closed rather than trusting the marker alone. Refs are never moved,
Release assets never overwritten and publication never force-pushes.

Cold finalization recovery is independently authorized, one-use and bound to
the exact stopped original run, ARM/approval, anchored receipt, next_shard=100,
and prior resource ceiling. It authenticates the remote journal, restores the
finished report/state and performs delivery only. It never invokes consume_shard
or a scientific reducer. A crash before the finalization journal is anchored can
use the previously proved separately authorized prefix100 recovery with zero
completed-shard replay. Each later recovery requires a new separate acceptance.

The V2 scientific invocation claim and experiment identity remain unchanged.
V2 and V3 share real workflow concurrency. The V3 independent acceptance path
is absent and must remain absent during this task; candidate publication grants
no real execution. Human independence is an audit/governance assertion, not an
invented cryptographic identity certificate.

The fabricated proof uses this exact finalizer with actual GitHub assets, Git
commits/ref updates and Release bodies. It uses no authentic input and no new
scientific campaign. Historical disclosure remains noncompliant with the frozen
privacy rule; accepted residual risk does not authorize new disclosure.
