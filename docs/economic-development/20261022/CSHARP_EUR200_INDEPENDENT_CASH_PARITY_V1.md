# MXM — EUR200 original Pepperstone C# ↔ existing continuous-account engine

2026-10-22. **Cash parity demonstrated, no economic edge certified.**

## Origin and durable evidence
- Protected GitHub branch `mxm-remediation-p0-p4-20261015-v1`; PR [#119](https://github.com/mariancradulescu/mxm-quant-greenfield/pull/119) merged `4b105d32ac6a3e89ff590c51bd9f575593d3a343`. Added one shared C# capital admissibility gate to reference and compiled cTrader product, account-global same-label position cap, configurable reserve.
- PR [#120](https://github.com/mariancradulescu/mxm-quant-greenfield/pull/120) merged `130409bc8be97903258597a2b987ece2d0ddcb60`. Original independent Python `competition/continuous_account_replay_v2.py` consumes signed C# trade prices, quantities, entry and exit commissions as one continuous EUR200 account, without cashflow resets or double-charging spread/slippage already embedded in those quoted fill-model prices.
- CI [#39782917697](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/39782917697) passed, including original cTrader/C# compile, two artificial seven-roundtrip ledgers (cash errors 0.0000000 and 0.00000023 EUR) and a negative test rejecting an artificially modified terminal balance.
- Machine-side original authentic Pepperstone source [#39660692230](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/39660692230) reused exactly: 14,003 BID and 14,209 ASK quote events (total 28,212) from the existing 4-hour market window, **no** broker connection. Original preserved market ciphertext SHA256 `f1d828d94b304e2af1f310701f92dcb31db935a8db7fc3f8772087adf5499346`.
- New protected authenticated C# to Python cross-engine run [#39783448541](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/39783448541) **SUCCESS**, source `130409bc8be97903258597a2b987ece2d0ddcb60`. Original 216 dependent C# exploratory sensitivity model leaves run unchanged. No new economic identity or independent confirmation.
- Complete encrypted internal result is native Actions artifact `12427503482`, with ordinary 30-day retention. Ciphertext SHA256 `c3429a8a8f18c647d3a222d07de8b06ec350317aaa27eab728a3889b2837ad5a` and private canonical SHA256 `dfa61599dd0df602074b1dfbef4948e03085d634f4fbbd2bcee638c2c41cc26e`. The artifact is not permanent in Git. This report conserves its **public-safe independent numeric reception and digests** durably.

## Cash parity measured on real preserved Pepperstone quote history under artificial execution terms

| Field | C# and Python independently reconciled |
|---|---:|
| Single initial capital | 200.000000 EUR |
| Modeled entries and exits | 7 / 7 |
| C# modeled terminal EUR cash | 199.418182 |
| Python continuous-account terminal EUR cash | 199.41818190000 |
| Absolute cash difference | 0.0000001 EUR |
| Total modeled per-side commission (Python account) | 1.4 EUR |
| C# model diagnostic total execution cost (including embedded price frictions) | 1.654545 EUR |
| Broker orders | 0 |
| Complete ISO UTC weeks tested | 0 |
| HARD21 qualified | NO |

The 1.4 EUR commission and 1.654545 EUR estimated total cost are different accounting concepts: the C# execution prices already include slippage and additional spread assumptions, whereas the Python account explicitly debits only commissions. Subtracting the full modeled total cost a second time would **double-count** price friction.

## Delimitations / NO PROMOTION
- Quote timestamps are not historical trade arrival/fill certificates. Same-millisecond BID/ASK interleaving is unknowable. No native cTrader execution confirmation.
- **No mark-to-market equity curve equivalence** was established by this test; it independently reconciles only terminal cash and trade/commission identity, on one assumed EURUSD channel with all terminal positions artificially closed at the dataset boundary.
- **No simultaneous multi-instrument shared portfolio** was verified. Although the real cBot now checks all labelled account positions, separate Cloud instances can race on non-atomic account snapshots. The final product requires one serialized orchestration path and broker reconciliation.
- Historical Pepperstone commissions, contract-specific margin/volume lattice, FX conversion, financing and broker stop-out remain unverified in this synthetic execution model.
- The €200 reference here is continuously funded only once, but not the required competition-ready globally diversified account.
- Existing DEVELOPMENT exposure, protected CONFIRMATION and C033/V2 scientific outcome ledger remain unchanged; no new validation, HARD21 or actual economic advantage. All 216 sensitivity cells remain dependent source reuses.
- **Director disposition: engineering accountability advanced; NO ALPHA / CBOT PROMOTION.** Select no apparent winner from a four-hour exposed quote sample. Further authenticated breadth/duration and actual brokerage cost feasibility are material prerequisites.

No LIVE trade, Cloud enablement, OAuth refresh, owner state change or added broker request occurred.
