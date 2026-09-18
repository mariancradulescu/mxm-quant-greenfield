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


V3 TICK-DELTA DECODER CORRECTION:
cTrader historical ProtoOAGetTickDataRes is newest-first and delta-compressed after the
first element. The first timestamp/raw price are absolute. Every later timestamp and raw
price value is a signed delta from the immediately previous encoded tick and is added
cumulatively. Negative timestamp deltas are expected and valid.

The first V3 user run blocked safely before any completed chunk because the older decoder
incorrectly rejected negative timestamp deltas. The corrected package bumps TOOL_VERSION,
so any prior V3 work directory is contract-mismatched, archived automatically, and the
corrected run starts clean. Do not reuse the old package.


V3 PIPELINED THROUGHPUT OPTIMIZATION:
The raw acquisition contract is unchanged. The collector now keeps up to 16 independent
historical tick-page requests in flight over ONE Pepperstone LIVE cTrader TLS connection.
Requests are serialized at 0.21 seconds between sends (the official historical ceiling is
5 requests/second/connection), then responses are drained and correlated by clientMsgId.

This replaces the old SEND -> WAIT RESPONSE -> NEXT SEND pattern that achieved only about
1.7-2.3 completed requests/second in the user's live run. It does not add another LIVE
connection, does not change symbols, dates, BID/ASK semantics, pagination, hashes, boundary
evidence, candidate semantics, or economics.

The stopped V3_TICKDELTA1 run can be resumed safely. Before reuse, every recorded chunk is
SHA256-verified and the complete V3 semantic resume contract must match exactly except for
the tool version. If any semantic field or chunk hash differs, migration is refused and the
existing work is archived instead of silently reused.


V3 PIPELINE2 STABILITY CORRECTION:
The user's live PIPELINE1 run proved that batch 16 was too aggressive for large historical
tick responses: 70 prior chunks migrated correctly, but repeated batch retries reduced the
effective completed-request rate to about 1.48 req/s.

PIPELINE2 keeps ONE LIVE connection and the same V3 raw acquisition contract, but starts
with at most 4 historical requests in flight. Requests are still paced at 0.21 seconds.
If a batch repeatedly fails, the collector automatically splits it 4 -> 2 -> 1, preserves
request order, reconnects with backoff, and prints the sanitized exact failure reason.

Verified chunks from both V3_TICKDELTA1 and V3_PIPELINE1 are eligible for explicit tool-only
resume migration only when the complete V3 semantic contract matches and every referenced
chunk passes SHA256 verification. No accepted OHLC data, candidate semantics, economics,
or protected evidence are touched.
