# MXM B–E — existing native C# H1 policy, authenticated annual source (30 October 2026)

## An actual product-policy economic gate, not a new optimized model

This is a **first**, frozen annual evaluation of the EXISTING `MxmRelativeStrengthPortfolio.cs`, already wired to the native cTrader robot's **observation-only** portfolio policy. No trading path or safety control is changed by this study. The existing C# policy was not previously qualified to trade. This trial does not promote it.

The original repo HEAD at model/rule selection: `4c3a4e66d56ca7e82215f9f4a12e2c4f82a04234`, C# policy Git blob `25019b000745058c6d7a59196a1fe8256ee41ea3`.

## Source and exclusion of hindsight

Both original PRIMARY145 year-long M5 archives were independently hashed before this study:

- selected archive SHA256: `09d999a595436de73c5edbb3d4a84002dc8b8779dc94393473d43afe1c3d9259`
- delta archive SHA256: `37a47cb9ff8bc9cce50aee830c1bd286b9db359df1200d4e4b9a0ce35f8fd12e`

Identity roster fixed before results: the eight **lowest numeric broker-symbol IDs** among the 145 PRIMARY Forex (Spot) series: `[3,7,9,10,11,12,13,14]`. This roster is dictated by the pre-existing native policy's joint 3–16 symbol contract, not outcome ranking. It neither restricts the wider Pepperstone research universe nor proves broad-universe quality.

Use every ISO week from **2025-W40 through 2026-W22** inclusive (35 complete weeks), deliberately outside the two closed study's 2026-W24..W37 evaluation period. These weeks were not separately reserved as a pristine forward holdout; all results are **DEVELOPMENT**. Do not reselect winning symbols or weeks retrospectively.

H1 close = last close from exactly twelve original M5 observations within an hour. Absent hourly components are genuinely unavailable, not interpolated. Replay each observed hourly close in chronological and deterministic alphabetical symbol order; simulated *observation availability* at `hour-end + 5min` is explicitly **not** a broker-received timestamp. The same exact existing C# policy chooses a single joint H1 target, or flat, based only on completed hourly closes, previous 12h and UTC 07–15 weekdays. Research settlement assumes hypothetical next M5 open at hour-end+5min to hour-end+60min, at most one position at a time. Historical BID/ASK, fill quality, real bid/ask spreads, commissions, swap, conversion, account-native volume lattice and EUR200 margin are **not** available from annual OHLCV and **not** invented.

The causal offline Python reference was hashed before its first outcome evaluation: SHA256 `a3d3651534ba97b48adb8a582ef9df2571544ebf5f1f18de0fe9594bffb30e8f`.

## Previously completed source-only local result — not native C# confirmation

35/35 complete weeks have at least 21 modelled proposals, 1,229 proposals and 1,229 observed price episodes, zero censored. Sum of signed individual percentage gross returns: **−137.984795719851 bps**; minus a purely hypothetical 20 bps/episode: **−24,717.98479571985 bps**. All 35 complete weeks fail the hypothetical 20 bps economic test. This is a net **bps-sum scenario**, NOT EUR200 account P&L, historical Pepperstone costs or actual executions.

The original-derived private episode ledger and input-to-C# tape were saved only in owner's ChatGPT Library:

`/MXM Quant Greenfield/Evidence/PRIMARY145_NATIVE_H1_CSHARP_20261030/`

Tape of 32,607 exact M5-derived completed H1 source events, plus separate private next-open historical settlement observations: SHA256 `7157db48811ed1f1e4583ab567c6e04c876a4c4738c4bd242f182632fff54ebb`.

## Machine-side **actual C#** source parity/receipt (new product integration)

Existing executable: `research_core_v4/laboratory/csharp/portfolio_policy/MxmPortfolioPolicy.csproj`, linked to the **original** `MxmRelativeStrengthPortfolio.cs` (no model rewrite). New source-blind executor `research_core_v4/laboratory/native_h1_csharp_annual_receipt.py` authenticates and decrypts the exact derived source tape from **RSA-OAEP SHA256 + AES256 OpenPGP** encrypted Git payload; checks owner existing custody private key fingerprint; executes the actual C# project once entirely offline on the authentic 32,607 H1 observations; calculates each C# target's historical gross return only after the target is chosen, and compares its aggregate to the frozen local Python reference. Its private C# per-decision outputs are re-encrypted under the exact existing recipient public key, before GitHub artifact publication. Public artifact contains weekly aggregates and explicit limitations only.

- Encrypted exact tape SHA256: `1434d71a5f22fec2e8b98ab268297c4b673ca741ebe21afd186cecfdcd39f013`.
- Repository-only public recipient key SPKI SHA256: `464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11`.
- C# parity is **NOT** proven until the protected Actions job completes and its report matches; failed/missing secret does not become a synthetic success.
- No unencrypted private source data, series closes, episode-level outcomes, raw ZIPs or keys are public in this PR.

**Go/no-go:** if machine-side actual C# confirms the negative net hypothesis, this existing observation-only policy remains economically unqualified and must not be routed into order submission. If native output diverges, fail closed and investigate the *same original hypothesis* without result-driven retuning. The existing order protections, Cloud block, broker ambiguity fence, and LIVE/DEMO prohibitions remain unchanged.
