"""Pydroid launcher for frozen FX cross-pair lead/lag pilot V2."""
from pathlib import Path
from m6.ctrader_capture import redact_text
from m6.pydroid_oauth import ensure_v2_authorization, force_fresh_v2_authorization
from research_core_v3.fx_cross_pair_quote_lead_lag_capture import ExpectedAccountUnavailable, LeadLagDiagnosticRunner, offline_preflight

ROOT=Path(__file__).resolve().parents[1]

def _once(app,token):
    r=LeadLagDiagnosticRunner(app["client_id"],app["client_secret"],token,ROOT)
    try:return r.run()
    finally:r.close()

def main():
    print("MXM Research Core V3 — FX cross-pair quote lead/lag pilot V2")
    print("PRIMARY: unchanged 72 cells | DIAGNOSTIC: 15-minute post-entry path only")
    print("READ ONLY | orders=NO | fill_authority=NO | protected-forward=NO")
    g=offline_preflight(ROOT)
    print(f"[PREFLIGHT PASS] tests={g['primary_tests']} relationships={g['relationships']} symbols={g['symbols']} base BID/ASK requests={g['base_side_requests_before_pagination']} diagnostic={g['diagnostic_horizon_seconds']}s")
    try:
        app,token,mode=ensure_v2_authorization(); print(f"[OAUTH] {mode}")
        try: out=_once(app,token)
        except ExpectedAccountUnavailable:
            print("[ACCOUNT RECOVERY] Frozen account absent under saved token; opening one fresh official cTrader authorization before any historical request.")
            app,token,mode=force_fresh_v2_authorization(); print(f"[OAUTH] {mode}"); out=_once(app,token)
    except KeyboardInterrupt:
        print("\n[PAUSED] Completed sanitized windows remain resumable under the exact frozen V2 contract."); raise SystemExit(130) from None
    except Exception as exc:
        print("\n[CAPTURE BLOCKED SAFELY]",redact_text(str(exc)))
        print("No orders, account mutation, fill authority, or protected-forward opening occurred."); raise SystemExit(1) from None
    print("\nCAPTURE COMPLETE. Return ONLY this ZIP to ChatGPT:")
    print(out)
    print("Do not run the superseded V1 package.")

if __name__=="__main__": main()
