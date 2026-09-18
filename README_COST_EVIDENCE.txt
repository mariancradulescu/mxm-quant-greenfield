MXM QUANT GREENFIELD V2 — TIER-1 COST EVIDENCE

RUN ONLY:
M6_COST_EVIDENCE_RUN.py

This is NOT the accepted OHLC collector and does NOT rerun market bars.

Purpose:
- read-only historical BID/ASK evidence for accepted Pepperstone LIVE:
  US500 symbolId 127
  NAS100 symbolId 126
- DEVELOPMENT interval only
- all weekday regular US cash-session envelopes, signal-blind
- deterministic causal BID/ASK merge at every official cash-session M15 boundary, including 09:30
- separate PRE_BOUNDARY and fresh POST_BOUNDARY_EXECUTABLE evidence
- contract-bound resumable local chunks + hash verification

Safety:
- OAuth scope = accounts
- orders = NO
- subscriptions/trading mutations = NO
- economics = NO
- candidate outcomes = NO
- V2 attempts = NO
- protected evidence = NO
- no credentials are put in the returned ZIP

The script reuses the existing local cTrader OAuth/application/account state when safe.
No manual symbol selection is required.

The run may be long. Keep Pydroid open. If Android/Pydroid interrupts it, RUN THE SAME M6_COST_EVIDENCE_RUN.py again. Verified
chunks are reused ONLY when the exact plan/tool/interval/protected/target/quote-domain
resume contract matches; incompatible prior work is archived and never silently reused.

At completion return ONLY:
cost_capture_output/MXM_M6_TIER1_COST_EVIDENCE_V2.zip

Do not send:
~/.mxm_quant/
.m6_cost_evidence_work/
