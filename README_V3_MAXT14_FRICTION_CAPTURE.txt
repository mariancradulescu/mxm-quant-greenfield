MXM Research Core V3 — staged authentic friction acquisition V6

Purpose
-------
Replace the stopped exhaustive V5 transport with an outcome-blind, information-efficient
DEVELOPMENT friction design. The complete 691,919 exact windows remain the reference
population; Stage 1 samples only pre-frozen DEVELOPMENT hours and may stop early only when
authentic spread alone proves a priority region economically dead.

Scientific boundaries
---------------------
- Pepperstone Europe LIVE, rebound accepted account fingerprint, exact 14 symbol IDs/names.
- Read-only cTrader Open API; no orders or account mutation.
- Protected-forward remains CLOSED.
- No current-spread substitution for historical DEVELOPMENT friction.
- No post-protected-forward quote outcomes for DEVELOPMENT selection.
- 7,975 corrected DEVELOPMENT cells, 88 gross robust regions, 14 priority regions,
  74 other COST_UNRESOLVED regions, and the full 1,576-identity frontier are unchanged.
- Frozen candidates remain 0.
- Runtime V2 remains legacy/read-only.
- Stage 0 transport adaptation may use only tick counts, pagination, response bytes,
  latency and broker/network errors. It does not compute or persist spread values.
- Stage 1 sample membership for every possible look is frozen before the first broker request.
- Favorable early stopping is forbidden. Non-death remains COST_UNRESOLVED.
- The only early stop is a familywise-controlled conservative proof that one authentic
  d0 spread alone already exceeds the region's minimum gross mean response.

Stage 0
-------
252 base probes = 14 symbols x 3 frozen density anchors x 3 spans (5m/15m/60m) x BID/ASK.
For every probe the collector records actual API attempts, successful responses, ticks,
protobuf bytes, elapsed time, hasMore/page depth, retries/rate limits and explicit broker
history-unavailable responses. No raw tick values are written to disk.
Per symbol the largest span whose observed page depth is <=2 on every benchmark probe is
chosen from 60m, 15m, then 5m. This changes transport only, never sample membership.

Stage 1
-------
Primary sampling unit: UTC calendar hour containing one or more frozen exact windows.
Strata: calendar month x UTC 6-hour session bucket.
Within every non-empty stratum, the full hour order is fixed by SHA-256 using only the
pre-outcome plan binding, symbol, stratum and hour. Cumulative looks request 1/2/4/8 hours
per non-empty stratum. All exact windows in selected hours are analyzed.

Exact no-network geometry across all 14 priority regions if every region reaches each look:
- Look 1: 5,977 exact windows.
  60m profile: 1,456 BID/ASK base requests; 15m: 5,620; 5m: 11,954.
- Look 2: 11,927 exact windows.
  60m: 2,912; 15m: 11,212; 5m: 23,854.
- Look 3: 23,610 exact windows.
  60m: 5,824; 15m: 22,392; 5m: 47,220.
- Look 4 maximum: 47,256 exact windows.
  60m: 11,648; 15m: 44,848; 5m: 94,512.
These are cumulative base requests before real broker pagination. Regions proven dead stop
before later looks, so actual Stage 1 work can be materially smaller.

Sequential rule
---------------
Familywise alpha = 1% across 14 regions x 4 looks. For the death proof, each fresh,
nonnegative d0 spread is clipped at 2 x the region's minimum gross mean response.
Missing/stale/unavailable/negative observations contribute 0 to the death lower bound,
which can only make death harder to prove. A stratified hour-cluster total estimator plus
a one-sided Hoeffding lower bound is used. If lower bound > minimum gross mean response:
CLEARLY_ECONOMICALLY_DEAD_STOP_MORE_CAPTURE_FOR_THIS_REGION.
Otherwise intermediate looks expand; final non-death is INSUFFICIENT_KEEP_COST_UNRESOLVED.
This is not candidate freeze, net certification or confirmation readiness.

Storage / transfer
------------------
- Raw ticks are never persisted to disk in V6.
- Each selected hour is derived in memory and saved only as compact gzip exact-window evidence
  plus request/page cryptographic commitments.
- Stage work directory hard cap: 256 MiB.
- Capture fails before disk can silently exceed that cap.
- Minimum free-disk safety floor: 512 MiB.
- Transfer bundle contains compact derived evidence and benchmark/provenance, never raw ticks.

Observed baseline and expected time
-----------------------------------
The stopped V5 phone run completed about 600 base chunks in about 210 seconds
(~2.86 base chunks/s). At that observed rate the old 461,102-base-request exhaustive plan
was about 44.8 hours before extra pagination/retries. cTrader's documented historical-data
limit is 5 requests/s per connection, so even the theoretical base-request floor was about
25.6 hours.

Using the observed 2.86/s baseline and ignoring pagination:
- Stage 0 252 base probes: ~1.5 minutes base time; budget several minutes with auth/pagination.
- Look 1 if all symbols choose 60m: ~8.5 minutes base time.
- Look 1 at 15m: ~32.8 minutes; at 5m: ~69.7 minutes.
- Maximum Look 4 if every region survives and all use 60m: ~68 minutes base time.
- Maximum Look 4 at 15m: ~4.36 hours; at 5m: ~9.19 hours.
Actual V6 records the real page depth/bytes/rate and chooses the transport span before Stage 1.
Sequential death stops can reduce these figures further.

Run
---
1. STOP and do not resume the old exhaustive V5 capture.
2. Extract MXM_V3_STAGED_FRICTION_PACKAGE_V6.zip into a NEW Android folder.
3. Open and run only V3_MAXT14_FRICTION_STAGE_RUN.py in Pydroid 3.
4. If OAuth browser does not foreground Pydroid, return to the SAME running process through
   Android Recents. Never press RUN a second time after callback success.
5. Stage 0 runs first, freezes an actual transport profile, then Stage 1 runs automatically.
6. If interrupted, run the SAME V6 file again; completed staged hours are hash-verified/resumed.
7. On completion return only:
   v3_friction_stage_output/MXM_V3_STAGED_FRICTION_EVIDENCE_V1.zip

Do not send raw tick archives. Do not resume V5.
