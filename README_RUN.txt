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


BROKER PRODUCT / SESSION SEMANTICS
----------------------------------
Names that share the same underlying are NOT assumed to be aliases.

Before raw capture, the client fetches current full cTrader metadata for every credible
LIVE broker product and profiles:
- exact weekly schedule + scheduleTimeZone
- tradingMode
- enableShortSelling
- min/max/step volume
- holidays
- base/quote/category identity

For the frozen V2-C011 share basket, the active binding requires the common executable
US equity cash-session semantics. A standard cash-session share CFD and a 24/5 share CFD
are therefore different broker products. The client selects only the unique current LIVE
product whose actual schedule is compatible with the frozen cash-session requirement.
The user is NOT asked to choose between products with different session semantics.

Manual local selection remains available only when two broker identities have the same
structural/session semantic fingerprint and the frozen requirements do not distinguish
them.

Current schedule metadata is mapping evidence only; it is never relabelled as historical
session truth.


INDEX / FUTURES PRODUCT-FAMILY GATE
-----------------------------------
The broker mapping stage now obtains the current cTrader Symbol Category and Asset Class
catalogs in addition to the full symbol schedule.

Products on the same underlying are not treated as aliases merely because their prices
refer to the same market. In particular, a cash/spot index CFD and a futures/forward CFD
are separate broker products.

For frozen V2-C006/V2-C012, raw US500/NAS100 acquisition uses the non-futures cash index
CFD product. The broker-native feed may trade for extended hours; candidate cash-session
rules are a separate semantic binding and are NOT inferred from total weekly broker
hours.

For frozen V2-C007/V2-C008/V2-C009/V2-C010, a futures/forward product is likewise not
silently substituted for the frozen spot/continuous/non-futures identity.

A local user choice is never used to choose between products with different
contract/session semantics. Such differences are resolved by frozen semantics + current
LIVE structural broker evidence or fail closed.

Current category/schedule/holiday metadata is captured as current mapping evidence only.
It is not promoted to historical truth.
