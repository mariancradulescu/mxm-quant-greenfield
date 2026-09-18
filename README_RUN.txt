MXM QUANT GREENFIELD V2 — ANDROID-SAFE M6 CAPTURE
=====================================================

USE THIS PACKAGE, NOT ANY EARLIER PACKAGE.

WHY THIS BUILD IS DIFFERENT
The earlier package depended on cTrader's Twisted/pyOpenSSL Python SDK stack. On
Pydroid Python 3.13/aarch64 that stack tried to compile cryptography with Rust.

This build does NOT install or import:
- ctrader-open-api
- Twisted
- pyOpenSSL
- service_identity
- cryptography
- requests

It uses:
- Python standard-library ssl/socket/urllib
- official cTrader generated protobuf messages from Spotware OpenApiPy 0.9.2
- protobuf==3.20.1 (universal pure-Python wheel)

1) EXTRACT TO A NEW FOLDER
Extract MXM_M6_CAPTURE_PYDROID_PACKAGE.zip to a completely new Android folder.

2) RUN
Open M6_CAPTURE_RUN.py in Pydroid and tap RUN.
Do NOT install anything manually first.

If protobuf 3.20.1 is missing, RUN installs only that package using:
--only-binary=:all: --no-deps
so source compilation/Rust is disabled.

3) FIRST CLEAN SETUP
After preflight the browser opens:
http://127.0.0.1:8765/setup

Enter:
- Open API Client ID
- Open API Client Secret

They are saved locally only at:
~/.mxm_quant/m6_ctrader_capture_clean_v2/app_credentials.json

No previous MXM/cTrader authentication folder is read or imported.

Registered redirect in your approved cTrader application:
http://127.0.0.1:8765/callback

4) OFFICIAL CTRADER OAUTH
The local form redirects to cTrader.
Sign in there, choose the intended Pepperstone LIVE account, keep accounts/view-only
permission, and tap Allow access / OK.

The LIVE account can have zero balance. DEMO is not used.

5) CALLBACK
cTrader redirects to:
http://127.0.0.1:8765/callback

Pydroid receives the code and continues automatically.
The callback page also has a Return to Pydroid link.

6) CAPTURE
Transport:
Python stdlib TLS -> live.ctraderapi.com:5035
Protocol:
official cTrader protobuf messages, 32-bit big-endian length framing
Historical pacing:
about 4.76 req/s, below the official 5 req/s historical ceiling

No orders. No account mutation. No M6 economics.

7) RESUME
If interrupted, RUN the same M6_CAPTURE_RUN.py again.
Verified chunks are reused.

8) RETURN ONLY
capture_output/MXM_PW02_CTRADER_CAPTURE_da9e9a65f5c8.zip
