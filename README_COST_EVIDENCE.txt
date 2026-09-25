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


V3 PIPELINE3 DNS-RESILIENT RECONNECT:
The user's PIPELINE2 run resumed 1130 verified chunks and reached 1170 chunks, then a
historical batch timeout was followed by Android/mobile DNS failure:
gaierror [Errno 7] No address associated with hostname.

PIPELINE3 keeps the same V3 raw evidence contract, one LIVE connection, batch 4 and
4->2->1 fallback. It now caches cTrader LIVE resolved IP endpoint(s) after a successful
connection. If fresh DNS later fails, reconnect can use the cached IP while still passing
live.ctraderapi.com as TLS server_hostname, so certificate verification remains hostname-
based. The endpoint cache is operational only, stored under .m6_cost_evidence_work, and is
not research evidence.

Transient network/DNS failures no longer immediately terminate the collector. It will
pause and retry automatically with exponential backoff (1,2,4,8,16,30s capped at 30s)
for up to 30 minutes. Valid completed chunks remain SHA256-verified and resumable.

The user must not edit package files, delete work state, or manually repair anything.
Extract the package and run M6_COST_EVIDENCE_RUN.py.


V3 COMPACT1 FINALIZATION:
The Tier-1 raw capture has completed all 4912 local BID/ASK chunks. The older finalizer
unnecessarily concatenated those chunks into multi-GB raw CSV tapes (observed US500 BID
and ASK about 1.67 GB each), which is unsuitable for Android finalization and chat transfer.

COMPACT1 does NOT recapture ticks. On launch it SHA256-verifies/reuses the existing V3
chunks, removes only the partial cost_capture_output/MXM_M6_TIER1_COST_EVIDENCE_V3
transfer directory, and derives the two generic boundary-evidence CSVs directly from the
retained daily chunks.

Raw tick bytes remain under:
.m6_cost_evidence_work/tier1_us500_nas100_v3/chunks

The transferable ZIP intentionally does NOT embed consolidated raw tick CSVs. Instead it
contains a deterministic raw_chunk_commitment manifest with all 4912 individual chunk
SHA256 values, row counts, request windows, four per-stream manifest digests and one
overall ordered-manifest digest, plus the two derived boundary evidence files and the
normal provenance/policy/checksum files.

Keep .m6_cost_evidence_work on the phone until ChatGPT explicitly says it can be deleted.
Return only MXM_M6_TIER1_COST_EVIDENCE_V3.zip. No manual editing or file selection is needed.


V3 COMPACT2 INDEXED FINALIZER:
The COMPACT1 finalizer correctly avoided multi-GB transfer tapes, but its boundary derivation
still performed repeated full-list scans for every M15 boundary and provided no progress
heartbeat. On the user's Android run, all 4912 raw chunks were already verified while
US500 boundary evidence advanced only slowly.

COMPACT2 does NOT recapture any market data. It reuses the same 4912 local raw chunks after
SHA256 verification, deletes only the partial transfer-output directory, and builds one
timestamp index per BID/ASK daily chunk. Every generic M15 boundary lookup is then O(log n)
via bisect instead of repeated O(n) scans.

During US500 and NAS100 derivation it prints:
[FINALIZE HEARTBEAT] <symbol> | <percent> | sessions X/1228 | rows Y | elapsed Zm
every 25 weekday windows, plus the first and final window.

Raw chunks remain local under .m6_cost_evidence_work and are not embedded in the compact
transfer ZIP. No economics, candidate signals, protected evidence, or candidate identities
are touched.
