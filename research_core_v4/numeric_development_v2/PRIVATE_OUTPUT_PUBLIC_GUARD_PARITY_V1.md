# Actual publication guard coverage

The immutable public_output_guard_v1.py is reused without weakening its schema.
Store.body validates the release body's entire document before the PATCH call
and reads back its exact bytes. Store.publish inherits safe_public_git_blob at
the actual Git blob callsite and checks exact remote content after the branch
update. Scientific states, reports, source-prefix metadata and failure/proof
evidence go only through encrypted release assets with authenticated remote
ciphertext, gzip, canonical plaintext and object readback.

Tests inject confidential fields into both actual public callsites and require
rejection before a blob/body write. Tests inject encrypted-final upload failure,
remote readback failure and public-final write failure and require exceptions;
entrypoint errors produce a nonzero exit. The authentic mode has no fabricated
stop/key/approval switches. Historical disclosure remains noncompliant; this
successor does not reclassify it or authorize further disclosures.
