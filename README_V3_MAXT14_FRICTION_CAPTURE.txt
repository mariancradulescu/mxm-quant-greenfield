MXM Research Core V3 — maxT14 authentic friction capture

Purpose
-------
Collect broker-native historical BID/ASK evidence from the already accepted Pepperstone
Europe LIVE account for the 14 DEVELOPMENT regions that passed the maxT screen.

Safety / research boundaries
----------------------------
- Read-only cTrader Open API account scope.
- No order or account mutation payloads.
- Exact accepted account fingerprint and exact 14 symbol IDs/names must match.
- Protected-forward is never requested.
- Raw ticks stay on the Android device.
- The returned ZIP contains exact-window quote observations and hashes, not executed fills.
- A valid empty tick response is retained as authentic zero-observation coverage, never zero spread.
- If Pepperstone explicitly reports requested history as unavailable/outside retention, that
  exact symbol/side/time range is recorded as broker-unavailable and capture continues.
- Transient network/rate-limit failures retry and resume. Authentication/account/symbol
  identity failures and ambiguous API errors fail closed while preserving completed chunks.
- The bundle reports REQUEST_COMPLETED / PARTIAL_BROKER_HISTORY_UNAVAILABLE /
  BROKER_HISTORY_UNAVAILABLE for each symbol, side and exact requested window.
- Bundle integrity, observed authentic quote coverage and economic sufficiency are separate.
- This capture does NOT freeze candidates and does NOT by itself certify net economics.

Run
---
1. Extract this ZIP to one folder on Android.
2. Open V3_MAXT14_FRICTION_CAPTURE_RUN.py in Pydroid 3.
3. Run that same file. Existing safe cTrader OAuth state is reused where valid.
4. If Android/browser authorization is needed, complete it once and return to the same
   running Pydroid process. Do not start a second copy.
5. If interrupted, run the SAME file again; hash-verified completed or explicitly
   broker-unavailable chunks resume without discarding valid prior work.
6. Partial authentic broker history is a valid capture outcome when provenance is explicit.
7. When complete, return only:
   v3_friction_output/MXM_V3_MAXT14_FRICTION_EVIDENCE_V1.zip

Keep .mxm_v3_maxt14_friction_work on the phone until the transferred evidence is
independently accepted.
