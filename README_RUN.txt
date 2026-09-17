MXM QUANT GREENFIELD V2 — M6 PYDROID READ-ONLY CAPTURE
======================================================

THIS PACKAGE DOES NOT CONTAIN CREDENTIALS OR TOKENS.
It performs data/evidence capture only. It does NOT run M6 economics and cannot place orders.

1) EXTRACT THIS ZIP
Extract MXM_M6_CAPTURE_PYDROID_PACKAGE.zip to one folder on your Android phone.
Keep the internal folders m6/, data/, and tools/ exactly as they are.

2) INSTALL THE PINNED PACKAGES IN PYDROID 3
Open Pydroid 3 -> Terminal, change to the extracted folder, then run:

python -m pip install -r tools/requirements-m6-capture.txt

Required versions are checked again automatically before OAuth.

3) RUN ONE FILE
Open M6_CAPTURE_RUN.py in Pydroid and tap RUN.
Do not edit Python internals.

4) FIRST RUN — LOCAL OPEN API APP CONFIG ONLY
Enter only the values belonging to your already-approved cTrader Open API application:
- Open API Client ID
- Open API Client Secret (hidden input)
- registered Redirect URI

DO NOT enter your cTrader username or password into Python.
The app configuration is saved locally in m6_capture_local.json and is never placed in the transferable evidence ZIP.

5) AUTOMATIC LOCAL PREFLIGHT OCCURS BEFORE OAUTH
The script stops before opening the browser if any of these fail:
- pinned Python dependencies/imports
- frozen acquisition plan and canonical SHA256
- writable output/work directories
- redirect URI and loopback callback-port bindability
- ZIP/SHA256 functionality
- secret-transfer guard
- accounts/read-only protocol allowlist and mutation denylist
- official cTrader SDK runtime import and idle-heartbeat path

CI also performs the same no-credential runtime import/preflight. CI does NOT connect to your broker account.

6) OFFICIAL BROWSER OAUTH
After preflight PASS, the official cTrader authorization page opens in the browser.
Log in to cTrader THERE, not in Python, and grant the requested VIEW/ACCOUNTS access.
The client requests scope=accounts only. It does not automatically escalate to trading scope.

If your approved redirect is a loopback URI such as http://127.0.0.1:8765/callback,
the local callback returns control automatically to Pydroid.
If your approved redirect is non-loopback, paste the FULL final redirect URL into the hidden prompt when asked.
The authorization code is used immediately and is not placed in the output bundle.

7) CAPTURE PROGRESS
Pydroid displays a compact live progress line after each historical request/chunk, including:
overall %, stage, instrument/timeframe, series %, completed windows/chunks, rows,
historical request count, effective req/s, elapsed time, and reused resume chunks.
Normal historical pacing is 0.21 seconds/request, approximately 4.76 requests/sec,
below the official cTrader historical ceiling of 5 requests/sec/connection.
No artificial sleeps are added; additional waits occur only for retry/backoff/reconnect/rate protection.
The official SDK transport heartbeat remains enabled; no trading or spot subscription is created for keepalive.

8) RESUME
If Android/Pydroid stops, RUN M6_CAPTURE_RUN.py again.
Hash-verified completed chunks under .m6_capture_work/ are reused; missing work continues.
Do not send .m6_capture_work/ to ChatGPT.

9) EXACT DEVELOPMENT CAUSAL BOUNDARY
A trendbar is included only if its COMPLETION timestamp (bar open + timeframe) is:
- <= the exact frozen DEVELOPMENT end 2026-09-16T23:59:59Z, AND
- < protected-forward start 2026-09-17T12:02:58Z.
A bar is never included merely because its OPEN timestamp is before the DEVELOPMENT end.

10) RETURN ONE FILE ONLY
After successful capture, return ONLY:

capture_output/MXM_PW02_CTRADER_CAPTURE_da9e9a65f5c8.zip

Do NOT return:
- m6_capture_local.json
- .m6_secrets/
- .m6_capture_work/
- client secret
- access/refresh tokens
- authorization code

The final evidence ZIP contains the transferable raw market data, auxiliary raw data actually captured,
broker mapping/account-symbol evidence with sensitive values removed, expected-margin evidence/status,
gap diagnostics, provenance, candidate bindings, bundle manifest, and checksums.
