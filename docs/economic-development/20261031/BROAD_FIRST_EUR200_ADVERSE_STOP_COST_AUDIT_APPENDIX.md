# Addendum — account-level risk failure in first broad M5 cash scenario

This is an **independent readback from the EXACT first executed PRIVATE ledger** of the closed frozen M5 wick-rejection policy, not any model reexecution, retuning, data resampling or modification of the two original full public receipts. Private episode-level source remains owner-side in Library, not committed to GitHub.

**Cause:** The scenario capped the *price-distance-only* modeled stop loss at EUR1.80 per minimum-volume position, but its current broker *dated* commission plus hypothetical 10bps roundtrip cost were booked **in addition**. The frozen source did not cap `price_stop_loss_eur + estimated_roundtrip_cost_eur <= EUR2` at candidate admission. This can violate the existing conservative account exposure/risk bound despite a minimum-volume ticket passing the margin gate.

The exact original first-result 88-episode private ledger was independently read, without rerunning any policy:
- **88 modeled entries** across one EUR200 simulated cash account;
- **30** modeled stopped episodes;
- **20/30 stopped episodes** had *net EUR loss greater than EUR2*, i.e. **20/88 total episodes** violated the existing EUR2 adverse-loss reference;
- Most adverse single episode conditional model net: **−EUR2.28555**, **not a broker fill**;
- Largest scenario per-episode roundtrip booked cost: **EUR0.48555**; **50/88** episodes had modeled transaction costs above EUR0.20.
- The originally frozen conditional final cash **EUR200.366702** and closed-equity drawdown **EUR18.796158** are preserved as originally calculated but **MUST NOT** be described as an OWNER-risk-admitted funded portfolio. The use of 22-Sep broker terms on Jan–14-Sep historical returns is an additional temporally post-dated *counterfactual* limitation.

**New verdict:** `NON_ADMISSIBLE_TO_EXISTING_EUR2_AGGREGATE_RISK_GUARD_AND_NOT_ROBUST_NET; CLOSED_NO_RETUNING`. Neither the nominal +EUR0.37 nor the historical price-source authenticity cures incomplete risk accounting, broker fills, HARD21 or missing contract payoffs. **No new safe trades should be added merely to hit weekly frequency**.

The existing operational C# `MxmOwnerEntryEnvelope` and stop-risk/final account guards remain unchanged and remain conservative; they must not be weakened to replicate this closed scenario. A *future distinct, prospective* market policy must include cost and stop risk jointly in **one common EUR200 funding admission** before signal scoring or order placement, and fail closed when minimum volume cannot fund the aggregate risk. This addendum does not replace user-provided final risk authority or impose new immutable 80/120/2 owner numbers. Current numerical caps are historical DIRECTOR implementation safeguards, with no authorization to relax them by this negative finding.

Grounded inputs: exact original first private `MXM_BROAD_WICK_FIRST_CASH_PRIVATE.json` file SHA256 `4e2907d62484cd2a2aa361fe97fb39111d7752f4b94c45ea35f25c64c26b7e7e`; canonical serialized ledger SHA256 `8348a88815996d5436ea1b2783381f7061a37a251b6df2a36cda16f291da0409`. Original script and public report hashes remain pinned in `BROAD_1576_NATIVE_EUR200_FIRST_MONETARY_EVIDENCE_PUBLIC.json`. Private PRICE/entry order data intentionally omitted.

No orders, broker calls, Cloud activation or new economic outcome.
