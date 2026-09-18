MXM QUANT GREENFIELD V2 — M6 PYDROID READ-ONLY CAPTURE
======================================================

THIS PACKAGE DOES NOT CONTAIN CREDENTIALS OR TOKENS.
It captures broker/data evidence only. It does NOT run M6 economics and cannot place orders.

1) EXTRACT
Extract MXM_M6_CAPTURE_PYDROID_PACKAGE.zip to one Android folder.
Keep m6/, data/, and tools/ exactly as packaged.

2) INSTALL
In Pydroid Terminal, from that folder:
python -m pip install -r tools/requirements-m6-capture.txt

3) RUN
Open M6_CAPTURE_RUN.py and tap RUN.

RUN does NOT ask for cTrader/cTID username/password in Pydroid.
RUN does NOT ask for Client ID/Secret in Pydroid.
An old package-local m6_capture_local.json is ignored.

4) AUTHORIZATION — EVERY RUN
Frozen target: Pepperstone - Europe LIVE.

If this phone still has the previously validated Open API APPLICATION credentials at:
~/.mxm_quant/a118_c02_openapi_v1/credentials.json

V2 reuses ONLY that application's Client ID and Client Secret.
Legacy SCOPE_VIEW is accepted only to recover those application credentials.
Old DEMO/LIVE grants and old access/refresh tokens are NOT used to skip the browser.

Every RUN opens the official cTrader authorization page. In the browser:
- log in with cTID/cTrader credentials;
- select the intended Pepperstone LIVE account;
- grant the requested view-only permission;
- tap Allow access / OK.

If LIVE and DEMO are both authorized, the capture still selects only Pepperstone LIVE.
The LIVE account may be unfunded; balance is not an account-selection criterion.

OAuth scope is accounts only. Trading scope is never requested.

If application credentials are no longer available locally, RUN still opens the browser,
but first shows a LOCAL page at http://127.0.0.1:8765/setup. Enter the approved Open API
Client ID and Client Secret there once. That local page redirects directly to cTrader.

5) AUTOMATIC CALLBACK
Registered redirect:
http://127.0.0.1:8765/callback

After Allow access, cTrader redirects to localhost. Pydroid receives the code, exchanges
it immediately for the token, stores V2 private state at:
~/.mxm_quant/m6_ctrader_capture_v2/credentials.json

and continues automatically. The callback page attempts to return Android to Pydroid
automatically. If Android/browser policy blocks the foreground switch, Pydroid is already
continuing and the callback page provides a Return to Pydroid link.

6) LATER RUNS
Browser authorization is intentionally repeated on every RUN so account and permission
selection remains explicit. The Open API application Client ID/Secret may be reused
locally, but a remembered access/refresh token never bypasses the browser.

7) PREFLIGHT
Before OAuth/capture the script verifies dependencies, frozen plan/hash, writable paths,
callback port, ZIP/SHA, secret guards, read-only protocol allowlist/mutation denylist,
and official cTrader SDK heartbeat availability.

8) PROGRESS
Normal historical pacing: 0.21 s/request, about 4.76 req/s, below the official 5 req/s
historical ceiling.

9) RESUME
If Pydroid stops, RUN again. Verified chunks are reused. Browser authorization is
performed again before the resumed broker session.

10) DEVELOPMENT BOUNDARY
Trendbars are included only when completion <= 2026-09-16T23:59:59Z and completion is
strictly < protected-forward start 2026-09-17T12:02:58Z.

11) RETURN ONLY
capture_output/MXM_PW02_CTRADER_CAPTURE_da9e9a65f5c8.zip

Do NOT return anything under ~/.mxm_quant/, .m6_capture_work/, client secret,
access/refresh tokens, authorization code, or m6_capture_local.json.
