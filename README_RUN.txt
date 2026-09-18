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


LIVE BROKER PRODUCT PREFLIGHT
-----------------------------
After LIVE account authorization the collector performs ONE complete structural preflight
before any ExpectedMargin, conversion-history or primary historical market-data request.

It loads and caches for this run:
- Pepperstone LIVE trader/account truth
- all assets
- all asset classes
- all symbol categories
- the complete current light-symbol universe
- archived-symbol records returned by cTrader
- full current symbol metadata for every structurally relevant broker product

The resolver treats broker products as different identities, not aliases. It distinguishes:
FX spot/margin CFDs; spot metals; spot energies; spot crypto; cash index CFDs;
index/commodity forwards or futures CFDs; standard cash share CFDs; extended-hours share
CFDs; index/share/commodity perpetual CFDs; other perpetual CFDs; other CFDs; unknown.

PERPETUAL and FORWARD/FUTURES identity is resolved before generic index/share/commodity
classification. A contradictory broker record blocks instead of being guessed.

The frozen current bridge expects:
US500 -> standard cash US500 index CFD
NAS100 -> standard cash NAS100 index CFD
XAUUSD -> standard spot-gold CFD
WTIUSD -> standard spot WTI/crude-oil CFD (currently publicly corroborated as SpotCrude;
          LIVE symbol metadata remains authoritative)
BTCUSD -> standard BTCUSD crypto CFD
AUDJPY -> standard AUDJPY margin-FX product
AAPL/MSFT/NVDA/AMZN/META -> each standard cash-session US share CFD

Products such as US500-F, NAS100-F, XAUUSD-F, Crude-F, -24 shares and perpetual products
are retained as structural alternatives/exclusions; they are never substituted merely
to obtain more history or trading hours.

Before historical capture the console prints ALL 11 rows with:
CANONICAL | BROKER SYMBOL | SYMBOL ID | PRODUCT FAMILY | CATEGORY | ASSET CLASS |
ENABLED | TRADING MODE | MAPPING POLICY | MAPPING EVIDENCE | STATUS

Only:
BROKER PRODUCT PREFLIGHT: 11/11 PASS
allows the run to continue.

Any other result prints:
BROKER PRODUCT PREFLIGHT: X/11 PASS — CAPTURE NOT STARTED
and produces a blocked evidence bundle with diagnostics for every canonical identity.
There is no manual symbol-product selection between different structural products.

Archived symbols are lineage evidence only and can never replace a current enabled product.
Current schedules/categories/asset classes are current mapping evidence only; they are not
promoted to historical 2022-2026 truth.

READ-ONLY AUXILIARY EVIDENCE
----------------------------
After 11/11 mapping PASS, broker-native SymbolsForConversion is used for USD->EUR and
JPY->EUR conversion-chain binding and ExpectedMargin is queried for the mapped symbols.
Neither operation places an order or requests trading scope.

Historical trendbars start only after the complete broker-product preflight passes.
Historical tick data is NOT bulk-downloaded in this build because no frozen Discovery
cost requirement justifies that acquisition yet.

C008 remains historically UNRESOLVED for continuous-CFD/roll construction until causal
roll-effective timestamps and adjustment semantics can be proved. C011 historical
corporate actions, financing, short eligibility and historical session versions likewise
remain UNRESOLVED unless point-in-time evidence is actually obtained.
