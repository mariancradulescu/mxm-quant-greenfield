# Reuse authenticated native symbol specifications — bounded economic evidence

B–E, 23 October 2026. PR #133 merged `51741e0e3e002e2782bc023a8ff3317c5cebe6d3`; protected run `39901409484` SUCCESS demonstrates the original encrypted quote source restored directly from Git and decoded inside unchanged custody, without downloading the original expiring Actions artifact. The immutable original decoder and ciphertext digests remain unchanged.

## Specific gap addressed
The portfolio replay's 1000 units, EUR50 margin, EUR0.10 fee and FX assumptions are explicitly hypothetical. The **already-saved original** native capture contains a SymbolById response in receipt #1, authenticated by the same original request/response wire verification, account fingerprint, ciphertext/private hashes and native catalogue. Ignoring that response leaves even the captured volume lattice and available fee semantics unnecessarily unknown.

Reuse only that response; do not connect to Pepperstone. Export a private symbol-terms sidecar after original native replay succeeds; bind its digest in the existing quote bridge receipt and in the encrypted complete result. Bind the original metadata response-wire digest, immutable source/run/ciphertext/private digest and symbol message digest. The public receipt exposes bounded presence/validity flags, not detailed private symbol values.

## Exact interpretation and tests
The protobuf's minVolume, maxVolume, stepVolume and lotSize are **hundredths of units**, not units or lots. Check the modeled 1000 units against the observed snapshot's explicit bounds and unambiguous step geometry without resizing a model order. Missing optional fields remain null; absent enum defaults such as USD or ENABLED are not observed evidence. Incomplete/ambiguous volume geometry cannot certify the volume.

Use explicit precise commission rate and explicit type only: non-percentage rates scale by 1e8; percentage-of-value rates scale by 1e5 and remain percentage values, not fractional rates. Minimum commission scales by 1e8, with asset/type availability tracked separately. Do not silently substitute deprecated integer fields or infer zero fees from absence. Eight artificial protobuf regression cases cover these distinctions, absent defaults, off-step/bounds, ambiguous geometry, different precision scales and malformed values. The actual `.algo` and existing source-preservation checks remain in required native CI.

Primary protocol reference: [cTrader Open API model messages — ProtoOASymbol](https://help.ctrader.com/open-api/model-messages/#protooasymbol). Repository-generated protobuf schema is the executable field/presence reference.

## Strict evidence boundary
The snapshot was received during original run `39660692230` on 21 October, whereas the existing tick window is 9 September. The message does not establish the September effective dates of volume rules, commission, margin or swaps. A captured admissible volume therefore establishes **captured-snapshot compatibility only**, never historical fill feasibility. A leverageId is a reference, not dynamic margin tiers. Rates alone cannot prove account currency, actual commission debit, historical FX/PnL conversion fees, guaranteed fills or real broker stops.

The model's cash ledger and hypothetical fee/margin/FX values remain unchanged. No new strategy leaf, tuning, new economic identity, protected confirmation, budget refund, broker request, pending-order cancellation, DEMO/LIVE order, Cloud activation, key or authority change. Qualification remains **NO_QUALIFIED_CANDIDATE** and HARD21 unproven. This is evidence extraction from existing authenticated market capture, not independent confirmation or proof of positive edge.

Native output is accepted only after required CI, merge and protected execution with digest-bound original source. Detailed recovered terms stay encrypted to the same original custody recipient. OWNER action required: NONE.
