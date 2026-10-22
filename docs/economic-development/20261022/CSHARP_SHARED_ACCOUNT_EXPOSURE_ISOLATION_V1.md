# MXM C# — EUR200 shared broker account isolation before new entries

Date 2026-10-22. Existing B–E product and source only. Engineering DEVELOPMENT, no new economic trial.

## Material defect fixed
After PR #126 the existing multi-symbol cBot used the *whole account* equity/free margin, but the account position cap and the aggregate estimated stop-risk calculation considered only `MXM_CSHARP_REFERENCE_V1`-labelled positions. Another bot or manual account position (or pending order) could consume the same EUR200 and be omitted from this robot's decision-time risk budget.

The revised product now enumerates **all actual broker-account open positions and pending orders** immediately before each proposed new order. Its single-account isolation gate rejects new entries unless every open account position is within this cBot's existing MXM label and there are **zero pending broker orders**. An inconsistent count fails closed. The original capital gate, stop-risk estimate and two-symbol orchestration remain intact, and the code still prevents any non-backtest LIVE trading.

The new pure C# check is compiled into the original `.algo` product and run against deterministic positive/negative artificial samples. Actual order submission remains behind this gate and the prior margin/stop-risk admission.

## Operational boundaries
- The gate does not manage or close unowned positions, and reducing an existing owned position through the pre-existing exit path is not prohibited by the new-entry fence.
- Another process might place a position **after** the snapshot: this is **not** an atomic account lock, nor proof of one and only one Cloud deployment. Existing shared-label positions from another cBot cannot reliably be distinguished by this gate. Production use still requires demonstrable single-instance broker operational control.
- No certified broker margin lattice, historical fill, exact commission, conversion, financing or cross-asset equity path follows from this change. Fail-closed admission may legitimately suppress trading and thereby reduce HARD21 feasibility.
- Pure CI fixtures are artificial; no broker request, new Pepperstone quote, new strategy trial, economic registry write, protected confirmation, owner checkpoint, order or Cloud activation is part of this PR.

**Disposition:** account-level admission correctness improvement only. The existing four-hour BID/ASK scenarios remain exposed DEVELOPMENT and losing under the modeled risk-admitted cases, and do not establish an edge. HARD21 has not been proven over any complete ISO UTC week. The next validation gap is a real broker-integrated single-instance demonstration and a complete multi-symbol, bid/ask-cost-aware continuous-account replay on sufficiently broad and held-out chronology.
