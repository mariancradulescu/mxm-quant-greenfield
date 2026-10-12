# MXM — signed executed-flow qualification, 2026-10-12

Role: EXECUTOR_DIRECTOR_MXM_QUANT_GREENFIELD. This is an executed source-schema qualification and a narrow synthetic observation-map proof, NOT an economic market pilot or independent audit acceptance.

## Result

One candidate assessed: SIGNED_EXECUTED_FLOW_PERSISTENCE_DURING_PRICE_STALL_V1.
Decision: NOT_QUALIFIED_INPUT_NOT_IDENTIFIABLE_FROM_REVIEWED_HISTORY.
Nine checks passed locally. Six source files were downloaded at immutable HEAD 2b5a51096dbcde47f3f42464c167cb4b5a3528d5; their local Git blob hashes equal the repository tree hashes. RESULT_V1.json records SHA256 of their exact bytes.

No empirical economic progress was demonstrated: market rows read 0, market pilots 0, broker requests 0, orders 0. NET is UNKNOWN/not measured, not zero or negative. HARD21 remains undemonstrated. The proof does not qualify a complete strategy or exhaust the broker universe.

## Single hypothesis and distinctness

Proposed economic mechanism: persistent one-sided executed demand, temporarily absorbed by passive liquidity without observable midpoint displacement, may precede directional repricing when replenishment fails. Inventory management can instead cause reversal; this is a falsifiable hypothesis, not an established causal effect.

Required pre-entry primitive: market-wide transaction execution times, executed quantities, aggressor-side observations or independently validated side labels, and contemporaneous receipt-ordered BID/ASK. The signed pressure must be observed before entry, not assigned using future price movement.

Relevant existing comparators/closures were read, not rerun:
- native_update_asymmetry_v1: trailing BID-versus-ASK UPDATE COUNTS, not traded buyer/seller quantities.
- integrated_alpha_campaign_v1 MATCHED_ACTIVITY_LOW_IMPACT: tick count relative to price impact, not signed executed demand.
- quote catch-up/FX lead-lag and spread forecasting remain closed in their exact scopes.
- Existing depth-size requirement is not a new discovery; displayed depth is not executed flow, and no depth acquisition was attempted.

The hypothetical falsification would compare signed-flow conditioning with identical-entry prior midpoint direction, quote-update asymmetry, unsigned activity/impact and cash. Entry/exit, matured training, complete ISO UTC weeks, side-aware spread, both commissions, EUR conversion, funding and slippage scenarios must be frozen before any market outcome. A source-distinct hypothesis is insufficient: this one fails the input gate, so no strategy freeze or pilot is asserted.

## Evidence and precise limitation

Pinned ProtoOATickData has exactly timestamp and tick. Historical ProtoOAGetTickDataReq.type selects BID/ASK. ProtoOATrendbar.volume is documented in the pinned schema as bar volume in ticks. The reviewed collectors retain price/time quote events and OHLC/tick_volume. ProtoOADeal has filledVolume and tradeSide, but those fields are not in historical quote responses: account deals are not a market-wide aggressor tape. ProtoOADepthQuote exposes displayed size, not filled volume or aggressor side.

The executable proof constructs 16 synthetic quote traces, each paired with two opposite unobserved executed-flow states: 32 synthetic worlds, 16 identical-observation collisions. Therefore this observation map is non-injective for signed executed flow. It does NOT establish either latent world as actual broker history, deny statistical inference under additional assumptions, or show that all price-based predictors are useless. Nine passing schema/logical checks are NOT nine profitable trials.

Missing information for this exact hypothesis is transaction-level signed executed volume available before entry. Merely requesting more of the same historical quote or bar endpoint cannot add fields absent from the verified schema. No claim is made about all private artifacts: they were not opened in this execution. No external supplier or data partition change is requested.

## Preservation of earlier encrypted results

Verified live: run 38244279805 completed SUCCESS at source HEAD a1458f1e3429cf2f8544401c7306f10efbf77427; job 114794180558 SUCCESS.
Release 410542358 remains present:
- asset 633625809, nativedecision-private-result.mxmenc, 13689 bytes; GitHub-reported digest sha256:16a35cf80ca831a56cf532412027d0b905e7d2e5bdc46f158379a3fa6758a920
- asset 633625947, nativedecision-private-delivery.mxmenc, 9406 bytes; digest sha256:837ed9cf89eac26acfddd8fb1a595d3e012933d51b423bbd6f8ff01e7e62b83b
- asset 633626013, nativedecision-attestation.mxmenc, 9774 bytes; digest sha256:245a10807f8c18c1b9fa83b6c0816ddc08dab4dcd63585d59dddcf3ac8d13f08

These are metadata/digest observations, not local binary downloads or fresh numeric readback. Detailed numeric delivery remains incomplete. No ciphertext was overwritten, decrypted, rewrapped or declared negative.

## Execution scope

Local command actually executed: python flow_identifiability/proof_v1.py --source-root evidence_inputs; exit code 0. Canonical reproduction after publication: run the same proof from its repository path with --source-root . in a checkout.

No new Actions run or job is claimed. Current callable GitHub tools expose GET, file/Git writes and reruns, but no new workflow_dispatch operation; no local CTRADER or GitHub token variable was found by variable-name-only check. No configured secret value was extracted. This is a limitation of direct empirical execution here, not a security denial of all research. Rerunning unrelated successful jobs or using a write as a covert dispatch was not attempted.

Capital policy retained: EUR200, aggregate planned risk <=EUR2, aggregate margin <=EUR80, reserve >=EUR120. No sizing, modeled holdings, orders, Cloud deployment, protected-forward opening, security changes, retuning or negative-exact replay.

This closes only the qualification attempt for the explicit observed-flow hypothesis under the reviewed input schema. Untested mechanisms, instruments, scales and broader Pepperstone research remain open. The result is a narrow documented input limit, not an economic null and not a claim that the project has become profitable.
