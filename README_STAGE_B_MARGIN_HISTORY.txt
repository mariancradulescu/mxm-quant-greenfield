MXM QUANT GREENFIELD V2 — STAGE-B HISTORICAL MARGIN EVIDENCE

PURPOSE
This package captures read-only broker evidence needed to assess whether a defensible
historical margin authority can be frozen for Stage-B. It does NOT run Stage-B economics.

SAFETY
- OAuth scope: accounts/view-only.
- Orders: NO.
- Order/position/account mutation: NO.
- LIVE economic execution: NO.
- Protected-forward evidence: CLOSED.
- DEVELOPMENT interval ends 2026-09-16T23:59:59.999Z.
- Only US500 symbolId 127 and NAS100 symbolId 126 are relevant historical targets.

ANDROID / PYDROID
1. Extract the package into:
   /storage/emulated/0/Download/MXM_M6_STAGE_B_MARGIN_HISTORY/
2. Open Pydroid 3.
3. Open and RUN:
   M6_STAGE_B_MARGIN_HISTORY_RUN.py
4. The package first performs an offline preflight. It will not contact cTrader if
   the package/read-only contract is invalid.
5. Existing saved view-only cTrader authorization is reused/refreshed when possible.
   If cTrader asks for authorization, approve the existing accounts/view-only flow.
6. If multiple Pepperstone LIVE accounts are authorized, the launcher asks you to
   choose the correct LIVE account locally. That raw account ID is not exported.

PROGRESS
Expected progress messages include:
- LOCAL PREFLIGHT PASS
- connecting read-only to Pepperstone Europe LIVE
- verifying US500/NAS100 product identities
- capturing DEVELOPMENT historical deals
- window N/... and historical request count
- finalizing privacy-safe evidence
- deterministic ZIP SHA256

The Open API connection uses the existing stdlib TLS/protobuf transport and its heartbeat.
Historical requests are paced at approximately 4.75 requests/second.

OUTPUT
Expected transferable ZIP:
MXM_M6_STAGE_B_MARGIN_HISTORY_EVIDENCE_V1.zip

It is written beside M6_STAGE_B_MARGIN_HISTORY_RUN.py in the extracted package directory:
 /storage/emulated/0/Download/MXM_M6_STAGE_B_MARGIN_HISTORY/
 MXM_M6_STAGE_B_MARGIN_HISTORY_EVIDENCE_V1.zip

UPLOAD BACK
Upload ONLY MXM_M6_STAGE_B_MARGIN_HISTORY_EVIDENCE_V1.zip to ChatGPT.

LOCAL RAW RETENTION
If sanitized target evidence exceeds the transferable threshold, full sanitized target rows
remain under stage_b_margin_raw_local/ with SHA256 commitments. Keep that folder until explicit
deletion authority exists. Do not upload private OAuth files or ~/.mxm_quant/.

INTERPRETATION
- No relevant target deals:
  UNRESOLVED_NO_ACCOUNT_NATIVE_HISTORICAL_MARGIN_OBSERVATIONS
- Relevant target deals but marginRate absent:
  UNRESOLVED_MARGIN_RATE_NOT_RECORDED
- Relevant target deals with marginRate:
  OBSERVATIONS_CAPTURED_REQUIRES_SEPARATE_FAIL_CLOSED_AUTHORITY_ASSESSMENT

Current dynamic leverage and margin-call settings are diagnostics only:
CURRENT_ONLY_NOT_HISTORICAL_AUTHORITY

Even a successful capture does not authorize Stage-B. A separate historical-margin authority,
independent audit, exact-head green CI, and separate single-use Stage-B execution authorization
are still required before any Stage-B economic outcome may be opened.
