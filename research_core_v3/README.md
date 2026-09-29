# Research Core V3

Minimal deterministic research core replacing Runtime V2 orchestration.

Principles:
- Runtime V2 is historical read-only evidence; it has no authority to create new work.
- One frozen experiment specification is executed by one generic causal engine.
- AI interpretation is batch-level only, never an inner-loop transition/router.
- Development response surfaces are separate from confirmation and final PnL certification.
- All features/signals at historical time T use only information available at or before T.
- The 1,576-symbol Pepperstone frontier remains authoritative; local panels are data subsets only.
- Missing/insufficient data keeps scope open and requests authentic Pepperstone cTrader Open API data; it is never research-negative evidence.

Run `python -m research_core_v3.bootstrap --root .` to inventory accepted evidence, salvage Epoch46–48/V2 accounting, freeze the initial multi-mechanism development spec, discover repo-resident OHLC inputs, and write canonical V3 state.
