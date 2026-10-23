# Authenticated 2026-W37 EURUSD — first full-week C# EUR200 development replay

Evidence source: [protected GitHub Actions run 39927756764](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/39927756764), job `weekly-cold-to-csharp` **120328241711 SUCCESS**, original artifact **12490835049** (`csharp-week37-development-modeled`), associated with official merged PR [#143](https://github.com/mariancradulescu/mxm-quant-greenfield/pull/143) and official source commit `ad8133f7d81596eb18f04f3f071d45549c058fdb`.

The byte-exact public model receipt is stored at [WEEK37_CSHARP_DEVELOPMENT_RECEIPT.json](WEEK37_CSHARP_DEVELOPMENT_RECEIPT.json), SHA256 `50662431d18349ef6ad46bd4e7113f95d31c34134558e5dbde8f88b3ad54b51a` (Git blob `9088ece9ceb4bbdc5712efd4c74688e2fa658913`). The actual source ciphertext and independent cold receipt were *already* durably preserved by PR #142; no source was recollected. The new model-result ciphertext has SHA256 `b04ef587cf44554a92a17d8db12002f3c42acd6e74ddadc281448162efe0c543` and is currently retained in the finite-lifetime original workflow artifact; this public report and receipt do **not** pretend that the exact model-result ciphertext has been committed durably to Git. The modeled result is reproducible from the durable original week capture through the pinned protected runner; it is not a scientific replication or historical execution proof.

## Actual measured engineering result (not broker P&L)

| Metric | Native C# development result |
| --- | --- |
| Input | 685,474 authentic Pepperstone EURUSD BID/ASK events, ISO UTC 2026-W37 (2026-09-07 through 2026-09-14 exclusive) |
| Partition | DEVELOPMENT only |
| Single initial capital | EUR 200.00 |
| Counterfactual entries / exits | 177 / 176, one open marked position |
| Model entry count meeting numeric 21 threshold | YES — **not** executed HARD21 |
| Final modeled cash balance | EUR 166.83138890003312 |
| Final modeled BID/ASK liquidation equity | EUR 167.07290562506634 |
| Net modeled change of marked equity | EUR -32.92709437493366, approximately -16.46% |
| Max modeled drawdown | EUR 33.84889565120277 |
| Independent Decimal cash difference | 7.799646330931089671990E-26 EUR |
| Independent Decimal equity difference | 8.241380421016828109377E-26 EUR |
| Broker orders / fills | 0 / 0 |
| Actual HARD21 | NOT PROVEN |
| Qualified economic edge | NOT PROVEN |

The model used the **existing shared C# Adaptive decision kernel, EUR200 continuous-account accounting and captured commission/quote-side FX components**, with unverified historic fees/effective dates, broker financing and swap, stop/partial fills, margin rules, execution latency, arrival precedence and executable historical liquidity. The 277,457 same-ms cross-side groups remain causally ambiguous. Neither a no-key CI SUCCESS nor a protected replay SUCCESS transforms the counterfactual into proven profit, realistic total costs or 177 actual broker trades. The run provides adverse DEVELOPMENT evidence against current settings and does not authorize promotion, selection or confirmation.

## Account / authority state and scientific continuation

- No change to the canonical economic TrialBook, identity budget, checkpoint, active delegation, OWNER1807 or separate DEVELOPMENT / CONFIRMATION / PROTECTED partitions.
- No additional broker requests, no LIVE/DEMO orders and no Cloud activation; existing protected custody recipient reused.
- One independent pass verifies arithmetic of the same modeled ledger; it is **not** an independent market sample or native cTrader replay.
- The next justified scientific work is to understand the loss contributors on W37 (gross vs captured spread/fees vs assumed slippage; stop/lifecycle decisions and holding time) before new strategy identity spend; realistically quantify uncertainty from cost/fill assumptions. An unfavorable week cannot become a qualified edge by merely reaching 21 modeled entries.
- Complete native cTrader callback-order and crash-recovery acceptance remains open. True HARD21 requires actual qualifying broker-executed trades under the stated authority; no such trades occurred here.

This commit is a durable public **result of actual economic experimentation**, not an infrastructure-only certificate, not a new research admission and not preservation of a plaintext account, market stream or secret.
