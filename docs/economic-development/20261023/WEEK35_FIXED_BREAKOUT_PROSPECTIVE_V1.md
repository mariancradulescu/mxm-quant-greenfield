# Fixed non-Adaptive Breakout W35 dependent DEVELOPMENT study

Continue from PR #152 source `ac5f2760685517e6fcee3d072f59c8bc7ae611c1`. No new collection. Reuse exact durable authenticated W35 run `39946364621` (683,022 BID/ASK events) in existing protected custody. This interval has exposed M5 results and is not independent confirmation.

## Decision frozen before W35 strategy outcomes

Evaluate the already implemented **Breakout** alternative in the unchanged shared product kernel. It uses six completed closes, a prior five-close channel and fixed 0.00005 relative buffer; the existing volatility shock hold applies. It does not route through Adaptive. Its earlier short-window developmental exploration is preserved; it is not presented as a newly invented or independent strategy identity.

Single continuous initial EUR200 account per alternative execution scenario; fixed 1000 units, one position, M5, product-default 12-pip stop, reversal-only discretionary exit, first observed quote-side stop and same-boundary revocation, current-equity risk fraction 2%, friction reserve EUR0.2, modeled margin EUR50 and 40% margin fraction. Base slippage .00002 quote units per side; stress .00004. Both scenarios must run and be reported, with no winner/parameter selection. Captured W35 commission/volume components and signed quote-side FX are independently checked; historical fees, financing, executable liquidity/margin, latency, broker callbacks and future closing costs of a terminal open position remain unproven.

Manifest `WEEK35_BREAKOUT_DEVELOPMENT_V1.json`, SHA256 **b42db94d1fdbe5d664f9d5bc6d51ffae8521b6e31a2b59620a6d135496950f36**, pins unchanged kernel bytes and every model assumption. Budget: one existing mechanism, two dependent scenario outcomes, zero unregistered followups/independent confirmation. This is a finite B–E dependent DEVELOPMENT extension, not canonical V2 outcome admission or a reserved C033 spend. The manifest and retained result record the exposures; formal ledger, all previous attempts, budget/reservation, checkpoint and OWNER1807 remain unchanged. Technical reproduction retains this exact identity and cannot be counted as new independent evidence.

Cash benchmark is EUR200. If both terminal quoted equities are <=200, reject this fixed development configuration. Otherwise classify INCONCLUSIVE_REQUIRES_INDEPENDENT_AFTER_COST_VALIDATION. Positive modeled equity never qualifies a candidate here. Stop at this finite result; no automated tuning or additional hypotheses.

## Execution and evidence

Normal required PR CI precedes protected merge. Existing original decoder checkout is SHA-pinned; W35 ciphertext/private/producer identities, captured terms, interval, counts and derived stream hash are checked independently. No broker credentials, App/writer, orders or Cloud in this workflow. Independent Decimal verifier checks each cash event, fee, quote-side fill, first eligible observed stop, terminal mark and shared margin for both scenarios. This is independent arithmetic of the same C# ledger, not an independent strategy-decision implementation or native cTrader execution.

Full economic numbers and exact original C# report bytes are encrypted to the existing recipient. Public receipt includes only source/spec/result commitments, exposure budget, disposition and explicit nonqualification. Durably preserve the small encrypted result after native success. No raw quote or account plaintext in Git/logs. Required CI retains all original W37 and product admission regressions and compiles the actual cTrader .algo, whose signal kernel is unchanged.
