# MXM PRIMARY_145 — actual originals, source and first economic development study

Date: 2026-10-30. Repository official branch HEAD after PR #280: `7fe2028ce4c04f3762ff307261cfeccebac1e918`.

## Input custody
Originals were located in owner's connected ChatGPT file library and copied privately for **read-only** study; no source CSV or raw OHLCV original is included in this evidence package. The exact SHA256 of the two entire archives match the accepted GitHub PRIMARY_145 manifest:

- `MXM_RESEARCH_CORE_V3_SELECTED_M5_DEVELOPMENT.zip`: `09d999a595436de73c5edbb3d4a84002dc8b8779dc94393473d43afe1c3d9259`
- `MXM_RESEARCH_CORE_V3_HIGH_QUALITY_DELTA_M5.zip`: `37a47cb9ff8bc9cce50aee830c1bd286b9db359df1200d4e4b9a0ce35f8fd12e`

Sources authenticated on actual bytes: 157 CSVs; 12 supplementary series excluded, leaving PRIMARY 145 with exactly 11,406,418 M5 rows. Non-price-dependent clock support: 53 observed ISO UTC weeks. The source collection stops on 2026-09-16; protected-forward material untouched.

## Source scripts and pipeline

- `source_chunk.py` verifies original per-member SHA256, timestamps, OHLC, nonnegative volume, exact M5 support. Run it on the original ZIPs in five partitions: base 0-29, delta 0-32, delta 32-64, delta 64-96 and delta 96-128. SHA256 of entire archives was separately checked before reading.
- `multiscale_features.py` makes causal M5 features from the actual original ZIPs, in the same five partitions. No future-censor filtering at selection time.
- `evaluate_multiscale.py` runs a **single** pooled Ridge (alpha 1000, eight fixed features), train before 2026-06-01, embargo until 2026-06-08, evaluation until 2026-09-17. Uses a single hourly modeled opportunity slot, price-only forward returns and assumed 10/20/40bps round-trip costs. A final print-only KeyError was fixed after results were written; **the economic model was not re-run**.
- `cold_economic_attribution.py` cold-reads the original first study's episode outcomes without re-running the strategy, excludes partial W38 and reports 14 complete W24-W37 weeks and concentration risks.

## Verdict and limits

The actual full-week assessment generated 241 proposed opportunities, 236 future-observable, 5 censored. Sum of per-trade price returns was +3,786.50 bps gross, -933.50 bps after an **assumed** 20bps per trade. Only 3 of 14 complete weeks had 21 or more **proposals**, which are emphatically NOT executed broker orders; 11 weeks fail even the necessary proposal-count bound. Partial W38 would add +6,301.19 gross bps and must not be used to certify complete-week performance. Do not tune or reuse this rejected model as a proven edge.

**No** dated Pepperstone BID/ASK fills/costs, min-lot EUR200 funded replay, verified financing/slippage, true live broker equity, HARD21 executed entries, reserved confirmation, cTrader Cloud reception or safe ambiguous-order retry proof were produced. Research is DEVELOPMENT only. No real/demo orders, no cloud activation.

## GitHub evidence

- [PR #280 source-calendar repair](https://github.com/mariancradulescu/mxm-quant-greenfield/pull/280), merged after all three CI checks succeeded.
- [Annual-source semantics CI #41046295939](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/41046295939).
- [R3 technical CI #41046295852](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/41046295852).
- [Native gateway C# CI #41046295831](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/41046295831).

The authentic annual-byte reception and economic ML study were performed **locally in this ChatGPT execution** using the owner's Library originals. Their receipts are in this evidence package, **not** posted to GitHub as authenticated CI results. Do not misrepresent a successful GitHub PR check as verification of these original bytes or economic results.