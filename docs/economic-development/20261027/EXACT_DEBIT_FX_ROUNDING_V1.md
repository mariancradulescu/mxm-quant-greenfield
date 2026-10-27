# Exact upward debit FX arithmetic in the existing native product

Reconciled official HEAD30aef42f92d750673adbc51d1af65ff118fcbd96 and PR223; no later PR or queued/in-progress run found at recovery. Old open PR1/8/104 are not continuation queues. Active authority07d1ddbe0b83753bbf189770af1911623fef8d6f, OWNER1807a830c132521bd4348454653f713e04f6107484fe and evidence heade49f08f360267d6fc4d128826590eb6bce051a58 remain unchanged.

## Defect and implementation

The observed cost-FX component advertises upward rounding to18decimals, but decimal division/multiplication can already round away a positive remainder before that ceiling. Artificial witness: inverse of999999999999999999 is strictly above1e-18; the earlier decimal calculation rounds it to1e-18, while the promised upward18-place result is2e-18. Likewise1e-18 times1.000000000000000001 has a positive remainder lost by ordinary decimal multiplication. These are numerical domain counterexamples, not evidence of an actual broker undercharge or a material error in a preserved market result.

The SAME production component now extracts the exact decimal integer coefficient/scale and uses bounded BigInteger rational division with ceiling only at the final decimal grid, per leg and per composition. Large results coarsen upward only as required by the96-bit decimal representation. Positive values never underflow to zero; unrepresentable products fail closed. No new conversion route, midpoint/credit substitution, quote-age change, fee assumption or stale fallback is introduced. The actual net6cTrader project already compiles this component; no new runtime dependency, parser, socket, Robot parameter or account format is added.

A suspected route-cache alias was checked and ruled out: the original Route implementation already returns a defensive copy. It is unchanged. The final MarkSubmitted operation is memory-only; durable preparation precedes the existing final revalidation, so no extra persistence operation is introduced there.

Independent Python uses exact Fraction arithmetic and a separate representability search. Required existing gateway CI tests both counterexamples, full decimal range, overflow and160randomly oriented two-leg paths, in addition to prior temporal/metadata/source guards and full native package compilation. Local .NET is absent; locally passed Python guards do not substitute for required compiled CI. CI status at installation is pending.

## Economic/source decision

The13October original DOM capture is explicitly TECHNICAL_CAPABILITY_ONLY. Its frozen PROSPECTIVE_PARTITION_V1.json forbids using diagnostic bytes for discovery or protected validation. Its OpenAPI depth events carry local arrival order, not a server session sequence or an initial-snapshot-complete flag. Therefore it is not valid to relabel them as authenticated FIX snapshots or feed invented server sequences into PR223. It may support a separate technical decoder reception if justified, but it cannot supply the next economic outcome. No new contact is justified simply to reproduce the same missing field.

The closed GBPUSD spread identity and original outputs stay unchanged. A distinct depth mechanism would require a separate legitimate development partition, actual source semantics and prospective rule/cost/censoring gates. A slower completed-bar mechanism remains a different route, with genuine quote-side endpoints, explicit unresolved intraperiod exposure and dated costs; bars do not manufacture firm fills or stops. The entire authorised universe remains open. No new economic hypothesis/outcome is claimed in this numerical correction, and no protected data is opened.

Zero broker requests, LIVE/DEMO orders, Cloud activation, model trials, economic reruns, authority/custody changes or capital reset. Original market evidence is neither decrypted nor recomputed. Robust net edge, broker-executed HARD21 and native operational cTrader reception remain unproven. OWNER operations NONE.
