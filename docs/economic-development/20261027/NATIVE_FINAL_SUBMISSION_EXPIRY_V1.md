# Consumed intent expiry at final native submission

Continuation from official `adac65def73b672a2109e128fc4ff141f172a558`, no later work found live. The product previously checked the consumed decision's bar lifetime before final fee, margin and full-book risk recalculations. An unchanged book could pass that check and then outlive the bar while those calls completed. Identity checks alone do not impose time expiry.

The existing broker fence now exposes a shared half-open bar check. The native product uses it both before those final calculations and immediately before MarkSubmitted/ExecuteMarketOrder, with a fresh broker clock and position identity. Expired/revoked decisions return through the original not-submitted cleanup; unknown broker outcomes and recovery are unchanged. The check/order pair remains non-atomic and native callback timing remains to be received; this change does not claim broker execution certification.

Seven artificial compiled fixture checks cover the last tick before expiry, exact expiry, delayed admission, clock before boundary, inclusive lower boundary, unchanged identity despite expiry and a changed final broker position. Existing admission CI runs this exact shared fence fixture and builds the cTrader product. No new broker request, model, order, Cloud, authority or capital change.
