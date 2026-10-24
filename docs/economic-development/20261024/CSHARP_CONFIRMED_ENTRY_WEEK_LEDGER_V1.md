# Confirmed protected entry lower bounds persist across account restarts

Continuation baseline: official `47f8d38040ce69f040855a906c1c16deedd6ef20`, PR171–172. The OWNER's new-chat instruction continues the existing B–E mandate, prioritizing robust after-cost economic advantage and the complete recoverable C# product. This is conversational provenance, not a native GitHub signature or new authority grant. The mandate is still open. Economic configurations rejected in prior studies remain rejected; this change does not reopen or fit any candidate.

## Concrete product behavior

The actual Robot previously protected unresolved entry attempts but had no durable account-wide per-ISO-week record of positively reconciled entries. A new account-scoped journal records position ID, symbol, direction, actual acknowledged units, broker position entry UTC and observation UTC, only after a successful opening result has reconciled with the owned broker book and requested stop. The timestamp of entry determines its ISO year/week, including an acknowledgement observed in the following week. Signals, rejected requests, exits, partial closes, startup-recovered positions and unresolved submissions never increment this counter. It is a conservative LOWER BOUND of confirmed protected entries from this adapter, not an exhaustive broker deal history or a universal definition of execution count.

A journal identity is unique per position. Exact repeated observations are idempotent; contradictory attributes for the same identity halt admission. A persisted digest and strict schema/scope/canonical checks reject corruption and cross-account substitution. The new journal verifies its stored snapshot before entry preparation. After positive reconciliation, it explicitly saves/flushes/reloads the entry BEFORE clearing the existing pre-order pending marker. A persistence fault leaves that marker unresolved and halts entry admission. In-memory state is committed only after exact readback; callback faults poison both barriers. No unknown opening call is replayed, inferred absent or cleared by the ledger.

Cold restart retains all recorded weeks and the original measurement start. Reports include zero-entry weeks, the current partial week, calendar-elapsed status, first-week measurement coverage and the recorded >=21 threshold. `BrokerHistoryCoverageProven=false` and `Hard21Proven=false` remain explicit even if a recorded week reaches21. Calendar elapsed time never certifies broker-history completeness. No order is added or accelerated to reach21. A single serial owning Robot and its existing account scope/storage domain remain required.

Backtests use separate fresh memory and report `simulation=true`; their entries are never represented as real broker executions. Existing net6 SDK packaging, twelve parameters, empty roster and DEMO=false defaults, trading authorization, costs, strategy/sizing/stop/margin policy and all authority/checkpoints remain unchanged. Cloud remains unqualified. The two LocalStorage keys do not constitute a transaction or an inter-instance mutex; ordering is enforced through the pre-existing unresolved checkpoint.

## Validation and reception boundary

The compiled C# fixture independently exercises ISO-year crossings, entry-vs-observation time, zero weeks, partial weeks, exact duplicates after restart, conflicting IDs, scope substitution, malformed/checksum corruption, lost/throwing writes, nonthrowing callback poison and clock regression. Three OS hard kills occur before ledger save, after ledger save before READY, and after READY. Cold processes must respectively observe (blocked,count0), (blocked,count1), and (ready,count1), with no duplicate increment. This is an artificial flushed-file store, not cTrader LocalStorage or a broker.

Python independently recalculates ISO weeks from the original fixture entry timestamps and checks every emitted week, including zero counts and no HARD21 promotion. The existing account-admission CI compiles the actual `.algo`, invokes the pinned vendor metadata command in the existing isolated no-account/no-network boundary, runs the new fixture, retains its original proof, and runs existing regressions. Adapter wiring checks ensure positive reconciliation -> durable ledger -> READY, and journal verification before any opening call.

Native CI results and final integration provenance are recorded in the PR after execution. Neither compilation, SDK metadata recognition, these process tests nor counters close native callback ordering/durability, full broker-history coverage, ambiguous-order resolution or operational acceptance.

## Economic decision and remaining work

No new market data, economic outcome, parameter variant or rejected-strategy rescue is justified by this engineering change. The prior compression gross rejection and UTC-seasonality hypothetical-friction rejection remain binding for those fixed candidates. No robust after-cost edge, independently validated candidate, continuously funded profitable EUR200 path or effective HARD21 has been demonstrated. This change supplies a missing measurement component for the eventual native product; it is not economic performance progress.

No custody key, new provider, broker connection/order, Cloud activation, scientific partition, V2/C033 budget, OWNER1807 or privileged authority is changed. Known limits: absent storage cannot distinguish first installation from complete deletion/rollback without an external anchor; a matching old READY plus rolled-back journal is not externally detectable; a crash after an actual fill before journal save may undercount and remains unresolved through the pending barrier. No automated recovery of that unknown request is claimed. The journal stops rather than pruning or resetting after100000 recorded identities. Full native durability/coverage reception and qualified after-cost research remain necessary in the existing B–E mandate.

## Executed original evidence

PR173 initial code head `ef24beb02446a68bf6eb5be028741f5d6baa1154` passed ALL5 applicable native CI checks. Account gate [40125946805/job120967247199](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/40125946805/job/120967247199) compiled the actual `.algo`, read its original package through pinned vendor CLI (metadata return0; malformed return1), and executed80 artificial ledger assertions,3hard kills and6new processes. Python independently reconciled22 artificial entries/four ISO weeks. Local inspection of the ORIGINAL downloaded proof additionally rejected five false-promotion/week/count/digest/barrier tamper cases. Other successful checks:40125946766,40125946767,40125946811,40125946816. Source tested was the GitHub PR merge `f677c9aa75b59c3e4cd3ae5938f0643fc31e5af6`, not a native cTrader broker run.

Exact original artifacts are durably preserved under `confirmed-entry-ledger-40125946805/`: ledger ZIP12573621254 (1004bytes, SHA256 `3fd39e8e5c1ba263b8de19b67c67169b25788dcf19137bf601825e4fd750d560`) and original compiled product/vendor CLI ZIP12573536406 (77292bytes, SHA256 `cad33135ae4dbb474337ef74fef2cad6d0a30cfccf33c8bcd2c3e9de70044a24`). The original proof and CLI receipt are also copied byte-for-byte; archives are never reconstructed from logs or reruns. Manifest commits every member/part and the exact tested implementation bytes. Subsequent documentary preservation changes do not modify those implementation bytes; later builds may embed a different source commit and are not relabeled as these original binaries.

Offline verification, no keys, market access or CLI execution:

```sh
python3 -m research_core_v4.laboratory.verify_confirmed_entry_ledger_result
```

Native LocalStorage durability, broker callbacks/history and unknown-order reconciliation remain unaccepted; neither this original compiled package nor the80artificial assertions establish economic edge or HARD21.
