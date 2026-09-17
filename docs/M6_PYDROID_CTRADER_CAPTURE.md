# MXM M6 — Pydroid cTrader Open API capture

This tooling captures **DEVELOPMENT evidence only** for frozen `PRIMARY_WAVE_02`.
It does not run M6 economics, place orders, mutate the account, or open protected-forward evidence.

## 1. Install in Pydroid

In **Pydroid 3 → Pip**, install these packages:

```text
ctrader-open-api==0.9.2
requests==2.32.3
service_identity>=24.1.0,<25
```

Keep the extracted tooling folder intact. It must contain at least:

```text
M6_CAPTURE_RUN.py
m6/
  ctrader_capture.py
  ctrader_openapi.py
data/
  PRIMARY_WAVE_02_MATERIALIZATION_PLAN_V2.json
```

Do not put any credentials into the Python files.

## 2. Open API application configuration

You need an approved cTrader Open API application. Reuse your existing valid **Client ID,
Client Secret and registered Redirect URI** if you already used that app from Pydroid.

For the smoothest Android flow, the registered redirect URI should be a loopback URI such as:

```text
http://127.0.0.1:8765/callback
```

It must exactly match the URI registered for the cTrader Open API application.

On the first RUN the script asks only for:

- Open API Client ID
- Open API Client Secret (hidden input)
- Redirect URI

It never asks for your cTrader username or password. The values are stored only in the local
ignored file `m6_capture_local.json`. OAuth tokens are stored only under `.m6_secrets/`.
Neither location is included in the capture ZIP.

If several Pepperstone LIVE accounts are authorized, the client fails closed instead of
guessing. In that case set `ctid_trader_account_id` in the local configuration to the exact
authorized account ID before retrying. If an instrument name is genuinely ambiguous, use
`symbol_overrides` in the same local file with the exact broker symbol returned by cTrader.
Do not change Python internals.

## 3. RUN / OAuth browser flow

Open `M6_CAPTURE_RUN.py` in Pydroid and press **RUN**.

The script:

1. starts a local callback listener when the configured redirect is loopback;
2. opens the official cTrader authorization page in your Android browser;
3. requests only the view-only `accounts` scope;
4. you log into cTrader **in that official browser page**, not in Python;
5. verify the authorization is for account/view access and tap **Allow access**;
6. cTrader redirects to the registered callback;
7. the script receives the short-lived authorization code and immediately exchanges it for an API token;
8. the authorization code is discarded and no token/secret is printed.

If your already-approved application uses a non-loopback redirect URI, the script cannot
intercept another application's HTTPS redirect. It therefore asks you to paste the **full final
redirect URL** into hidden local input; the code is parsed and exchanged immediately and is not
stored.

On later RUNs, a valid local refresh token is used first. If refresh fails, browser
authorization is started again. Scope is never escalated automatically.

## 4. What the capture does

The client connects only to the cTrader **LIVE Protobuf endpoint** and performs the official
application/account authorization sequence. It selects a LIVE Pepperstone account fail-closed,
then resolves the exact ENABLED broker symbol for every frozen raw identity.

It captures each primary raw series once:

- US500 M15
- XAUUSD H4
- WTIUSD H1
- BTCUSD H1
- AUDJPY D1
- AAPL D1
- MSFT D1
- NVDA D1
- AMZN D1
- META D1
- NAS100 M15

C006 and C012 therefore reuse the same immutable US500 M15 raw file. There are 11 raw captures
and 12 candidate bindings.

Trendbars are requested in deterministic bounded windows with server pagination. Historical
requests are paced below the official 5 requests/second historical limit. The client retries
transient failures, preserves source gaps, never resamples, never synthesizes bars and never
forward-fills.

Only rows inside the frozen DEVELOPMENT interval are written. Bar availability must also remain
before the protected-forward boundary `2026-09-17T12:02:58Z`. Downloading an old bar today never
changes it into OOS/protected evidence.

Progress looks like:

```text
[1/5] Authorizing Open API application...
[2/5] Resolving exact ENABLED Pepperstone symbols
[3/5] Capturing read-only structural/auxiliary broker evidence
[4/5] Capturing 11 unique DEVELOPMENT raw market series
  [1/11] AAPL D1
  ...
[5/5] Finalizing deterministic evidence bundle
```

## 5. Resume

Work-in-progress chunks are kept under `.m6_capture_work/`. Every completed chunk is SHA256
bound in `resume.json`.

If Android/Pydroid is interrupted, press RUN again. Verified completed chunks are reused and
only missing/corrupt work is requested again. Final series are rebuilt deterministically, with
duplicate timestamps accepted only when their rows are byte-equivalent; conflicts block the
capture.

Do not delete `.m6_capture_work/` until the final ZIP has been returned and accepted.

## 6. Auxiliary evidence rules

The bundle records broker mapping, full current symbol metadata, assets, volume constraints,
commission/swap/session metadata, conversion-chain metadata, DEVELOPMENT M15 trendbars for the
current USD→EUR / JPY→EUR conversion-chain constituents, and broker-native expected-margin
responses when the API permits them with `accounts` scope. The current chain itself is not
mislabelled as historically point-in-time valid: that chain-validity question remains
`UNRESOLVED` unless independently proven.

Important classifications:

- current spread/swap/session metadata is **CURRENT SNAPSHOT — NOT VERIFIED HISTORICAL**;
- historical financing is `UNRESOLVED` unless genuinely historical evidence was obtained;
- point-in-time corporate-action history is `UNRESOLVED` if Open API did not provide it;
- historical WTI continuous-CFD/roll construction is `UNRESOLVED` if not independently supplied;
- approximate margin formulas are never authoritative;
- `ProtoOAExpectedMarginReq` is attempted read-only at broker minimum volume; if the server
  rejects it under `accounts`, that component becomes `UNRESOLVED` and scope is **not** escalated.

These unresolved states are intentional evidence gates, not economic failures.

## 7. Output

Successful output is written under:

```text
capture_output/MXM_PW02_CTRADER_CAPTURE_da9e9a65f5c8/
capture_output/MXM_PW02_CTRADER_CAPTURE_da9e9a65f5c8.zip
```

The folder/ZIP includes:

```text
raw/*.csv
auxiliary/conversion_raw/*.csv
evidence/account.json
evidence/broker_mapping.json
evidence/symbol_metadata_current.json
evidence/assets.json
evidence/expected_margin.json
evidence/auxiliary_status.json
provenance_manifest.json
bundle_manifest.json
CHECKSUMS.sha256
```

A safely blocked run may still create the same ZIP with `BLOCKED.json` and whatever
non-secret evidence was completed.

The bundle never contains cTrader username/password, client secret, authorization code,
access token or refresh token.

## 8. What to return to ChatGPT

Return **only**:

```text
MXM_PW02_CTRADER_CAPTURE_da9e9a65f5c8.zip
```

Do **not** send:

```text
m6_capture_local.json
.m6_secrets/
.m6_capture_work/
```

The next step is verification/materialization against the frozen plan and central
`data/DATA_MANIFEST.json`. Economic M6 research remains separate and does not start merely
because this capture finishes.
