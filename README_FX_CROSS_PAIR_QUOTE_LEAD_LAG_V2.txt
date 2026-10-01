MXM V3 FX CROSS-PAIR QUOTE LEAD/LAG PILOT V2 — DIAGNOSTIC OBSERVABILITY

AUTHORITY
- Run only V3_FX_CROSS_PAIR_QUOTE_LEAD_LAG_PILOT_RUN.py.
- Primary research design is unchanged: exactly 72 frozen cells, holding horizons 15/60/180 seconds.
- The added 900-second path is DIAGNOSTIC ONLY. It cannot enter the primary max-T family or promote the pilot.
- The V1 package is superseded and must not be run.

SAFETY
- Pepperstone Europe LIVE, cTrader Open API read-only accounts scope.
- No order request types are authorized.
- fill_authority=false.
- Protected forward remains closed.
- Raw historical BID/ASK ticks are processed locally and are not included in the transferable evidence ZIP.
- No automatic follow-on acquisition.

PYDROID
1. Extract this package into a NEW EMPTY folder.
2. Open V3_FX_CROSS_PAIR_QUOTE_LEAD_LAG_PILOT_RUN.py in Pydroid.
3. Press Run once.
4. Complete official cTrader authorization only if prompted.
5. When complete, return ONLY:
   MXM_V3_FX_CROSS_PAIR_QUOTE_LEAD_LAG_PILOT_EVIDENCE_V2.zip

Do not edit the frozen JSON authority files and do not run the superseded V1 package.
