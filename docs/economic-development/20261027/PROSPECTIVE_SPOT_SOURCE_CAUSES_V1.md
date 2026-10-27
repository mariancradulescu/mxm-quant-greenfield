# Original spot source cause analysis and C# input integration — 27 October 2026

Continuation from official `4e2fec1e7ab2c03931a89f1769902a5adb505ba7`, PRs #210–212, with no later product change found live. OWNER confirmed independent reception and continued the same B–E delegation; this is conversational provenance, not a forged native review or authority change. Original VIEW source run40455704891 remains closed and must not be collected again for this task.

## Fixed question before this analysis

The saved public source receipt collapses locked and crossed books into one category and does not explain whether an invalid book came from a two-sided message or a partial update. It also distinguishes valid received events from observation stretches: SpotCrude had321/322valid events and eight stretches. This operation classifies **all1,140original events on all three fixed instruments**, in original receipt order, without new data, responses, models, trade decisions, filtered periods or selected winners.

Measure descriptive book geometry (missing/invalid/crossed/locked/positive), field presence (both/bid-only/ask-only/neither), explicit same-price side observations, server-clock failures, inter-receipt gaps and healthy-to-healthy gap breaks. Separate locked/crossed books directly containing both fields from a carried book after a partial update. A partial update can explain the observed representation; it cannot prove what a broker would execute. Explicit same-price fields measure observation, not price movement or guaranteed freshness. Missing updates do not prove missing liquidity.

**Keep the entire original source consumer policy unchanged:** initial snapshot excluded from freshness, later side observations, positive spread, 5-second side age and healthy gap, 300-second observed span. Reconstruct the complete original public profile exactly and require equality to the immutable native receipt before interpreting any new cause count. Do not reclassify the old zero five-minute result as positive, relax the source contract, merge disjoint stretches or infer fill quality/profitability. The original diagnostic window remains excluded from confirmation and directional response testing remains forbidden.

## Functional C# integration

Add descriptive `MxmBookShape` to the actual product and source readback. The native Tick adapter explicitly retains its existing predicate: finite positive BID/ASK and ASK>=BID, which includes a locked book. It used this rule before this change. The source-quality consumer explicitly continues requiring a positive spread. Classification and caller policy are separate; neither predicate alone is order admission. No risk/capital/fee/intent/recovery limit or native execution permission changes. A compiled test compares the shared native method to the exact old predicate on100ordered boundary/nonfinite pairs, plus descriptive cases and caller-policy separation (106checks).

Implement the receipt-clock source profiler in C# using that shared geometry. A separate Python reference and the frozen original source profiler reconcile every event's disposition digest, shape/cause counts and complete original profile. Source-program input is seven explicit fields only; no strategy/account/cost engine is linked. Native BID/ASK doubles and source raw-price decimals keep their own representation; this does not prove event-clock or callback equivalence between Open API and Robot.

## One finite native operation

New `mxm-spot-source-cause-reception.yml` runs once when installed, no dispatch/schedule/retry, with GitHub contents/actions READ and the existing custody environment only. Admission precedes key access and binds official source/workflow/authority/history plus the original native run success. Restore exact original cipher/public receipts from committed ZIPs, not from broker or Actions retention.

Inside the existing immutable decoder checkout `d2fae5641b759b1c8c24161d83d62d39e104eafd`, verify exact extension/main bytes, original manifest/cipher/private/source hashes, existing custody fingerprint and complete original native source. Decode/export all receipt events only into private runner storage. The key is available only to that export step. A later keyless step executes the real compiled C# classifier, independently checks every disposition/counter against Python and requires exact equality to the original published source profile. It binds input hash, actual assembly hash, analysis head, source identities and unchanged-policy facts. Only aggregate source facts, digests and no-promotion flags are uploaded. No source price/event timestamp/account identifier is published or decrypted in Work.

Existing public encrypted source and original scientific partition remain unchanged. Zero new broker requests/connections, model trials, market economic outcomes, direction/return tests, orders, Cloud or capital resets. Current broker terms do not become historical cost or executable FX proof. A source-cause finding may guide a separately preregistered future source/mechanism design; it does not admit any old or new trading hypothesis.

## Validation

Local pure Python scope/cause tests passed. C# compiled boundary/predicate, exact-span/gap, field/clock and deterministic1,000event fuzz parity tests are required in CI and may not skip there; the real product package also builds in its existing CI. Native authentic source parity is a separate post-merge step, not inferred from those artificial tests. The analysis remains unexecuted until its new one-shot workflow is installed after required CI. Subsequent preservation must keep the exact original aggregate artifact and native run/job/head identities, without rerunning this readback.
