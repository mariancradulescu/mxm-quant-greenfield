# Original source causes received in C# and Python — 27 October 2026

**Actual native operation:** [run40463984769](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/40463984769), job122054897374, one attempt, SUCCESS, source `9b268d814eb21e446f8447b388326cbbaff52ec0` (PR #213). It restored the original encrypted source40455704891 from Git and decoded all1,140saved native spot messages only in the existing custody environment. No new broker request/connection, source collection, strategy/account/response test or price decryption in Work occurred.

The actual C# profiler independently matched Python for every event disposition, all cause counts and the entire original source profile. Derived input SHA256 `839fa07c0e8fe15011d76d7151b9db61224d76f31b48e0e62fa581e01819c6b4`; actual compiled assembly `c0620bcda23f22a954027b63dd7dca0a51cf7a44a1de90e6da686c6e5bbb9041`; ordered disposition digest `2f2a15df450c3cd569caace4d813da6eebb877c5bb0e3d7a50feadcc7ef0de2e`. Source authentication comes from the outer native custody bridge and original crypto/provenance, not a claim that the standalone C# program authenticates market data itself.

## Measured causes, without changing the consumer

| Saved source | Messages | Positive book geometry | Locked BID=ASK | Crossed BID>ASK | Locked message containing both fields | Locked after partial update | All inter-message gaps >5s | Healthy-to-healthy gap breaks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| EURUSD | 336 | 183 | 153 | **0** | 115 | 38 | 10 | 5 |
| GBPUSD | 482 | 445 | 37 | **0** | 10 | 27 | 7 | 3 |
| SpotCrude | 322 | 322 | 0 | **0** | 0 | 0 | 7 | 7 |
| Total | **1,140** | **950** | **190** | **0** | **125** | **65** | **24** | **15** |

All190observations in the old combined locked/crossed category were locked at the saved API representation; none were crossed. In125cases both price fields were explicitly in that same native message, so the entire phenomenon cannot be attributed to carrying an older opposite side through a partial update. Those counts include initial snapshots where applicable; they do not prove fresh firm two-sided quotes or zero executable trading cost. Equality is evaluated on exact original raw-price integers through decimal representation, before price rounding, not introduced by floating-point conversion.

There were840two-field messages,150bid-only and150ask-only. After initialization, **zero explicit equal-to-previous side-field observations** were found, on either side of any instrument. This sample is compatible with a change-driven quote stream; it is an inference about these saved records, not a universal vendor guarantee that every absent field remains executable indefinitely. A last-change/last-field clock must not be silently called the expiry time of the maintained broker quote.

All received events passed the declared server-versus-receipt clock check; server-clock-failure counts were zero. This says nothing about server/host clock synchronization, upstream events never received, or firm price validity during silence. SpotCrude's321valid received events and eight stretches are accounted for by seven healthy-to-healthy gaps >5seconds. Those gaps measure an absence of saved price updates, not an observed absence of market liquidity. Other source invalidities/categories can overlap; do not sum reason counters as disjoint trades.

**The original strict profile is byte/provenance-bound and exactly unchanged:** EURUSD179healthy/157unavailable, GBPUSD440/42, SpotCrude321/1, zero observed >=5minute stretches under the frozen positive-spread/five-second/initial-snapshot rule. Positive geometry950 is not the940consumer-valid observations. Neither count is an executable trade, native cTrader callback proof, whole-week frequency, HARD21 or net edge. The historical GBPUSD W37 six-stretch result remains a separate unmodified source/window/clock result.

## Functional integration and validation

The actual C# product now uses the shared descriptive `MxmBookShape`, also used by the independent C# source profiler. Its native geometry predicate is preserved exactly: finite positive BID/ASK with ASK>=BID, including locked books. It already used this predicate before PR #213. The source-quality caller explicitly still requires a positive spread; no old or new order is admitted by this descriptive helper alone. Risk, continuous EUR200, commission reserve, durable intent, final expiry, recovery, trading permission and confirmed-entry/HARD21 controls are unchanged.

All five required native CI suites passed on the original PR source, including real product/CLI metadata build and existing cold-process recovery. The new compiled tests check100ordered native boundary/nonfinite pairs against the exact old predicate, descriptive cases and policy separation (106checks), exact span/gap/field/clock cases and deterministic1,000event fuzz. All12new tests executed in CI without skips. The subsequent authentic custody run independently reconciled all1,140real source dispositions; artificial tests are not relabeled native market evidence. This is functional source/input integration, not operational Robot reception or a profitable strategy.

## Exact evidence and retained limits

Original public artifact **12715701511**,1483bytes, SHA256 `98d5d2b44f53b42a2c4be007ee45712a51a3a27672e90eed14d1187d4e42719e`, is preserved byte-for-byte in `spot-source-causes-40463984769/artifact.zip.b64`. Its sole original receipt is3732bytes, SHA256 `fc677ee78cbe6c63fb18766eb57ad07a290dda8db922d96ae558844b3f941a0a`. The direct job output and downloaded original artifact agree. Offline verification binds both originals, the original capture manifest/private commitment, actual source/binary/input/disposition identities, every public cause count and all no-promotion flags. Four preservation tests cover exact originals, ZIP corruption, receipt substitution and symlinks, with no key or source replay.

The original encrypted primary source, strict profile, initial/latest-snapshot limitation, deadline-closed possible trailing frame, original diagnostic interval/exclusion and response-testing prohibition all remain intact. No plaintext source prices, event timestamps, account identity or key is published. Optional BID/ASK fields and the first latest-price snapshot are documented by the vendor, but those protocol facts do not certify execution or perpetual quote validity. Primary references checked27October2026: https://help.ctrader.com/open-api/symbol-data/ and https://help.ctrader.com/open-api/faq/ .

## Director decision from this finding

Do not repeat six-minute captures or old five-minute source censuses just to seek a favourable stretch count, re-subscribe/poll to manufacture fresh field observations, reopen rejected models or relax the recorded criteria retrospectively. This original causal question is answered without any new broker activity.

Before the next economic admission, preregister an appropriate **future** book-state/exposure/response contract: distinguish received-message time, explicit field-observation/value-change time and maintained-book state; distinguish locked from crossed geometry; retain independent data/transport status and unresolved execution/valuation intervals. Unchanged or quiet quotes are neither automatically expired nor automatically firm executable prices. Require dated all-in cost/FX/margin applicability and distinct mechanism/response evidence. Do not transfer current metadata into September terms, score directional responses on this diagnostic capture, select the best past stretches, or turn source counters into trading advantage. The wider authorized universe and alternative exposure mechanisms remain open, with their own prospective evidence requirements.

B–E OPEN. Source-only operation consumed zero new economic trials/outcomes and made zero orders, Cloud, capital reset or authority/custody changes. Native product operating reception, after-cost edge and effective HARD21 remain unqualified. OWNER operations NONE.
