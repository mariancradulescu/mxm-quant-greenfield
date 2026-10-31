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

Native HISTORICAL Open API tick-price scale is **100,000 raw price units per quoted price unit**, documented by Spotware. EURUSD and GBPUSD have five digits and pipPosition=4; therefore 10 raw price units = 1 pip, and 1 raw unit = 0.1 pip. The previous script incorrectly divided the raw spread by 1,000 instead of 10; archived v1 pips must be multiplied by 100. EUR and bps ratios are invariant. For one EUR-quoted reference lot of **1,000 base units**, the instantaneous USD spread debit is `1000 * (askRaw-bidRaw) / 100000` USD. Conservative USD liability into EUR at strictly prior EURUSD bid: `1000 * (askRaw-bidRaw) / eurusdBidRaw` EUR. Report EUR median, p90/max, USD-independent pips and bps medians, per-UTC-hour **sample counts and medians**, plus explicit missing-reason counts. No minimum executable broker-volume claim; 1,000 is a unit reference only, not a ticket recommendation.

A measured one-time spread is **not**: commission, financing, slippage, bid/ask fill, available executable volume, latency, broker fill/arrival order, opening/closing total future friction, EUR200 funding admission, signal-level profit, 21 executed orders, independent confirmation or Cloud acceptance. Future economic candidates require contemporaneously available *both* entry and exit quotes plus product/commission/FX, risk/margin and continuous account accounting. The real research universe remains the full Pepperstone/cTrader authorized inventory, not these two pairs. W37 is previously **exposed DEVELOPMENT**.

## Execution and scope

The new independent reader `research_core_v4/laboratory/w37_authentic_spread_cash_20261031.py` performs source-blind causality/monetary selftests on PR. After reviewed merge, **only one** protected official-branch source read runs using the two frozen original restored archives, byte-identical native decoder already accepted in GitHub, existing R3 key and existing export verification. A single *aggregate public* result is retained by Actions, with **zero** original price events, keys or private trading records published.

No model parameters, closed experimental code/returns, operational C# entry path, margin/stop/Cloud guards or broker permissions change. No LIVE/DEMO orders; Cloud remains off.

## Material correction after PR #297 — original evidence UNCHANGED

The original published source and original protected GitHub run **41227762678**, artifact **13052347106**, are frozen as historical v1 evidence. Original native source git blob `4f915a8c19bc5358925a7516d5010f00bf71029e`. Its median PIPS `0.001/0.002` was 100-fold too small; corrected EURUSD `0.1 pip` and GBPUSD `0.2 pip`. Old original EUR1000-reference spread medians `0.008607 / 0.017211 EUR`, original bps medians `0.086068 / 0.147848` and original 305/255 complete sample counts **must remain byte-for-byte equivalent in corrected processing**. Pips arithmetic is independent of the original date/time and has no implication for historical fills.

Specification: https://help.ctrader.com/open-api/symbol-data/ historical tickData values are divided by 100000; original native two-symbol decoder has `digits=5` and `pipPosition=4` from authenticated original metadata. The previous source code and README also erroneously described raw scale as 1e7. It was harmless in the USD/EUR ratio but incorrect as source documentation. Correct USD spread numerator is `1000 * (askRaw-bidRaw) / 100000` for 1,000 base units; divide by the observed EURUSD BID after its *same* 100000 raw conversion and scale cancels.

### Coverage — no post-hoc selection

Original W37 *whole-week* five-minute grid 2016 slots per symbol: EURUSD 305 ready / 836 locked or crossed / 874 stale / 1 missing; GBPUSD 255 ready / 173 locked or crossed / 691 stale / 699 EURUSD-FX locked or crossed / 197 EURUSD-FX stale / 1 missing. Those were **source-time quote prerequisites**, not venue outages, calendar closure proofs or broker order rejects. The source was reconstructed by merging independently observed BID and ASK streams; sample-time cross with different original quote timestamps must NOT be represented as simultaneous broker-native crossed book or arrival order.

Corrective analysis separates the originally conflated `ask=bid` (locked) versus `ask<bid` (crossed), same-timestamp versus asynchronous-side book geometry and per-UTC-weekday/hour coverage, with 5-second causality rule unchanged and original results cryptographically pinned. Stale and locked samples stay **UNAVAILABLE**, no inferred substitute quote, no historical filling and no claim that valid-sample medians are population estimates. Coverage counts are deterministic diagnostics, **not** exploratory sampling to find profitable trade hours. Any conditional cost-aware future selection must be pre-committed on distinct data and separately evaluated for predictive NET after fees and EUR200 margin/risk.

These are two previously exposed DEVELOPMENT FX symbols only, not an exclusion of the entire Pepperstone/cTrader universe, not fresh alpha confirmation and not a new strategy result. No order/cloud permission change.
