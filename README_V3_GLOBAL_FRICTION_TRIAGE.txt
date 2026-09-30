MXM Research Core V3 — GLOBAL authentic friction triage V7

Purpose
-------
Obtain the fastest scientifically defensible economic kill/unresolved answer for all 14
priority gross-robust regions using authentic historical Pepperstone DEVELOPMENT bid/ask
friction, without changing the frozen 7,975-cell research surface or opening protected-forward.

This package supersedes V6 EXECUTION ONLY. V6 scientific artifacts remain preserved.

Initial campaign
----------------
- ONE frozen global triage look only.
- All 14 priority regions complete acquisition before any economic classification.
- Stratification remains UTC month x 6-hour session bucket across the DEVELOPMENT calendar.
- One frozen UTC hour is selected per non-empty stratum by SHA-256 order.
- Up to three exact reference windows are frozen inside each selected hour by an independent
  SHA-256 order.
- Unselected exact windows in a sampled hour contribute ZERO to the death proxy.
- Missing, stale, unavailable or negative-spread observations also contribute ZERO.
- This intentionally makes the test conservative.

Economic decision
-----------------
For each region, fresh nonnegative d0 spread is clipped at 2 x that region's minimum gross
mean response. A stratified hour-cluster Horvitz-style lower proxy is formed over the full
reference-window denominator. A one-sided Hoeffding bound uses familywise alpha 1% across
the 14 regions.

If the lower bound exceeds the region's minimum gross mean response:
  CLEARLY_ECONOMICALLY_DEAD_BY_AUTHENTIC_SPREAD_ALONE

Otherwise:
  PLAUSIBLE_OR_UNRESOLVED_STOP_ANDROID

The second label is NOT positive-edge certification, NOT candidate freeze and NOT permission
to open protected-forward. No Look2, Look3 or Look4 is requested automatically.

Transport benchmark
-------------------
Stage 0 benchmarks 1m, 5m, 15m, 60m and 180m ranges at three frozen density anchors per
symbol and both quote sides: 420 base probes total. It records latency, API attempts,
pagination, protobuf bytes, tick counts, retries/rate limits and historical unavailability,
but no prices/spreads.

The Stage 1 eligible set is 1m/5m/15m/60m. Selection minimizes measured elapsed milliseconds
per reference-window opportunity, then bytes, then API attempts. The 180m probe is retained
as a broader measured envelope check; because the triage is hour-bounded, 180m cannot reduce
below one bid/ask transport pair per sampled hour compared with 60m and therefore is not
eligible for Stage 1.

Storage / transfer
------------------
- Raw ticks are never written to disk or transferred.
- Aggregate local capture artifacts hard cap: 256 MiB.
- Minimum free disk: 512 MiB.
- Preferred first evidence ZIP: <=25 MiB.
- Hard evidence ZIP cap: 64 MiB.
- Evidence uses gzip-derived sampled-hour rows plus transport/page provenance and hashes.

Run
---
1. Do NOT resume V5 or run the old V6 package.
2. Extract MXM_V3_GLOBAL_FRICTION_TRIAGE_PACKAGE_V7.zip into a NEW Android folder.
3. Open and run only V3_MAXT14_GLOBAL_FRICTION_TRIAGE_RUN.py in Pydroid 3.
4. If OAuth leaves the browser foregrounded, return through Android Recents to the SAME
   running Pydroid process. Do not press RUN again.
5. Stage 0 benchmarks transport, then the single frozen global campaign runs.
6. The script stops Android acquisition after all 14 are evaluated.
7. Return only:
   v3_friction_triage_output/MXM_V3_GLOBAL_FRICTION_TRIAGE_EVIDENCE_V1.zip

No raw tick archive is needed. Do not request another look until the returned 14-region
evidence has been evaluated together.
