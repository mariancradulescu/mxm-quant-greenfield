# Observed commission FX: native integration result and current product corrections

PR218 merged **e923f37efc2df64b82bd15c26fb60ffe44b9b64f**, after all five required CI suites succeeded on their first attempt. Gateway40488629253/job122136651716 executed all13 new compiled/structural/source-scope tests, including unique multileg topology, debit side/rounding, no favorable ambiguity resolution, no stale longer fallback, same-price observations, epoch reset and the complete artificial source-to-fee path. The actual native cTrader .algo compiled with the same shared observer/FX graph/commission implementation. Native Robot execution remains unqualified.

[Run40488994775](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/40488994775), job **122137881195 SUCCESS attempt1**: complete original1140 observations and captured minimum-volume terms were authenticated using the pinned decoder and existing custody key, then the compiled C# ledger was reconciled row-for-row against independent Python graph/Decimal arithmetic. Evaluation had no private key. Its private result was encrypted to the existing recipient; a later separate custody process verified the exact ciphertext/plaintext hashes, provenance and1140 rows. This is separate process readback within the same job, not an independent external audit or separate broker receipt.

## All-source component availability, not liquidity or entry qualification

| Original source | All saved events | Conditional commission-component estimates | Explicitly unresolved |
|---|---:|---:|---:|
| EURUSD/1 | 336 | 330 | 6 ticket-book observation/geometry/age |
| GBPUSD/2 | 482 | 427 | 52 required FX-book observation/geometry/age; 3 ticket-book |
| SpotCrude/250 | 322 | 322 | 0 |
| **Total** | **1140** | **1079** | **61** |

The52 GBPUSD cases demonstrate the separate conversion-source dependency: a locally available ticket book alone is insufficient for a nonzero USD commission estimate in EUR. No stale substitute or favorable path was used. SpotCrude's literal zero declared commission/minimum requires no FX multiplication for that component; this does not resolve spread, conversion/PnL charges, financing, stop execution or slippage. All three identities and every row remain in the result. No instrument or time subset was selected on returns.

**1079 is not a new healthy-source count or a trade count.** This commission-only contract permits conditional arithmetic from carried noncrossed/locked geometry and initial observations, with an explicit local side-age limit. It does not certify source as-of time, continuous observation, firm/executable prices, actual fee conversion/rounding, full entry admission or all-in costs. The old fixed strict source-quality result remains940 healthy/200 unavailable/zero observed stretches >=5minutes, unchanged. Initial latest snapshots, BID=ASK and silence retain all previously documented limitations. The complete diagnostic capture remains excluded from confirmation and directional response tests; no strategy or account replay was run.

Captured metadata applies only within original contact05:31:01.143636–05:37:04.067853UTC on27October2026, without individual metadata-response timestamps or simultaneous snapshots. This check supplies a conditional observed debit-side commission-FX estimate, not present or September historical broker charges, loss-side PnL conversion or proof of risk at stop. Native AmountRisked/PipValue limitations remain open.

## Original artifacts and recovery

Original Actions artifact **12725734663**: ZIP **7389 bytes**, SHA256 `d4ce88a1ce8389f01ecfced07d6e297ab4c94331269a0ff5307acea96ebd1d18`, stored byte-exact as `observed-cost-fx-40488994775/artifact.zip.b64`.

- `receipt.json`:1659bytes, SHA256 `7f86d54f855b8216ef02f42abdec515f11308552ae2d57d49486038bf90cdc3b`.
- `ledger.mxmenc`:5744bytes, SHA256 `344f505c0cf23fddbf796b362c34d0efe93497424256859fee8eb2fb93445890`; no source or derived cost values were decrypted in Work or made public.
- `cold.json`:552bytes, SHA256 `2475705c55346244827b921e5658f643e6bdb3014878eed6cce5ca3c205b74ab`.

Both direct public copies match the original archive and native log. Private result commitment `5937c6e69ac98b292b8aed7e5f04b24c5b53227f797c755e56c743006b6dc1f5`; derived input `c7b1b527db6f9ee4d16eff3c188a4f7230a98dd7db15b4ff42c3ac4f5e62c3b1`; **original218** evaluator DLL `e8df1483af6044bd8ea9e95af9afcc59de299b5d35898934fdc0d76630777a42`; policy `506b94740911f3a068dbe0b049c316b483ab8e4b1e7cd37fdcda9f9a8f68b4b0`. Original source40455704891/privatead08d8…/manifest39f224… and decoderd2fae… remain bound, not reconstructed.

`python3 -m research_core_v4.laboratory.verify_observed_cost_fx_result` verifies all original bytes/provenance/counters/no-promotion flags without key, broker, compiler or replay. Optional `--out <new-directory>` restores **only the exact encrypted ledger**, refuses existing/symlink output and never decrypts or overwrites. Five original/corruption/substitution/symlink/restore tests protect this path.

## Product corrections after the original native result

Review found that the newly added fee-source receipt clock also needed a declared **backtest time domain**. A fast native backtest can process a minute of simulated market time within a second of host time. Using host uptime for that case would retain old FX observations too long. The product now uses simulated broker UTC milliseconds for observer epochs, updates, reads, cost leases and the final expiry check when IsBacktesting; live callbacks use process monotonic time. Simulation UTC must be explicitly UTC/nonnegative; clock regression still latches the existing observer fault. Sampled observation UTC is labeled simulation when applicable and never becomes a source event timestamp. Compiled artificial clock tests and actual product compilation are required before merging this correction. No Robot/backtest is launched, and no actual historical availability or performance is claimed.

Conversion eligibility is also explicitly restricted to **Cost Conversion Symbols**, including a source that is already subscribed in the trading roster. A trading instrument does not become an FX edge merely because BaseAsset and QuoteAsset differ; a caller must declare an appropriate conversion quotation contract. Duplicate roles reuse one observer/subscription. An empty conversion roster admits only identity/no-needed-FX arithmetic and holds other fee estimates. The Director configures these sources as part of an eventual admitted product; no OWNER operation is requested. Assets/prices alone do not certify currency-route unit applicability or execution.

These are current product corrections, not retrospective changes to the original raw-source1140-event program, which already aged by captured receipt chronology. They cannot change the original native ledger or original218 DLL hash; no native task or model is repeated. The updated binary is separately compiled/tested in required CI. Historical economic identities and source criteria remain closed.

## Continuing economic boundary

This is functional integration and authentic commission-component evidence; it is not an economic strategy result. A new economic mechanism still requires a separately frozen exposure/response protocol with appropriate future/dated data, total friction, loss conversion and stop/execution assumptions, followed by independent confirmation. Do not rescue old models or rerun source/margin/cost counts to increase availability. The entire authorized Pepperstone universe remains open; declared conversion sources are engineering inputs, not a profitable roster.

Single continuous EUR200, existing custody/authority/risk limits and HARD21 are unchanged. Zero new broker requests, directional responses/models, orders, Cloud activations or capital resets in this continuation. B–E OPEN; robust NET edge, effective HARD21 and operational native Robot reception remain unproven. OWNER operations NONE.
