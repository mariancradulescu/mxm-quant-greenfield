# cTrader order outcome and broker stop reconciliation

Baseline: `da47a6e39294b40fc8dc51bcc4926e44811f44df` (PR164). Product repair; zero new scientific trials and no new research outcome reads during implementation. Existing merge-triggered protected DEVELOPMENT replays are technical regressions on already preserved sources, not independent economic observations. The CompressionRelease `GROSS_FAIL` closure remains in force. No failed strategy is promoted or retuned.

## Material defect and behavior

The native Robot previously logged `TradeResult.IsSuccessful` and resumed its normal decision loop without validating the resulting position and attached stop against the broker book. Successful API return alone cannot establish protection.

After each synchronous market order, `MxmOrderProtection` now checks exactly one owned symbol position against the returned identity, requiring that identity to be absent from the complete pre-call book. It validates direction, exact requested normalized volume, finite positive entry/stop/pip/tick geometry, and a stop on the loss side of entry within the requested distance plus one instrument tick for price rounding. The actual position is read from the broker book; the result object's stop is not used as proof. Tighter stops are allowed. This is a protection check, not certification of fees, atomic admission, maximum realized loss, or the post-fill aggregate risk limit.

Clean rejected call with no returned identity and no observed owned symbol position creates no fill. Any other failed or ambiguous reconciliation permanently latches this Robot instance's admission off and clears every queued portfolio intent. Bar and tick decision callbacks cannot reopen admission. A thrown order call also latches admission off without guessing an identity.

Only a returned identity absent from the pre-call book and currently carrying the exact expected owner label and symbol is eligible for defensive closure. The adapter attempts that close immediately and on a five-second timer; each attempt rechecks identity/ownership. Failure can retry that close, never the entry. Reported close success is logged separately from observed book absence. Disappearance suppresses further closes but does not release the admission latch. Null identities, other owners, other symbols and preexisting IDs cannot be seized. Unknown exposure remains explicitly unresolved; broker availability and crash interruption can prevent flattening. No inter-instance mutex or account transaction is claimed.

Cold startup now also validates every recovered owned position's protection against the configured stop-distance bound before subscribing to events. Invalid recovered protection stops startup without opening orders or closing an unattributable position. This conservative check may reject a position manually modified to a wider stop or a profit-side trailing stop. The admission latch is in memory, not a new durable native recovery format: platform restart, external modification and actual broker callback ordering still require native acceptance evidence.

## Verification and limits

`MxmBrokerIntentFenceFixture` runs the actual shared C# guard with artificial books: valid long/short, one-tick rounding, missing/NaN/wrong-side/too-wide stops, zero entry, wrong/nonfinite volume, wrong direction/identity/label/symbol, missing result identity/book, failed call carrying a position, preexisting ID, duplicate positions, clean rejection, thrown-call halt, repeated failed close, ownership change, disappearance and irreversible admission latch. It reproduces the old successful-call/no-stop counterexample. The existing no-secret CI compiles the actual `.algo` with this guard and runs this fixture plus account/recovery regressions.

These are artificial contract checks and compilation, **not native cTrader execution, broker fills, or crash/callback reception**. The native defaults remain DEMO disabled, empty roster and LIVE prohibited. No Cloud activation, broker order, new data capture, protected outcome access or scientific budget charge is introduced.

Economic edge after costs, HARD21 and final product acceptance remain open. This repair prevents unverified order outcomes from silently returning to normal trading; it does not make any rejected research strategy competitive. Existing DEVELOPMENT / CONFIRMATION / PROTECTED boundaries and all authority checkpoints remain unchanged.

Technical API reference: [official Robot.ExecuteMarketOrder](https://help.ctrader.com/ctrader-algo/references/General/Robot/ExecuteMarketOrder/) (consulted 2026-10-23). The six-argument overload requests stop distance in pips and returns a `TradeResult`; the source remains compiled against the existing pinned cTrader.Automate 1.0.21 package.

## Integrated verification receipt

Product PR165 merged as `1f9e5abcaa7c38f8b5176271f449a9c5b57af74b`, from final source head `50bb28e2595993df09758a4f780500cb9adea598`. All five required checks passed. Account gate run [39999349839](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/39999349839/job/120571090756) compiled the actual `.algo` and emitted `MXM_POSTFILL_PROTECTION_IDENTITY_STOP_LATCH_RETRY_PASS_NOT_NATIVE_PROOF` from the actual C# fixture. The first CI attempt exposed an obsolete textual assertion requiring the former rejection-log branch; CI was updated to require the new reconciliation path and latch wiring. No failed check was waived.

The merge automatically invoked the unchanged protected chronology and lifecycle workflows because their existing path filters include this adaptor. Those workflows decrypt the already preserved DEVELOPMENT sources inside custody and rerun the same registered programs; they make no new broker requests and are not new independent trials. Their outcome status is recorded in `CTRADER_POSTFILL_VERIFICATION_V1.json`. Duplicate economic ciphertext is not repackaged as new economic evidence. This technical receipt preserves provenance pointers and artificial-contract status only; it does not reinterpret earlier negative economic results or certify native execution.
