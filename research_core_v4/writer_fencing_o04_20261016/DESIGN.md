# O04.1 — NO-GO global, isolated implementation evidence

This package is an isolated executable specification. It does not secure live
Releases, change the accepted checkpoint, authorize a campaign or certify the
platform. `production_backend()` always denies access. No legacy writer is
migrated or revoked by adding this package.

## Required global architecture

1. A trusted broker is the sole principal allowed to accept checkpoint or
authority transitions. Historical Actions jobs have no write credential for
these resources. Restrict and inspect GitHub App installations, PAT grants,
deploy keys, collaborators, repository Actions policy and administrator bypasses.
Repository default read-only token permission alone is insufficient: explicit
`contents: write` in a historical workflow must be excluded at the boundary.
2. A single protected Git ref is the authority. Each commit has exactly one
parent, the previously accepted ref OID. The snapshot contains epoch, owner,
lease deadline, monotone checkpoint version and immutable accepted digests and
operation IDs. A claim and any takeover increment the epoch using the same CAS.
3. The broker authenticates the caller, validates the grant and server time,
verifies checkpoint ciphertext and manifest bindings, and prepares a successor.
The Git receive-pack update carries the explicit expected old OID. It may only
advance to a child of that OID. No force rollback, deletion or alternate ref is
allowed. The lab uses `git push --force-with-lease=REF:EXPECTED` for the expected
OID comparison, plus server-side non-fast-forward and deletion denial. The
option name does not authorize weakening GitHub protections.
4. Before accept, the broker checks current OID, owner, epoch, lease and version
together. The checkpoint digest is appended, never replaced. Recovered workers
obtain a new epoch; delayed workers cannot accept. An ambiguous transport ACK
requires exact readback by operation ID, version and digest, never blind retry.
5. Releases are immutable evidence transport, never a mutable acceptance anchor.
The existing generation-1807 release body and all OWNER assets remain preserved.
Future readers must use the protected accepted ref. Historical readers/writers
must be disabled or migrated before activation. A stale Release PATCH must have
no authority and no credential capable of changing accepted evidence.
6. Bootstrap, only after administrative exclusion is proven, would bind the
preserved generation-1807 digest into the new authority. It is NOT performed by
this change. Checkpoint imports, new authority issuance, broker deployment and
campaign execution are not implied by test success.

## What is actually implemented

The lab drives real Git object creation and competing receive-pack sessions
against temporary filesystem-only bare repositories. It refuses HTTP remotes
and requires a synthetic lab marker. No live write path is provided. Principal
checks and lease time are injected lab fixtures, not authenticated server
attestations. There is no production broker, cryptographic authorization service,
artifact import or global GitHub protection deployment in this package.

Eight targeted tests cover competing writers, expired/stale writer, restart,
lost ACK, missing principal, immutable version and server rollback rejection,
production denial, and an adversarial unrestricted-writer bypass. The last test
deliberately demonstrates why client-side validation is insufficient globally.

`inventory.py` reads all fetched heads/tags and reachable executable source
versions without importing historical code. Its candidates retain blob IDs,
SHA256, refs, categories and line numbers. Workflow versions include exact
source, permissions, secret names and actions. Static candidates do not prove
the exhaustive set of effective external credentials or dynamic entrypoints.

## Current legitimate-access blocker

The connected user is reported as admin, but the managed integration returns
403 Resource not accessible by integration on branch-protection GET. No callable
administration mutation, token inventory/revocation or workflow-disable API is
exposed by the current connector. Do not substitute an Actions token, copy a
secret or bypass protections to acquire missing administration access.

Required capability: legitimate repository Administration read/write for rules,
branch protections and Actions policy; Actions write to disable legacy workflow
entrypoints and prevent reruns during migration; read/write over relevant deploy
keys and GitHub App installation grants; owner-level inspection/revocation of
PAT/App credentials that can bypass the broker. These require corresponding
callable APIs and identity/grant evidence, not a self-issued JSON authorization.
If the current account/repository plan cannot enforce the chosen restriction,
the design must remain NO-GO until an enforceable boundary is available.

No claim is made that editing historical branch heads alone fixes reruns of old
SHAs or removes existing external tokens. No security protection is disabled.
