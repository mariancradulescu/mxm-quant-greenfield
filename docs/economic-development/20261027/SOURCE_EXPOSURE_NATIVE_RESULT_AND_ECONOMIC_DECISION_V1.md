# Independent reception of the exact W35–W37 observation capacity census — 27 October 2026

**Native evidence:** [GitHub Actions run #40415845622](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/40415845622), job 121897842586, SUCCESS, attempt one, at official protected source commit `49958f462b5b57bdd7d7ad74a4a2b1facab2e8ae`. This run was triggered once by PR #205's source-only workflow; pre-key admission passed and then exact previously encrypted W35/W36/W37 originals were reauthenticated with the existing custody source/decoder, NOT recollected from the provider. No economic model, new market data request or broker action took place.

The full **public aggregated** output emitted by the successful job was saved in `source-exposure-40415845622/receipt.json` (reformatted from the exact native logged JSON, not represented as an original Actions ZIP). The original Git content blob SHA1 is `30397fecc50877f804c31fbed264937a7ca6369c`. The independent offline `verify_source_exposure_result.py` checks Git object hashing, source/run identity, all original public counts, threshold identity, non-promotion, no modeling/market effects and corruption tests without decrypting or running history. All original source private timestamps/prices and custody keys remain private; no new binary artifacts are disclosed.

## Authenticated source observation findings

| Week | Source events | Timestamp groups | Consumer-valid groups | Unavailable groups | Healthy observation stretches | Stretches with observed valid span at least 5 min |
|---|---:|---:|---:|---:|---:|---:|
| W35 | 683,022 | 379,584 | 69,609 | 309,975 | 45,802 | **0** |
| W36 | 761,196 | 421,150 | 72,952 | 348,198 | 50,135 | **0** |
| W37 | 685,474 | 408,017 | 126,734 | 281,283 | 74,446 | **0** |
| **Total** | **2,129,692** | **1,208,751** | **269,295** | **939,456** | **170,383** | **0** |

The **declared pre-evaluation contract** uses at most 5,000 ms side observation age, positive spread, no missing/conflicting/crossed book, inter-healthy-observation gaps at most 5,000 ms, and a fixed five-minute observed span. A healthy observational stretch is NOT a proof that a firm/executable quote existed continuously BETWEEN ticks, or that the broker would execute any order at those prices. An unhealthy group is never deleted, filled or promoted by a later valid group. No source's longest observed qualified stretch reaches five minutes under this strict contract.

**Material research decision:** These particular authentic weeks do not support claiming continuous priceability for an arbitrarily funded five-minute-plus position path under the current consumer guard. Running another fixed long-exposure directional model on these SAME source contracts risks repeating DATA_LIMITED, wasting the economic model/attempt without adding execution evidence. This is NOT a null result about historical liquidity or profitability, nor proof no other instrument / strategy / shorter holding horizon can work. The observation cadence and *chosen consumer contract* are distinct from true broker price continuity.

## Next genuine economic work

Prioritize obtaining a **distinct, preregistered authentic two-sided source with an exposure-path contract** rather than retrospectively dropping unpriceable source events. Prefer independently timestamped fresh/synchronous current BID/ASK observations for future research, with actual historical transaction/fee/FX/swap/volume/margin applicability admitted separately; the October 3 symbol snapshot and hypothetical fees are not enough. Keep broad Pepperstone source/instrument possibilities open, but select neither candidate, holding horizon nor instrument ex post from prior losses/returns. Any new directional hypothesis requires frozen prospective policy, strict single continuous EUR200 accounting, original source authenticity, separated DEVELOPMENT and independent CONFIRMATION, and real cTrader native acceptance before claiming edge/HARD21.

The old intrinsic policy remains DATA_LIMITED and frozen, the earlier cost-floor screen remains only a necessary fee hurdle, and these 3 weeks remain valid SOURCE EVIDENCE. No strategy retune, V2/C033 allocation edit, authority change, funding reset, broker new request, LIVE/DEMO order or Cloud. Mandate B–E OPEN; owner operations NONE.
