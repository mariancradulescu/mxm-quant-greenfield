MXM Research Core V3 — Winner-First Authentic Friction Screen V9R1

WHY THIS EXISTS
---------------
V7 and V8 proved that spending broker time on formal "death certificates" is a poor
use of information budget. V9 changes the objective: find the few remaining gross
regions whose authentic Pepperstone event-time spread is small enough to justify
deeper execution and net-economics work.

SCOPE
-----
- 57 still-unmeasured gross-robust regions on 56 unique symbols.
- Three additional remaining regions on CRM.US-24, AMD.US-24 and XTZUSD reuse V8
  symbol-scope diagnostics and are not recollected.
- Protected-forward remains CLOSED.
- No candidate can be frozen or net-certified by this screen.

SPARSE DESIGN
-------------
The complete frozen DEVELOPMENT scope contains 2,623,050 exact quote windows.
Those millions of windows are NOT loaded on Android.

Before packaging, CI deterministically freezes a sparse sample:
- strata = UTC month x 6-hour session bucket;
- select 2 non-empty session strata per month by SHA-256 order;
- select 1 hour inside each chosen stratum by SHA-256 order;
- select up to 3 exact windows inside that hour by SHA-256 order;
- fixed 60-minute transport grouping;
- d0/d1/d5/d30 quote diagnostics, with 2-second freshness threshold.

The exact sampled window membership is included in the Android ZIP. Sampling uses no
broker outcomes. Android therefore processes only a few thousand frozen windows, not
the 2.6 million-window reference universe.

OUTPUT INTERPRETATION
---------------------
Per region, the phone records only screening diagnostics:
- fresh quote count / fresh fraction;
- min, p25, median and mean authentic d0 spread;
- those spread statistics divided by the frozen gross edge.

Diagnostic labels:
- FRICTION_PLAUSIBLE_SIGNAL:
  >=3 fresh d0 observations and at least one spread <= gross edge.
- STRONG_NEGATIVE_SIGNAL:
  >=3 fresh d0 observations and even the minimum spread > 2x gross edge.
- otherwise UNRESOLVED_SCREEN.

These labels are NOT certification, NOT promotion and NOT a candidate freeze.
Only the few best friction-plausible regions will get detailed commission, minimum
volume, margin/leverage, execution/slippage and net-economics work.

CURRENT SYMBOL METADATA
-----------------------
The evidence ZIP also contains safe current cTrader symbol metadata (commission fields,
lot/min/step volume, leverage ID, schedule, swaps where supplied). It is explicitly
marked CURRENT ONLY and is NOT treated as historical cost truth.

V9R1 RESUME HOTFIX
------------------
V9R1 repairs multi-page cTrader tick chronology only. It does NOT change the frozen
research plan, sparse sampling membership, symbol set, or economic rules.

If V9 stopped with "BID ticks are not chronological" or "ASK ticks are not chronological":
extract V9R1 OVER THE SAME EXISTING V9 FOLDER and allow file overwrite. Do NOT delete
the hidden .mxm_v3_winner_first_friction_work directory. That directory contains the
verified completed-hour resume state. The same frozen contract remains valid, so
completed hours are reused without broker recollection.

RUN / RESUME
------------
1. Extract MXM_V3_WINNER_FIRST_FRICTION_SCREEN_PACKAGE_V9R1.zip OVER THE SAME V9 folder.
2. Allow overwrite/replace of package files; do not delete other files/folders.
3. Open only V3_WINNER_FIRST_FRICTION_SCREEN_RUN.py in Pydroid 3.
4. Run once. Previously completed hours will scroll past quickly and be reused.
5. If OAuth leaves the browser foregrounded, return through Android Recents to the
   SAME Pydroid process. Do not press Run again.
6. If interrupted, rerun the same file from the same folder; completed sparse hours
   remain resumable.
7. When complete, return only:
   v3_friction_winner_output/MXM_V3_WINNER_FIRST_FRICTION_SCREEN_EVIDENCE_V1.zip

Do not run V7 or V8 again.
