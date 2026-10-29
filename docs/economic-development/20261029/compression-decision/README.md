# Frozen compression candidate: close without Stage B

Decision: **CLOSED_FROZEN_CONFIGURATION_CANNOT_MEET_HARD21_ON_DECLARED_DEVELOPMENT**.
Identity V4-SUP-20261028-COMPRESSION; complete unchanged AUDUSD5, Copper111,
SpotCrude250; basis official HEAD 2f25fb27f011c47518ea87bb3a95023ff0f9c57b.
No instrument, session, threshold, entry delay, holding period or serialization
rule is changed. This is a final economic disposition for this configuration,
not an infrastructure milestone or a statement that all compression strategies
are impossible.

## Necessary capital and execution screen

The already accepted September22 broker capture was recovered without broker
contact. Both ZIP SHA2569553fd3b60f4f5dc8428c30d19cde7d7a13cad12de18a27a93785836e97f5f77
and internal JSON SHA256d144494113106c1ab65c7ae0bcb45a60176a1bccadf13ad7c3051e2ca40f9f69
match data/BROKER_NATIVE_COMPETITION_UNIVERSE_ACCEPTANCE_V2.json.
Original: [accepted broker capture](https://chatgpt.com/library?file_id=libfile_3e723ee97540819198f63ce379e7b3d4&account_id=personal).
Only the three requested product declarations are projected here; no source
prices, credentials or raw account identifier are published.

| Instrument | Minimum units | Step units | Maximum units | Captured minimum BUY / SELL margin EUR |
| --- | ---: | ---: | ---: | ---: |
| AUDUSD | 1000 | 1000 | 10000000 | 31.04 / 31.04 |
| Copper | 20 | 20 | 200000 | 11.95 / 11.94 |
| SpotCrude | 1 | 1 | 5000 | 8.53 / 8.52 |

Native volume fields are hundredths of units; lot sizes are100000,2000,100
units respectively. Enabled=true, tradingMode=0, short-selling=true were
declared for all three. Existing current_margin_evidence.reference and
universe_commission_checks.terms decode/reconcile the exact raw minimum-volume
bindings and commission fields, without a new capital calculator.

At those dated minimum volumes, the sum of the larger directional margin for
each instrument is51.52EUR. A hypothetical flat200EUR account would have148.48EUR
left **before fees and floating losses**. Each ticket is below80EUR and this
margin-only sum leaves more than120EUR. Therefore these declarations do **not**
prove capital impossibility. They also do not admit three simultaneous trades:
real overlap times, marked equity, fees, FX, portfolio risk and the2EUR
new-entry estimated-loss ceiling still apply. Summing minimum margins is an
all-three-open necessary arithmetic scenario, not measured peak exposure.

The later authenticated October27 receipt40483982559 separately declares
SpotCrude1unit min/step and9.11/9.10EUR BUY/SELL margin. It must not be silently
spliced into the September snapshot or called an August margin history.
The source is docs/economic-development/20261027/current-margin-40483982559/receipt.json.

The September declarations imply AUDUSD0.03USD per side at minimum volume
(100000cent-units /10000000lot-cent-units *3USD/lot); Copper and SpotCrude
declare zero commission/minimum commission. Zero commission does not imply
zero spread, slippage, financing or FX cost. The source contains signed swap
declarations, retained in the projection; they are not verified August charges.
The fixed07–15UTC decision window, delayed entry and two-hour exit cannot be
converted into an unconditional zero-financing assertion without dated schedule,
charge and fill evidence.

A1000EUR Stage A notional is a normalization. An exact executable quantity
would require1000*EURUSD/target-price units and membership in the dated broker
volume lattice. No such quantity was bound in Stage A. Rounding upward,
choosing a different notional, scaling68.933730EUR to a200EUR account, or
inserting a stop to manufacture a2EUR risk bound would change assumptions.
The frozen two-hour exit alone does not bound intrahold loss. No C# account
admission is asserted from these metadata.

## Decisive economic stop before an unnecessary account replay

The authentic run40770145814/job123105014767 published75 settled compression
opportunities, with zero post-signal censorship. Stage A serializes each
instrument; it does not apply shared-capital admission.

| Complete ISO UTC week | AUDUSD | Copper | SpotCrude | All instruments | Deficit versus21 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2026-W32 | 7 | 12 | 8 | 27 | 0 |
| 2026-W33 | 6 | 6 | 8 | 20 | 1 |
| 2026-W34 | 6 | 5 | 2 | 13 | 8 |
| 2026-W35 | 6 | 4 | 5 | 15 | 6 |

For the unchanged configuration, accepted account entries are a subset of
those opportunities. Account margin, risk, costs, shared inventory and overlap
controls can remove entries; they cannot create signals. Thus three weeks
cannot reach HARD21 even with unlimited frictionless capital. Surplus entries
in week32 cannot repair deficits in other weeks. Splitting tickets or counting
exits as new entries is not fulfillment of the existing gate.

There is an additional conservative cross-check independent of retaining the
Stage A serialization decision: all75 accepted signals plus the7 overlap
rejections total only82 raw predicate hits, below the84 entries necessary
across four21-entry weeks. All540 eligible target decisions had complete
future source support; there are no censored signals to recover. Even removing
serialization would not establish the required density. Serialization remains
unchanged in this decision.

This is a deterministic failure of a necessary economic/product requirement
on the declared four-week cohort. It is not a claim of universal capital
impossibility or a claim about every future week. A Stage B replay cannot
reverse it without changing the frozen configuration or counting convention.
**Stage B is not admitted or executed.** No new evaluator, workflow, collection,
model outcome or simulator modification is needed.

## Profit, cost sensitivity and scientific status

Stage A gross95.986667EUR minus coarse cost27.052937EUR gives68.933730EUR
on75 separate1000EUR normalized opportunities. SpotCrude contributes63.003765EUR
(about91.4%); the entire three-instrument configuration remains the object of
the decision. Estimated remaining uniform round-trip cost headroom is
68.933730/(75*1000)*10000=9.191164basis points. This is only linear Stage A
break-even arithmetic. It is not a guarantee about heterogeneous actual costs
or discrete executable volumes.

No200EUR account profit, drawdown, accepted/rejected account ledger, measured
peak exposure or loss distribution has been generated. Their JSON fields are
null, not zero. Chronological execution sensitivity remains unmeasured because
the necessary density gate already fails. Do not relaunch this configuration
to produce those figures after closure.

This was one positive family selected among three dependent families. Impulse
and residual families remain closed at their original negative outcomes.
No scientific budget is refunded: the receipt still records V2used21,
remaining63 and three separately admitted V4families. The four August weeks
remain exposed DEVELOPMENT; this disposition is not independent validation.
No independent confirmation evidence has been admitted or evaluated here, and
availability of genuinely independent permissible evidence has not been
established. An extra replay of the same four weeks cannot provide it.
The closed configuration does not advance to that stage.

## Evidence and reproduction

- stage-a-40770145814.json is the exact JSON text extracted from the successful
  GitHub job log, with a terminal newline. It is explicitly not represented as
  an artifact-byte download. The original artifact is12851378503, ZIP digest
 15245c890c6ce633d225e3c05302a9d1a0f4b3f4de84b4dc0b3c34ba0e1822c3.
- broker-minimum-volume-projection.json preserves three public product terms,
  raw integer margin bindings, original capture hashes/time and existing
  Python decoder results. Original capture must be retrieved and hash-checked
  to independently authenticate the projection.
- decision.json binds source/spec/cost/projection hashes, reason, weekly
  ceilings, capital limitations and explicit closure.

Reproduce the decisive arithmetic without prices, secrets or model execution
from the repository root:

```python
import json
from pathlib import Path
p = Path("docs/economic-development/20261029/compression-decision")
r = json.loads((p / "stage-a-40770145814.json").read_bytes())
m = next(x for x in r["models"] if x["identity"] == "V4-SUP-20261028-COMPRESSION")
weeks = {
    w: sum(x["weekly"][w]["signals"] for x in m["per_market"])
    for w in ("2026-W32", "2026-W33", "2026-W34", "2026-W35")
}
assert list(weeks.values()) == [27, 20, 13, 15]
assert m["settled"] == m["causal_signals"] == sum(weeks.values()) == 75
assert sum(x["rejections"].get("SERIAL_OVERLAP_REJECTED", 0)
           for x in m["per_market"]) == 7
assert 75 + 7 < 4 * 21
from research_core_v4.laboratory.current_margin_evidence import reference
b = json.loads((p / "broker-minimum-volume-projection.json").read_bytes())
from decimal import Decimal
v = reference(b["items"])
assert sum(max(x["margin"]["BuyEur"], x["margin"]["SellEur"])
           for x in v) == Decimal("51.52")
print(weeks, "CLOSED_NO_STAGE_B")
```

No orders LIVE/DEMO, Cloud activation, access extension, protected-data opening,
OWNER checkpoint/authority change, new family or automatic follow-up.

