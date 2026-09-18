MXM QUANT GREENFIELD V2 — M6 PYDROID READ-ONLY CAPTURE
======================================================

THIS PACKAGE STARTS CLEAN.
It does NOT import or reuse any previous MXM/cTrader authentication folder, token,
refresh token, account grant, or old package-local configuration.

It captures broker/data evidence only. It does NOT run M6 economics and cannot place orders.

1) EXTRACT
Extract MXM_M6_CAPTURE_PYDROID_PACKAGE.zip to a NEW Android folder.
Keep m6/, data/, and tools/ exactly as packaged.

2) RUN — NO MANUAL PIP STEP REQUIRED
Open M6_CAPTURE_RUN.py in Pydroid and tap RUN.

The launcher first checks the exact cTrader runtime packages. If they are missing or
incompatible, it automatically runs Pydroid's Python pip against:
tools/requirements-m6-capture.txt

The installation output is visible in the console. After a successful first install,
the same RUN continues automatically.

3) FIRST CLEAN BROWSER SETUP
After preflight, the browser opens automatically at a LOCAL page:
http://127.0.0.1:8765/setup

Enter:
- Open API Client ID
- Open API Client Secret

Use the credentials of your approved cTrader Open API application.
Do NOT enter your cTID username/password on this local page.

The app credentials are saved only on this phone at:
~/.mxm_quant/m6_ctrader_capture_clean_v1/app_credentials.json

NO old ~/.mxm_quant authentication folder is read or imported.

The registered redirect URI in the cTrader application must be exactly:
http://127.0.0.1:8765/callback

4) OFFICIAL CTRADER AUTHORIZATION
After Save locally and continue to cTrader, the browser redirects automatically to
the official cTrader OAuth page.

There:
- sign in with your cTID/cTrader credentials;
- choose the intended Pepperstone LIVE account;
- grant view-only/account access;
- tap Allow access / OK.

OAuth scope is accounts only. Trading scope is never requested.

If LIVE and DEMO accounts both exist, this capture uses only LIVE.
The LIVE account may have zero balance; balance is not a selection criterion.
The runtime connects only to live.ctraderapi.com:5035.

5) AUTOMATIC CALLBACK
cTrader redirects to:
http://127.0.0.1:8765/callback

Pydroid receives the authorization code, exchanges it immediately for an access token,
stores OAuth state only locally at:
~/.mxm_quant/m6_ctrader_capture_clean_v1/oauth_state.json

and continues automatically. The callback page attempts to bring Pydroid back to the
foreground and also contains a Return to Pydroid link.

6) LATER RUNS
The saved Open API Client ID/Secret are reused from the NEW clean local folder so you do
not type them again. The official cTrader browser authorization still opens on every RUN,
so account/permission selection remains explicit.

7) PREFLIGHT
Before OAuth/capture the script verifies the frozen plan/hash, writable paths, callback
port, ZIP/SHA, secret guards, read-only request allowlist, mutation denylist and SDK
heartbeat availability.

8) PROGRESS
Normal historical pacing remains 0.21 s/request, about 4.76 requests/sec, below the
official cTrader historical limit of 5 requests/sec/connection.

9) RESUME
If Pydroid stops, RUN M6_CAPTURE_RUN.py again. Verified chunks are reused. Authorization
is performed again in the browser before the resumed LIVE broker session.

10) DEVELOPMENT BOUNDARY
Trendbars are included only when completion <= 2026-09-16T23:59:59Z and completion is
strictly < protected-forward start 2026-09-17T12:02:58Z.

11) RETURN ONLY
capture_output/MXM_PW02_CTRADER_CAPTURE_da9e9a65f5c8.zip

Do NOT return:
~/.mxm_quant/
.m6_capture_work/
app_credentials.json
oauth_state.json
client secret
access/refresh tokens
authorization code
