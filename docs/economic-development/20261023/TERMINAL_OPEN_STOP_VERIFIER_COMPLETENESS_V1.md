# Independent stop verification: omitted terminal exit counterexample

Continue from PR #154, official source `b3dabbf3b1e4bbf001be46581b3ad24edf605c0a`. Existing negative Adaptive/Breakout dispositions and preserved records remain unchanged.

## Reproduced material defect

The independent Decimal checker scanned first eligible observed BID/ASK stop touches when checking an EXIT ledger row. It did not scan an open position's remaining quote path before calculating terminal mark. A ledger could omit the required stop exit and retain the position through price recovery; all monetary equations then reconciled, and the verifier accepted that artificial ledger. No claim is made that this happened in an authentic C# run.

Before the change, full-verifier negative tests reproduced four erroneous acceptances: long and short stop-touch-then-recovery, and long and short exact terminal-quote touches. The tests mock only the independently tested source parser with a miniature synthetic atomic book to isolate ledger verification; they are not native data, custody evidence, new economic trials or broker fills. Untouched-terminal controls passed.

## Remediation and scope

For each terminal open position in fixed-stop modes, independently scan all usable atomic snapshots strictly after its entry through the terminal quote, inclusive. Require long BID > stop and short ASK < stop throughout that suffix; equality is a touch. Recovery cannot erase an earlier touch. Existing first-touch exit checks, quote-side accounting, source binding and legacy no-stop behavior remain unchanged. Receipt now counts independently checked terminal-open stop paths; no claim of full native broker stop fidelity.

No signal, entry, exit, stop distance, cost, sizing, capital, model budget or C# product parameter changed. This closes an acceptance loophole that could overstate future modeled profitability. Required no-key CI executes the counterexamples and controls, old source/provenance/account tests and actual .algo build. The existing protected C# workflow is triggered by this verifier path to check authentic original/W37 records under the stronger check. This is technical regression/reception of the same fixed models, not a new research identity or independent market evidence. Prior W35 Breakout result is retained as negative; this patch alone does not claim a new protected verification of its archived private ledger.

All authorities, checkpoint/OWNER1807, V2/C033 and DEVELOPMENT/CONFIRMATION/PROTECTED stay unchanged. Zero broker collection/orders or Cloud. Native cTrader callback/crash recovery, historical costs/liquidity and competitive edge/HARD21 remain open. This concrete material verification defect is addressed once; it does not justify reopening completed audits or retuning rejected configurations.
