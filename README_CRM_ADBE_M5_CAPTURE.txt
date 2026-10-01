MXM V3 CRM/ADBE exact-M5 temporal acquisition

RUN ONLY:
CRM_ADBE_M5_CAPTURE_RUN.py

Frozen scope:
- Pepperstone cTrader Open API
- CRM.US-24 + ADBE.US-24 only
- exact M5 trendbars only
- 2025-01-02T00:00:00Z through 2025-09-14T23:59:59Z
- read-only; no orders, fills, BID/ASK, ticks or account mutation
- no strategy PnL/outcomes or formation estimates on-device

RETURN ONLY:
MXM_V3_CRM_ADBE_M5_TEMPORAL_EVIDENCE_V1.zip

If DATA_UNAVAILABLE is reported, do not change interval or resolution.
