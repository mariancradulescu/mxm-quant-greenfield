# Recipient custody contract V1

This additive contract does not alter any frozen workflow, scientific design, encryption format or fail-closed validator.

Three distinct states are mandatory: NUMERIC_SUCCESS, OWNER_READBACK_SUCCESS, DELIVERY_SUCCESS. The latter requires the actual recipient's successful authenticated download/decryption and verified source and canonical-summary hashes. A public encrypted-upload PASS must never stand for DELIVERY_SUCCESS.

The current recipient is held locally under 0600 and has proved possession of the exact pinned public key; no private key is stored in this repository. Actual readback is attested by a RSA-PSS-SHA256 signed hash-only acknowledgement. No economic plaintext is public.

For a future additive worker, import delivery_contract_v1 and bind its hash and recipient SPKI in its one-use authority. Require a fresh, signed readiness document for the exact invocation, an active same-session recipient with expiry covering the whole bounded execution plus readback, and no unattended or cross-session execution. Reject missing/expired/insufficient custody before any new market computation. Require the final signed delivery acknowledgement against the expected source run, delivered ciphertext hash and canonical-summary hash before marking DELIVERY_SUCCESS.

A signed readiness document proves possession when signed, not physical survival of a temporary filesystem. It is never evidence of permanent key storage. No permanent recipient secret store is exposed or certified here. Cross-session private-key persistence remains unguaranteed, and unattended/cross-session work is blocked by this contract. Existing historical workers remain immutable; this module is a required contract for future additive workflows, not a claim that every legacy workflow was retrofitted.

Durable recovery custody remains the already established OWNER secret plus OWNER-encrypted scientific results. If a conversation session is lost, recover the saved OWNER summary to a separately verified recipient in a subsequent authorized session, without repeating scientific computation. No assumed persistence of a scratch directory, no secret export or private-key upload.

The currently completed recovery used one new one-use authority, with no broker requests and no scientific calculation. The primary scientific result remains intact. Tests proved a real signed delivery acknowledgement, bounded readiness, and rejection of modified, expired or insufficient acknowledgements/leases.

All further experiments must remain within legitimate Pepperstone/corpus scopes, preserve full adaptive history and carry an explicit verifiable recipient route through completion. No experiment is started solely because producer-side encryption works.
