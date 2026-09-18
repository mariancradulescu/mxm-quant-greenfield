MXM QUANT GREENFIELD V2 — M6 PYDROID CAPTURE
================================================

THIS BUILD RESTORES THE WORKFLOW USED BY THE EARLIER FUNCTIONAL COLLECTOR.

FIRST RUN / CURRENT FRESH AUTHORIZATION
- Client ID + Client Secret are stored locally under:
  ~/.mxm_quant/m6_ctrader_capture_clean_v3/
- cTrader OAuth scope is accounts (view-only).
- The selected Pepperstone LIVE account is saved locally after broker verification.
- If cTrader returns more than one authorized LIVE account, a one-time LOCAL selector
  opens; choose the intended Pepperstone LIVE account once.

LATER RUNS
- No browser login while the saved access token is valid.
- If the access token is expired/near expiry, the saved refresh token renews it automatically.
- The saved LIVE account ID is reused automatically.
- Browser OAuth is used again only if local authorization is absent, revoked, or cannot
  be refreshed.
- Completed verified capture chunks are reused.

The access token is normally valid for about 30 days. The refresh token is used to obtain
a new access/refresh token pair. Credentials, tokens and raw account IDs remain local and
are never included in the evidence ZIP.

ANDROID RUNTIME
- Python 3.13 compatible
- protobuf==3.20.1 only
- no Twisted / pyOpenSSL / cryptography / Rust
- stdlib TLS/socket/urllib + official cTrader protobuf messages

ACCOUNT TARGET
Pepperstone - Europe LIVE only.
DEMO is never used for capture.
LIVE may have zero balance; balance is not a selection criterion.

RUN
Open M6_CAPTURE_RUN.py and tap RUN.

RETURN ONLY
capture_output/MXM_PW02_CTRADER_CAPTURE_da9e9a65f5c8.zip

Never return ~/.mxm_quant/, app_credentials.json, oauth_state.json,
account_selection.json, access/refresh tokens, authorization code or client secret.


LIVE SYMBOL MAPPING
-------------------
All 11 frozen canonical instruments are resolved from the currently authorized
Pepperstone LIVE symbol list. Mechanical broker suffix/punctuation differences may be
auto-resolved only when exactly one enabled LIVE symbol is structurally supported.

If mapping is zero/ambiguous, Pydroid prints a numbered local list. Enter the number of
the correct broker identity, or 0 to BLOCK. A user-selected mapping is saved locally
only after full symbol metadata confirms it is enabled/tradable. The saved mapping is
bound to the LIVE environment + broker symbolId + exact broker symbol name and is
revalidated on every run. If it becomes stale/disabled, it is cleared and selection is
requested again.

No V1/legacy strategy result, PnL, ranking or economic information participates in
mapping.
