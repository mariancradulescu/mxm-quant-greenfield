# MXM B-E: PR #302 economic-false-negative and M5 open-time audit

**1 November 2026.** One targeted correction to interpretation of ALREADY-FROZEN PR #302, not a new strategy, not an opened confirmation sample, not an economic rerun, not a modification to any closed mechanism.

## What was verified, and what PR #302 could not prove

The original user-controlled evidence ZIP SHA-256 `b49dc03da74cf4cead3e78168787795ca7f8c853220ba44e1e3985a46254e381` contains the exactly frozen November 1 scanner whose Python source SHA-256 is `e57d9ce6231d2dac8c001bcec2075c083ecec55fab88028b9aa400c761da1dd5`. A separate independent source-only interpreter reloaded the exact same original archive and all SHA-bound original Pepperstone input ZIPs for **157 original annual M5 series**, with **zero** future outcome labels or model execution. It independently reproduced the original prefilter counts, then isolated each economic veto.

| Past-data-only condition | Count |
| --- | ---: |
| Previous 12 M5-bar history complete | 1,260,041 |
| Price versus past volume-pressure disagreement | 7,074 |
| Volume condition | 3,161 |
| Postdated broker-terms and minimum ticket model compatible | 2,771 |
| Frozen 20-bps + commission scenario COST under EUR2 | **2,771** |
| Frozen hypothetical cost >= EUR2 | **0** |
| Prior 12-bar half-range cash proxy insufficient versus cost + EUR0.25 | **2,722** |
| PR #302's exact scenario-qualified proposals | **49** |

The speculative cost ceiling of EUR2 was **not** the actual count-dropping component for these 2,771 USD-normalized postdated contract candidates. The decision boundary was their **past** half-range reference relative to a 20-bps scenario plus EUR0.25. Median scenario cost = **EUR0.042966** (p90 EUR0.1066428; max EUR0.58626). Median *past* half-range cash proxy = **EUR0.0225** (p90 EUR0.09675). These values are NOT quotes, future labels, broker P&L, true contract multiplier-adjusted CFD cash returns, or proven execution prices. This explains the actual 2,722 reductions but cannot infer that those signals will be unprofitable.

Before that proxy veto, up to **168 historical source-only opportunities in one ISO week** met the input and narrow postdated contract conditions; after the original proxy rule, up to five. Neither number implies trades on a single EUR200 account, let alone HARD21 with real broker fills. A sparse genuine winner is still eligible to be a portfolio component even if it cannot individually meet the system-wide frequency objective. There is no permanent source symbol cutoff at 157, 62, FX, W37 or this conditional market subset.

The historical account started at EUR200. In a static **initial-ticket** only check, all 2,771 candidates have hypothetical postdated minimum margin and roundtrip scenario charge leaving >=EUR120; this is NOT an account-wide concurrent margin/risk/stop test, does NOT prove each actual tradable symbol is financed and cannot invent a future cash path or historical broker terms. The short source window and original 5,324 instrument contract metadata must not be treated as time-aligned historical BID/ASK/commission certification.

## Material causal chronology: M5 timestamp is bar OPEN, not complete OHLCV

Spotware official `ProtoOATrendbar.utcTimestampInMinutes` is the **open** timestamp: https://help.ctrader.com/open-api/model-messages/ . `Bars.BarClosed` in native cTrader Algo fires when a new bar is opened: https://help.ctrader.com/ctrader-algo/references/MarketData/Bars/Bars/ .

Thus a source bar timestamp 10:25 cannot be used for a 10:25 decision using its full high, low, close and volume. The earliest **nominal** bar completion is 10:30, but the actual next bar first tick/receipt can be **later**. In 2,710 of the 2,771 broker-geometry observations, the historical next bar has the nominal contiguous open timestamp; 61 lack it. Neither group has complete **arrival-time** verification from historical OHLCV. The original source selector logged `t[i]` as the candidate time while accessing `h[i],l[i],c[i],volume[i]`; this is an open-time labeling error, NOT established evidence that a live signal was available at the logged time. It does not retroactively change frozen PR302 counts or authorize rerun. The already-frozen full backtest was correctly not opened.

Added source-blind guard in a **new, isolated prospective-only helper** `research_core_v4/laboratory/m5_bar_timestamp_admission_20261101.py`: a full M5 observation is inadmissible at its opening timestamp, and a native-live decision additionally needs an explicit observed next-bar event receipt timestamp. Missing or late native reception never gets silently replaced by a nominal clock or a generated entry. The existing `m5_authentic_envelope.py` and every historic SHA-frozen laboratory implementation were restored/left **byte-identical** to official HEAD, because their strict frozen implementation identities cannot be mutated. This helper has its own key-free GitHub CI and does not alter any prior mechanism. No changes to C# order intent, Cloud admission, or stop-risk configuration.

## Full reproducibility and custody

Public machine-side exact source-only detailed result (SHA-256 `a96a93d6a3a694ce7a312e3b3d5d2d049edaae18ca09dadbe4f1303c327eebfd`) and a full independent Python reproducibility script SHA-256 `56c3a10ac08049a261becdf3db1208386e85d8de201e569c09c9157ebd3105a6` are preserved in the ZIP SHA-256 `7e16d71d208c1c9cd4b65e273dff3a12df722cb52d67ed0c4ac618435bb2f3e2` in OWNER private Library:

`/MXM Quant Greenfield/Evidence/BE_20261101_PR302_CostTimestamp_Erratum/MXM_BE_PR302_COST_TIMESTAMP_REPRO_20261101.zip`

These files are a separate *interpretation audit* of the frozen input-side experiment. The public companion JSON here is a small selected-field summary, **not claimed byte identical** to the complete independent receipt. Its user-controlled source ZIP is not accessible by GitHub CI, therefore CI separately proves the new standalone time/arrival selftests and existing product/regression invariants; independent machine-side original ZIP digest and exact-result reproduction are reported separately.

**B-E operating decision**: PR #302's exact policy remains closed under its declared scientific boundary. Its 49 counted entries must be called *20-bps scenario and past-range survivors*, not a broker opportunity impossibility bound. For a distinct new predictor require separately proven causal feature availability, source-side entry and exit quote timestamps, present minimum volume, contemporaneous FX, broker commission dating, stop/aggregate portfolio admission, and no protected holdout mining. Full Pepperstone research universe remains open. Zero LIVE/DEMO orders and zero Cloud activations; unknown-outcome retry remains prohibited.
