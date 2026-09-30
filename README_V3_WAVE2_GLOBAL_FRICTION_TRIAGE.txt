MXM Research Core V3 — Wave2 authentic friction triage V8

Purpose
-------
Move immediately from the parked V7 priority-14 batch to the next 14 gross-robust
regions with the largest minimum DEVELOPMENT gross response. This is transport priority
only, not promotion. The prior 14 remain open historically but receive no more broker
acquisition for now because their authentic V7 observations were strongly unfavorable.

Wave2 symbols / mechanisms
--------------------------
CRM.US-24 breakout, HOOD.US-24 breakout, AMD.US-24 breakout,
NERUSD, ONDUSD, XPDUSD, BNKUSD, DOGEUSD, ATMUSD, COMPUSD,
ETCUSD, XTZUSD, KSMUSD and LTCUSD.

Scientific correction from V7
-----------------------------
The V7 frozen sample membership was valid, but its death estimator forced unselected
within-hour exact windows to zero without inclusion weighting. That made the official
death test structurally incapable of crossing its threshold.

Wave2 fixes this prospectively, before any Wave2 friction outcome exists:
- one frozen UTC hour per non-empty month x 6h-session stratum;
- up to three frozen exact windows inside that hour;
- selected-window clipped spread total is expanded by
  reference_window_count / sampled_window_count;
- the one-sided Hoeffding range remains the full-hour bounded total;
- familywise alpha = 1% across all 14 regions;
- missing/stale/unavailable/negative observations still contribute zero;
- favorable early stopping remains forbidden;
- there is exactly one global campaign and no automatic second look.

Economic interpretation
-----------------------
If corrected lower bound > minimum gross mean response:
  CLEARLY_ECONOMICALLY_DEAD_BY_AUTHENTIC_SPREAD_ALONE

Otherwise:
  PLAUSIBLE_OR_UNRESOLVED_STOP_ANDROID

Non-death is not net certification and does not freeze a candidate. Protected-forward
remains CLOSED.

Transport / storage
-------------------
Stage 0 reuses the fast measured benchmark structure: 1m/5m/15m/60m at three frozen
density anchors plus 180m only at the median anchor, 364 base probes total.
The chosen Stage 1 transport minimizes measured wall-clock per retained triage window.
Raw ticks are never written to disk or transferred.

Aggregate local capture hard cap: 256 MiB.
Minimum free disk: 512 MiB.
Preferred evidence ZIP <=25 MiB; hard cap 64 MiB.

Run
---
1. Extract MXM_V3_WAVE2_GLOBAL_FRICTION_TRIAGE_PACKAGE_V8.zip into a NEW folder.
2. Open only V3_WAVE2_GLOBAL_FRICTION_TRIAGE_RUN.py in Pydroid 3.
3. Run once. If OAuth leaves the browser foregrounded, return through Android Recents
   to the SAME Pydroid process; do not press RUN again.
4. The script benchmarks transport, completes all 14 frozen Wave2 samples, evaluates
   them jointly, writes one compact evidence ZIP and stops.
5. Return only:
   v3_friction_wave2_output/MXM_V3_WAVE2_GLOBAL_FRICTION_TRIAGE_EVIDENCE_V1.zip
