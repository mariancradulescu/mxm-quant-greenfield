# B–E: one authentic W37 monetary spread measurement, before any further alpha trial

31 October 2026. Continuation of existing owner mandate after PR #296. **NOT another closed-strategy rerun.**

## Concrete source and economic question

Stop repeatedly assuming an unverified 10 or 20 bps spread on arbitrarily chosen historical M5 bars. Use already preserved authentic Pepperstone VIEW-only EURUSD and GBPUSD BID and ASK source observations from **the same entire ISO week 2026-W37**, with historical **strict-prior** price conversion rather than assumed fixed EUR/USD. Measure how expensive instantaneous displayed spreads actually were across the observed week, **as observed**, in EUR for exactly **1,000 *reference* base units**. This is a market-cost *support* study, not a directional prediction, not an executable round-trip cost and not a profit forecast.

Original source identities, already admitted and independently cold authenticated:
- EURUSD W37: 685,474 original events, run 39917922508, original ciphertext SHA256 `2403c74dfd81ab410f9b9c3bdabf4f3d5a5a4df0133cd0adc03933a364d539b6`
- GBPUSD W37: 1,275,114 original events, run 40179011821, original ciphertext SHA256 `3c643d7f4d72503deb39873e5bf10a8f6cb210d83d310d11150acd549dc7c08a`
- Prior native paired-source reception 40195796730 independently matched 1,214,095 atomic cross-symbol timestamp groups and proved 5-second strict-prior EURUSD FX source compatibility. The current experiment must revalidate original private source SHA identities before calculating anything.
- The two preserved original ciphertexts are restorable **offline from repository**, but private decryption occurs **only** inside existing protected `mxm-r3-custody-v1`; no new market request and no owner manual action.

## Predeclared causal and accounting law

A single **fixed** five-minute UTC grid over the **complete requested seven-day week**, not chosen after seeing spread. At each grid boundary, read only provider-source-timestamp quote observations **strictly earlier** than that boundary and no older than 5,000 ms for BOTH sides; GBPUSD USD liability uses same-grid native EURUSD bid, also strictly prior, fresh, noncrossed. Handle all same-ms updates atomically; conflicting same-ms duplicate side values invalidate that side until independently replaced. Locked/crossed, stale, unsupported and conflicting snapshots are counted as **UNAVAILABLE**, not zero-cost or filtered away. All 2,016 grid boundaries are accounted for in each symbol, including closed sessions. Every original record is scanned exactly once in chronological order. No observed price or individual result exported.

Native quote price scale is 10,000,000 raw ticks per quote unit. For one EUR-quoted reference lot of **1,000 base units**, the instantaneous USD spread debit is `1000 * (askRaw-bidRaw) / 10000000` USD. Conservative USD liability into EUR at strictly prior EURUSD bid: `1000 * (askRaw-bidRaw) / eurusdBidRaw` EUR. Report EUR median, p90/max, USD-independent pips and bps medians, per-UTC-hour **sample counts and medians**, plus explicit missing-reason counts. No minimum executable broker-volume claim; 1,000 is a unit reference only, not a ticket recommendation.

A measured one-time spread is **not**: commission, financing, slippage, bid/ask fill, available executable volume, latency, broker fill/arrival order, opening/closing total future friction, EUR200 funding admission, signal-level profit, 21 executed orders, independent confirmation or Cloud acceptance. Future economic candidates require contemporaneously available *both* entry and exit quotes plus product/commission/FX, risk/margin and continuous account accounting. The real research universe remains the full Pepperstone/cTrader authorized inventory, not these two pairs. W37 is previously **exposed DEVELOPMENT**.

## Execution and scope

The new independent reader `research_core_v4/laboratory/w37_authentic_spread_cash_20261031.py` performs source-blind causality/monetary selftests on PR. After reviewed merge, **only one** protected official-branch source read runs using the two frozen original restored archives, byte-identical native decoder already accepted in GitHub, existing R3 key and existing export verification. A single *aggregate public* result is retained by Actions, with **zero** original price events, keys or private trading records published.

No model parameters, closed experimental code/returns, operational C# entry path, margin/stop/Cloud guards or broker permissions change. No LIVE/DEMO orders; Cloud remains off.
