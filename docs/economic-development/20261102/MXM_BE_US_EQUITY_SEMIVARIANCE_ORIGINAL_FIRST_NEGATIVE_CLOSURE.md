# MXM B–E — Original Pepperstone M5 semivariance experiment, 2 Nov 2026

## Owner mandate, evidence classification

New, single precommitted hypothesis; **NOT a retune or rerun of a previously closed mechanism**. The experiment is now **CLOSED NEGATIVE / NO PROMOTION / NO RETUNING**. All observations were from the already-authorized Pepperstone Europe LIVE VIEW original archives, read offline. There were **zero** LIVE/DEMO orders, zero Cloud activation, zero external suppliers, zero protected-forward reads, and no operational C# changes. No repository secret or raw price series appears here.

**Explicit limitation**: The numeric replay was executed locally in **Python**, NOT the existing native C# account engine. The current executor has no dotnet runtime. Consequently the result is a fully disclosed *development proxy*, not an independently confirmed C# funded-account backtest, not a Pepperstone broker P&L and not an economically qualified signal.

## Source provenance, frozen before viewing new outcomes

- Original Pepperstone 29-instrument M5 source: `MXM_RESEARCH_CORE_V3_SELECTED_M5_DEVELOPMENT.zip`, exact SHA-256 `09d999a595436de73c5edbb3d4a84002dc8b8779dc94393473d43afe1c3d9259`. All 17 selected USD-quoted US equity series were individually SHA-256 matched to their authenticated per-series manifest.
- Pepperstone 22 Sep 2026 current broker minimum-ticket snapshot: `MXM_COMPETITION_BROKER_UNIVERSE_V2.zip`, exact SHA-256 `9553fd3b60f4f5dc8428c30d19cde7d7a13cad12de18a27a93785836e97f5f77`. Its per-instrument minimum volumes and directional estimated minimum margins are **postdated to most historical bars** and provide only necessary modeled capacity, not historical broker execution evidence.
- Fixed pre-outcome registry ID: `BE-20261102-US-EQUITY-SEMIVARIANCE-IMBALANCE-2H-ONEFIRST`. Exact frozen specification SHA-256: `0e49eb0ca3cdb110a30776cfd4b9189b09b7d4c37af3bf7438d2965f1ebe959a`. Exact original executable Python source SHA-256: `7ce8c04b0849f13127637ca20e8825f20306a48702187a83cf2929ab3f1b139b`.
- The OWNER's private complete source script, specification, three cash ledgers, aggregate output and an **independent cold cash-ledger verifier** were preserved in the original chat execution artifacts. They are not retrospectively modified or replaced by this report. Original aggregate output SHA-256 `1394ce4e67a9cbf8c44e4c0690bcb01ca4c7f6e2c85b2ec9f31f632168e812d3`.

## Fixed causal mechanism and economic admission

All 17 original USD-quoted US equity symbols with dated broker minimum ticket BOTH_FEASIBLE are eligible, with no return-based symbol selection. On weekdays between 14:00 and 20:00 UTC, after a completed M5 bar, compute only the last 24 contiguous completed M5 log returns. Compare positive vs negative **squared** return sums; if negative semivariance dominates positive by >1.8 select LONG; if positive dominates negative by >1.8 select SHORT. This is an untrained signed tail-energy imbalance hypothesis, not a reused VWAP, gap, trend, wick, or historical-model scoring kernel. Use an ex ante 0.7-scaled one-hour realized-volatility cash proxy >2.5x declared round-trip friction to reduce economically hopeless source proposals. Rank simultaneous candidates by the frozen semivariance dominance score and lexicographic symbol. No future prices in feature selection.

Nominal next contiguous original M5 open entry; hold 12 complete bars, or stop at 2% adverse OHLC price, with later known price opening gaps explicitly flagged. One continuing hypothetical EUR200 cash account, no overlapping positions or resets; no entry if minimum volume's scenario stop + friction > EUR2 or 1% of current equity, margin > EUR80 or 40% of equity, or post-margin and cost reserve <EUR120. Historical BID/ASK, fee receipts, USD settlement multiplier, tick arrival, intrabar order of events and complete financing were **not** authenticated for these historical entries; a USD→EUR factor of 0.90, illustrative total round-trip spread + slippage bps and an additional fixed EUR0.05 per ticket were explicitly predeclared. Same-day session constraint prevents intended overnight holding, not proof of zero swaps.

## Actual original-source numerical execution — predeclared scenarios

| Scenario total spread + slippage | Model trades | Gross EUR | Assumed cost EUR | Model NET EUR | End EUR | Max realized DD EUR |
|---|---:|---:|---:|---:|---:|---:|
| 20 bps + EUR0.05 fee | 329 | -1.6056000 | 33.0958474 | **-34.7014474** | 165.2985526 | 35.8770604 |
| 40 bps + EUR0.05 fee | 329 | -1.6056000 | 49.7416948 | **-51.3472948** | 148.6527052 | 52.3110628 |
| 80 bps + EUR0.05 fee | 307 | -1.4238000 | 76.1668232 | **-77.5906232** | 122.4093768 | 78.1480592 |

3,802 source-only causal candidates across the 17 symbols. At baseline 20 bps, 175 trades in earlier exposed development yielded -EUR17.4286478 model NET, and 154 trades in later exposed development -EUR17.2727996. **Neither partition is independent holdout**. The 20-bps closed trades span 52 ISO weeks with at least one simulated trade; **zero** weeks had 21 or more simulated trades, **zero** broker-confirmed entry weeks. There is one flagged gap/end uncertain exit in each sensitivity, and no false execution-validity claim.

## Cold independent result and mandatory interpretation

A separate cold-read checker independently replayed cash balances **from the saved closed trade ledgers only**, without rerunning the predictor, reopening the market ZIP or changing trades. All 3 scenario receipts passed exact price-difference-to-USD-proxy gross, fees, continuous cash, chronological exclusivity, minimum-volume stop exposure, weekly counts and SHA checks. The checker provides **cash arithmetic** verification, not C# equivalence, real BID/ASK certification, or independent temporal confirmation.

There is **no demonstrated positive predictive economic NET**: the baseline hypothesis loses even before hypothetical friction (gross -EUR1.6056). This exact identity is CLOSED permanently without parameter retuning, changing direction, rescoping to the positive symbols or optimizing its costs. Do not attach the unqualified signal to the sole operational cBot.

Operational C# source, native account fences, registered historical strategies and protected controls are unchanged. No inference that the overall project or all distinct economic hypotheses are rejected.
