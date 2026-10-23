# C# Native bar-contiguity defect found by authentic Pepperstone readback

23 October 2026. Existing B–E mandate. No new market-source collection, orders, or scientific candidate selection.

## Empirical evidence
On execution-branch commit `931e5964ea9147495cc2218bcafb2bcaecc471c2`, protected run `39897981975` succeeded against exactly **28,212** original Pepperstone EURUSD BID/ASK events, original source run `39660692230`. But its new C# portfolio replay modeled **zero entries** and final cash/equity **EUR200**, while the older single-symbol counterfactual modeled **seven** entries and EUR199.418182 under a different, uncertified model. These numbers are not comparable performance results or real broker fills.

The native adaptor formed a `MxmBarClose` event at the **first observed quote timestamp in the new five-minute bucket**. The shared C# `MxmPortfolioAccountReplay` then calculated `bar.Utc - lastBarUtc == 5 minutes` to decide whether to keep its causal six-complete-bar kernel. Real first-quote arrivals vary around the fixed bucket boundary; this silently reset the kernel on normal feeds, suppressing signals. A synthetic fixture with perfectly aligned bucket timestamps had concealed the defect.

## Corrective contract
`MxmBarClose` now carries an optional `BoundaryUtc` in addition to its **observed, actionable Utc**. The bar boundary is used *only* for calculating the continuity of adjacent closed-bar identities. A strictly validated condition requires a UTC boundary no later than the actual observation, within the same five-minute bucket. `PendingAt` remains the actual observed quote timestamp. The engine still refuses to execute a completed-bar signal using a quote from that same instant; only a strictly later original quote may execute.

The native readback derives `BoundaryUtc` from `timestamp / 300000 * 300000` without changing any original quote timestamps. If data genuinely skips a whole bar the kernel still resets. An artificial multi-symbol replay with jittered first-tick observations and an explicit future-boundary negative case now proves the distinction. The synthetic native quote-shape test also deliberately jitters the first tick of each bar, and the existing Python cash / MTM crosscheck remains mandatory.

The native protected workflow adds bounded public diagnostics (number of bar-close events, accepted grouped BID/ASK timestamps and reasons for modeled admission rejection), while the full ledger remains inside existing encrypted custody.

## No unjustified promotion
This fixes **causal replay validity**, not native cTrader callback timing parity, true historical order fills, exact Pepperstone cost, account conversion, margin or HARD21. Original data remains 4-hour, EURUSD-only, scientifically DEVELOPMENT-exposed. The older seven-entry reference uses a different scenario; the goal is to identify the difference, not optimize a winning leaf from reused data.

Original active authority, OWNER1807, economic V2/C033, original encrypted corpus, locked protected-forward boundary, Cloud execution and trading permissions remain unchanged. No LIVE or DEMO order is authorized or placed by this work.
