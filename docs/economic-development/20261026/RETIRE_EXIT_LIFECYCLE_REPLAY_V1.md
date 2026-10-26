# Retire second automatic historic economic replay — exit lifecycle (2026-10-26)

## Confirmed second trigger after PR196

Official PR196 merged at `f36131aef32ae5021be98d9bf265f29819333185`, following five required successful no-secret C# CI runs. It changed the **native Robot risk-entry envelope only**. The inherited `.github/workflows/mxm-csharp-exit-lifecycle-cold.yml` nonetheless had a push trigger covering `MxmReferenceProductBot.cs`, and automatically launched [40385729713](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/40385729713) / job `121793357590` on that merge.

The original job completed **SUCCESS**, and its steps include decrypting the SAME original short Pepperstone source and recomputing an already registered **216-leaf** exposure/exit policy sensitivity (28,212 side events; only exposed DEVELOPMENT, no full ISO week and no independent confirmation). It is therefore an actual redundant computation, not simply a no-op source reception, not a new scientific admission, and not evidence that PR196 generated better economics. The generated receipt, if any, must retain its historical development-only label; no second outcome/confirmation, strategy retune, budget refund, new market source or HARD21 claim follows. No broker orders or cTrader Cloud activation were requested by this code change.

This is a **distinct** legacy workflow from the two jobs already retired in PR195. An earlier claim that all redundant economic triggers had been eliminated was too broad.

## Deterministic retirement

This PR removes `workflow_dispatch` and **every C#/strategy/archive push trigger** from the historical scorer. Its sole permitted push path is the workflow file itself; both branch and job limits remain official, and its one job has literal `${{ false }}` before runner, environment, secrets or economic steps.

Every original job step, command, recipient, permission and guarded environment is retained for audit. Exact original raw step-tail SHA256 `51499c4e9db536969cf8b63c17e61985e75de46ae18ccba71371a0f11d90898d`. The original full workflow remains at the official `f36131aef32ae5021be98d9bf265f29819333185`. A structural no-secret regression rejects changed step bytes, resurrected job, widened triggers, manual dispatch, permission drift and new jobs. The existing PR195 retirement tests stay intact.

All other required regression tests and separately prospectively admitted scientific workflows stay active; **do not** rerun the completed fixed scorer merely to verify its retirement. Postmerge verification must observe any historical workflow as `SKIPPED` with zero steps and no assigned runner. No weakening of custody, branch protection, AUTHORITIES, OWNER1807 or broker-order prohibition. B–E, economic edge, HARD21 and native cTrader operational reception remain OPEN.

## Next scientific work

Choose a DISTINCT prospective hypothesis only after passing an explicit supported source/fee/FX/volume/margin/funded exposure admission, consistent with already rejected/censored policies and budget. Fresh arbitrary C# refactoring must not trigger any historical expensive economic models.
