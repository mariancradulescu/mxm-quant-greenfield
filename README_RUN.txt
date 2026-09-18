MXM QUANT GREENFIELD V2 — ANDROID-SAFE M6 CAPTURE
=====================================================

USE THIS PACKAGE, NOT ANY EARLIER PACKAGE.

This build is specifically hardened for Pydroid Python 3.13/aarch64:
- no Twisted / pyOpenSSL / cryptography / Rust;
- Python stdlib TLS/socket/urllib;
- official cTrader generated protobuf messages;
- protobuf==3.20.1 only.

IMPORTANT OAUTH BEHAVIOR
------------------------
The running Pydroid script owns http://127.0.0.1:8765 for the whole OAuth exchange.
The browser NEVER uses an intent:// link and NEVER intentionally opens Google Play.

Do not start M6_CAPTURE_RUN.py a second time while OAuth is open.

1) EXTRACT
Extract MXM_M6_CAPTURE_PYDROID_PACKAGE.zip to a NEW folder.

2) RUN
Open M6_CAPTURE_RUN.py in Pydroid and tap RUN once.

3) FIRST CLEAN SETUP
Browser opens:
http://127.0.0.1:8765/setup

Enter:
- Open API Client ID
- Open API Client Secret

Saved locally only at:
~/.mxm_quant/m6_ctrader_capture_clean_v3/app_credentials.json

Registered redirect URI in cTrader must be EXACTLY:
http://127.0.0.1:8765/callback

4) OFFICIAL CTRADER AUTHORIZATION
The browser redirects to the official cTrader page.
Select the intended Pepperstone LIVE account and grant accounts/view-only access.
Tap Allow access.

Do not select DEMO for this capture.
The LIVE account may have zero balance.

5) CALLBACK
cTrader redirects to:
http://127.0.0.1:8765/callback

Correct success page:
"Authorization received."

There is NO Return-to-Pydroid browser link and NO intent:// URL.

After the code is exchanged, the script asks Android locally to foreground the already
installed Pydroid app. If Android blocks that foreground switch, use Android Recents to
return to the SAME Pydroid session.

DO NOT press RUN again.

6) CAPTURE
The existing script continues automatically after OAuth:
Python stdlib TLS -> live.ctraderapi.com:5035
accounts/read-only
no orders
no account mutation
no M6 economics

7) RESUME
If the capture process itself later stops, reopen the same package and RUN once.
Verified historical chunks are reused.

8) RETURN ONLY
capture_output/MXM_PW02_CTRADER_CAPTURE_da9e9a65f5c8.zip
