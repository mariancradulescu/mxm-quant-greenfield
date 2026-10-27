# Final existing-position stop-risk estimate — 27 October 2026

Continuation from official `656290a651eb82f703b09ecb42b96778d99d3199`, PRs #205–206. Live branch and latest PRs were reconciled before writes; no later official change was found. Scheduled recovery runs 40429552415 and 40436786452 completed successfully on their own pinned source; they are not later official product commits. Historical open PRs #8 and #104 retain their separate remediation context and are not merged here.

## Functional change

After durable intent preparation the native product already checks existing position identity, stop, units and quote marks, plus initial aggregate stop exposure. Its final account gate previously resampled only the proposed ticket risk. It now calls the existing complete-book estimator again, rejects missing/changed exposure or changed position count/book, and passes both old and new existing-risk estimates into the shared final account gate. Any increase is a hold even if equity increased. Unchanged or reduced estimated risk can proceed through the remaining original gates. A required fifth snapshot constructor argument prevents silently omitting existing risk in future callers. Unknown requests still retain their pending marker; pre-submission holds use the existing not-submitted cleanup.

Validation uses the existing artificial C# portfolio fixture and full cTrader compilation in the existing no-secret admission CI. New cases cover stable/reduced/increased exposure, increased equity hiding increased existing risk, negative initial/final risk and unexpected exposure from a flat account. This is synthetic gate validation, not native broker callback reception or economic evidence. Native CI run/commit identities are recorded by the PR checks after publication.

## Remaining valuation boundary

This change compares **API estimates**, not independently timestamped executable EUR loss-side conversions. Spotware documents AmountRisked as imprecise and PipValue as fixed at initialization, not updated in real time. Repeating AmountRisked must not be represented as proving fresh FX. A separate native valuation proof remains necessary before operational acceptance. No claim is made about AmountRisked internal implementation beyond its documented contract.

Official references checked on 2026-10-27:
- https://help.ctrader.com/ctrader-algo/references/MarketData/Symbols/Symbol/AmountRisked/
- https://help.ctrader.com/ctrader-algo/references/MarketData/Symbols/Symbol/PipValue/

## Science and economics

Original W35–W37 source result and receipt remain untouched. No new market request, source decryption, directional trial, outcome, order, Cloud activation, authority change or capital reset. Those weeks remain source evidence with the existing five-minute consumer limitation; they do not exhaust Pepperstone's universe. Broad source admission and fresh dated cost/FX/margin proof remain the next economic dependency. No edge, HARD21 or native operational acceptance is claimed.
