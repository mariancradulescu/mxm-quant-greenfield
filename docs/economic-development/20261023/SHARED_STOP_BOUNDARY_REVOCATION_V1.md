# Shared stop-boundary revocation in product and account replay

Continuation from official PR #149, source `49d589097db0b2c7ee1afb74b1dbf003773f0532`.

## Concrete defect and change

The product broker fence already rejects a BarClosed publication for a UTC bucket in which a broker stop revoked the decision. The shared portfolio account replay only cleared its pending intent on an observed stop. If a stop quote precedes a BarClose event in the same bucket, the later bar republishes a direction and the following quote can reopen. The previous synthetic fixture covered bar-before-stop ordering only. This is a product/evaluator lifecycle mismatch, not evidence of an economic edge.

Move the existing monotone bucket revocation rule into `MxmCausalIntent`, used by both paths. The broker fence delegates revocation and publication checks to that queue; the replay revokes through the stop quote's bucket. Clearing pending state cannot erase the barrier. A subsequent genuinely new boundary remains eligible. No strategy thresholds, stop distance, cost parameters, capital, authority, source corpus or partition changes.

## Validation scope

Required PR CI must compile the actual cTrader `.algo`, run the broker fence interleavings and the C# account fixtures, including stop-before-bar on long and short instruments, no same-bucket reopening and next-bucket resumption. Direct queue fixtures cover publication after revocation, Clear preserving the barrier, delayed notification monotonicity and single consumption. CI also retains bar-before-stop and stale-intent tests. Synthetic event permutations do not prove native callback ordering or broker fills.

After normal required CI and merge, the existing protected custody workflow is triggered by these C# paths and independently reconciles the unchanged authentic DEVELOPMENT streams. This is a regression check of implementation consistency, not a new strategy trial, parameter search or W37 optimization. Any resulting ledger supersedes the old implementation's affected counterfactual only; the previously negative Adaptive verdict remains nonpromotable. No LIVE/DEMO orders, Cloud activation, broker collection, new feed, TrialBook mutation, EUR200 reset or checkpoint/OWNER1807 change.

## Scientific disposition

This repair provides no competitive candidate. W37 remains exposed DEVELOPMENT and cannot serve as fresh confirmation. Economic qualification, multi-week and multi-instrument robustness, executable HARD21 and native cTrader recovery acceptance remain open. The next economic program must be prospectively specified against eligible authorized data with finite identity budget; no winner is selected from this repair.
