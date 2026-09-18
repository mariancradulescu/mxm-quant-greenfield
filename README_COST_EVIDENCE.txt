MXM QUANT GREENFIELD V2 — TIER-1 V3 QUOTE / COST EVIDENCE

RUN ONLY:
M6_COST_EVIDENCE_RUN.py

This is NOT the accepted OHLC collector and does NOT rerun market bars.

Purpose:
- read-only historical BID/ASK evidence for accepted Pepperstone LIVE:
  US500 symbolId 127
  NAS100 symbolId 126
- DEVELOPMENT interval only
- all weekday regular US cash-session envelopes, signal-blind
- preserve complete raw BID and ASK event tapes with exact timestamps and hashes
- derive candidate-independent generic M15 boundary quote evidence, including 09:30
- keep candidate MARKET_PROXY timing separate from quote/spread/slippage/delay evidence
- contract-bound resumable local chunks + hash verification

Derived boundary evidence includes:
- CAUSAL_STATE_AT_BOUNDARY: latest causally known BID and ASK at/before boundary, with side ages
- FIRST_POST_BOUNDARY_BID_EVENT
- FIRST_POST_BOUNDARY_ASK_EVENT
- FIRST_POST_BOUNDARY_ANY_QUOTE_EVENT
- BOTH_SIDES_REFRESHED_AFTER_BOUNDARY = QUOTE_REFRESH_DIAGNOSTIC_ONLY

The 15-minute both-sides refresh window is ONLY a bounded diagnostic observation window.
It is NOT a fill time, mandatory delay assumption, Stage-A execution truth, or economic fill rule.

No numeric quote-staleness/slippage/fill-delay rule is frozen before capture.
After capture, only the prospectively frozen candidate-independent calibration protocol may
establish VERIFIED_APPLICABLE_RULE, CONSERVATIVE_BOUND, or UNRESOLVED before any C006/C012
economic outcome is opened.

Safety:
- OAuth scope = accounts
- orders = NO
- subscriptions/trading mutations = NO
- economics = NO
- candidate signals/returns/PnL are NOT inputs
- candidate outcomes = NO
- V2 attempts = NO
- protected evidence = NO
- no credentials are put in the returned ZIP

The script reuses the existing local cTrader OAuth/application/account state when safe.
No manual symbol selection is required.

V3 starts in its own clean work generation:
.m6_cost_evidence_work/tier1_us500_nas100_v3

The user has not run V2, so V2 work is not migrated. Verified V3 chunks are reused only
when the exact V3 plan/tool/interval/protected/target/quote-domain resume contract matches.

At completion return ONLY:
cost_capture_output/MXM_M6_TIER1_COST_EVIDENCE_V3.zip

Do not send:
~/.mxm_quant/
.m6_cost_evidence_work/
