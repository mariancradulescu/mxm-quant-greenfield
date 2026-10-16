# O04 staging v1 — BLOCKED_STOP_ONLY

This is executable synthetic protocol evidence and a permanently closed public
acceptance API, not a deployed exclusive checkpoint acceptor. Maximum authorized
state remains STAGED_READY_STOP_ONLY, but this implementation MUST NOT claim it
until the principal-isolation reception passes. No environment variable, JSON,
commit author or workflow_dispatch can enable `accept_checkpoint`.

## Atomicity and authority are separate controls

The unchanged GitFenceLab `_publish` builds a one-parent commit and submits
`git push --force-with-lease=REF:EXPECTED_OLD_OID`. GitHub ruleset 25222248
forbids deletion, rollback and merge commits. Two and ten transport contenders
must yield one winning server OID. This does not validate the contents of a
forward commit. The separate write-without-acceptor-role job demonstrates that
missing boundary, using a quarantined synthetic child only. GET/PATCH in this
negative probe is deliberately NOT called CAS.

`FixtureProtocol` separates UNCLAIMED -> CLAIMED -> PENDING -> ACCEPTED. Recovery
claims advance epoch and discard a stale PENDING entry after lease expiry;
accepted records and operation IDs remain. Invalid proposals are REJECTED without
publishing. Untrusted forward state is QUARANTINED by the reader. A synthetic
Ed25519 fixture key is generated in temporary storage for each run, never an
OWNER or broker key. It binds every record field, manifest and ciphertext, but
is NOT a verified GitHub issuer or exclusive authorization grant. Server HTTPS
Date provides a time observation for the fixture. Receive-pack does NOT validate
lease expiry, signature or semantic version. Those remain a required trusted
acceptor responsibility and are blocked by the missing principal boundary.

## Schema

`schema_version=mxm.o04.stage.checkpoint.v1`, `marker=SYNTHETIC_ONLY`.
Root contains STOP OID, generation1807, release412686323, journal642889915,
release413440554, canonical/ciphertext/gzip/body digests. Synthetic generations
start at zero and have no relationship to OWNER generations. A proposal binds:
parent_oid, expected_old_oid, epoch, version, operation_id, writer_principal,
writer_session, lease_until, server_time_observed, generation, source_SHA,
manifest_sha256, ciphertext_sha256 and issuer kind/public-key fingerprint.
Signature is separate from the signed canonical record. PENDING commits both
content-addressed proof byte strings before ACCEPTED references them. Each
ACCEPTED record also records its PENDING OID; old records remain in history.

## Threat model and missing capability

Adversary: another valid contents:write credential, workflow or branch, stale
session, replay, malformed evidence, lost process/ACK. GitHub administrator able
to change rules is a declared governance boundary. Existing Actions tokens all
represent the GitHub Actions integration; job permissions do not create a
server-side acceptor role. Ruleset UI exposes roles/apps/users/deploy keys, not
a pinned workflow-job identity. Only the existing ChatGPT Codex Connector is
installed. Its integration cannot be delegated or extracted into Actions.

Required capability before readiness: a dedicated acceptor identity, enforced
by a stage/active-specific restrict-update/create rule allowing only that
identity, with ephemeral credentials issued ONLY after verifying the approved
repository ID, pinned workflow SHA/ref/job, run/attempt, actor and staging gate.
The credential must never be available to generic workflows, branches or callers.
A dedicated GitHub App with an authenticated credential issuer is one possible
realization; it is not installed or provisioned by this change. An App-wide
bypass for GitHub Actions or the existing general-purpose connector is not an
acceptable substitute. No broker credentials, scopes or new market infrastructure
are relevant. No new credentials are requested by this implementation.

## Dry-run readers and future bootstrap

`readers.py:dry_run` is a new opt-in adapter for the four explicitly enumerated
reader entrypoints. It never imports or executes the historical campaign. The
original disabled entrypoints remain untouched. It requires the selected ref to
equal the staging gate ref, validates evidence, and reports an unverified grant
explicitly. It never returns OWNER authorization. Original release selection,
side refs, UNKNOWN and active refs return NOT_AUTHORIZED; science remains UNKNOWN.
ReadOnlyAPI mutation regression retains its existing semantics.

Future `refs/heads/mxm-o04-active-v1` procedure (DOCUMENTATION ONLY): obtain
independent reception and separate owner production mandate; prove dedicated
principal + issuer and reader grant verification; create a deny-by-default
active-specific creation/update rule without weakening either existing ruleset;
bootstrap one-parent root with STOP provenance and zero accepted new OWNER
checkpoints; pin gate to that protected root; verify unauthorized writes and
readers fail closed; only then consider separate activation. This task creates
no active ref and changes no production gate.

## Evidence retention and recovery

Run-scoped refs contain only state.json, not workflows. Proof bytes reside in
PENDING/ACCEPTED Git commits, keyed by SHA256. Server no-delete/no-nonff protects
history from ordinary writers. Forward tampering can still occur and is why
readiness is NO_GO. Retention is repository lifetime subject to administrator
control, not an absolute immutable OWNER archive. Actions logs/artifacts retain
90 days only. Final evidence is exported with SHA256 in the owner's protected
report bundle; temporary fixture private keys are destroyed. Replay recovery
uses exact ref + operation_id + digest in a new interpreter/workspace, never a
blind retry. A process cut before/after commit is fault injection, not proof of
a physical GitHub network outage. No production durability claim is made.
