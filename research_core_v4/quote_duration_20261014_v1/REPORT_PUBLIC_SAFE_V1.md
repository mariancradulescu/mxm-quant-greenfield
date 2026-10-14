# MXM — native quote duration economic DEVELOPMENT pilot

Verdict: **CLOSED_NO_PROMOTION_NEGATIVE_EXACT**. Un singur mecanism înghețat, după calificare cost-first înainte de outcomes. Rezultatul primar, fără promovare, este negativ după costurile de referință și nu bate comparatorul count; cash este comparator. Nu se declară nul pentru familia de timing/cotații sau întreg universul Pepperstone. Factor drift, carry și exacte închise sunt păstrate.

Mecanismul DIRECTIONAL_QUOTE_WAITING_TIME_ASYMMETRY_V1 folosește durate marcate ale schimbărilor midpoint, din Time/Bid/Ask native, distinct de count și endpoint. Cele două alternative examinate înainte de numeric (downside variance și price/activity saturation) au fost respinse pentru originalitate insuficientă. Predictorul și adaptorul compilat C# nu necesită HTTP/Python/GitHub/AI în producție; nu există deployment. Kernelul C# și Python au paritate pe input autentic. Feed delivery/history/fills Cloud nu sunt certificate automat.

Universul păstrează catalogul complet și motivele structurale/date/quote/FX/cost/risk. Inventarul include identități cu quote pages, fără acestea și cu alte istorii încă nereconciliate; corpusul side-quote conservat este o limită a suportului, nu un cap nou de univers sau un verdict despre broker. Nu s-a selectat după rezultate câștigătoare.

Există contabilizare paired pe quotes BID/ASK și FX autentice complete, cu comisioane din snapshot curent și slippage/funding stress etichetate. Acesta este NET de referință/proxy, nu fills/taxe istorice autentificate. Full historical actual NET rămâne N/A. Oportunitățile admise cu exit/FX lipsă nu sunt imputate zero sau folosite la intrare.

Ledgerul separat are subtotal pozitiv de închideri cunoscute, apoi halt la prima ieșire/FX cenzurată; NET complet este N/A și nu califică o strategie. Cohorta completă evaluabilă și scenariile/blocurile nu justifică promovare. Planned tail/friction risk are încălcări observate pe oportunități; max adverse excursion, margin istoric și executabilitate integrală nu sunt certificate. HARD21 este nedemonstrat; ferestrele sparse nu sunt acoperire continuă și nu devin fills.

| Phase | Source HEAD | Run | Job | Release | OWNER asset |
| --- | --- | --- | --- | --- | --- |
| Cost/native compatibility qualification | d8bb35a42d07f70437cd1c2b33788d6c3930c86d | 38527989736 | 115732803461 | 412441630 | 639592539 |
| One frozen DEVELOPMENT pilot | be8f0526adea020d6891043ee6472df78ad58ba7 | 38528427815 | 115734220271 | 412444612 | 639601405 |

[Encrypted qualification](https://github.com/mariancradulescu/mxm-quant-greenfield/releases/tag/mxm-duration-20261014-duration-cost-precheck-v1-38527989736) • [Encrypted pilot and all detailed records](https://github.com/mariancradulescu/mxm-quant-greenfield/releases/tag/mxm-duration-20261014-duration-one-pilot-v1-38528427815)

Pilot OWNER ciphertext SHA256: `79a92e65af00b491d7e3b2a6449442fbcf51c66a6f0e9516089e5d43b990a98b`.

Pilot canonical SHA256: `7577886a6c5640945bf2ef97266e06d413cc2072a4faf746a67d91aee0963bdc`.

Pilot summary canonical SHA256: `020e54575a7c9a204bfd76d5005dcbd540f45cf494561ae954771a7967321b3b`.

[VERIFIED_DELIVERY_ACKS_V1.json](VERIFIED_DELIVERY_ACKS_V1.json) records same-session recipient decryption and machine-side OWNER readback; signatures RSA-PSS/SHA256 under [RECIPIENT_PUBLIC_KEY.pem](RECIPIENT_PUBLIC_KEY.pem). [EXACT_DECISION_V1.json](EXACT_DECISION_V1.json) binds design, reconciliation, source/run and no-rescue verdict. Qualification is not numeric profit SUCCESS.

[Full financial/scientific report — OWNER encrypted](duration-final-report-owner.mxmenc): ciphertext SHA256 `4f4992ba14e6b70370926f1ac0fe0d922187122f0e1a016dd06bb83f5f0d5a9b`; plaintext report SHA256 `af36ea6261d57b8e6fae4c7b9f27853546e2cb73cc5ecd4829fcb94b86ca7bc0`. The archive uses the existing pinned OWNER key and standard MXM envelope. Its inner cipher was locally read back through a session mirror; no new OWNER-private report-archive decryption is claimed. Actual numerical results have OWNER and recipient readback verified. No assumption of session-private-key persistence.

The first qualification build failed before data/pilot; numeric literal syntax and recursive manifest binding were corrected without changing scientific side/window/support/cost policy. No failed economic outcomes were retried. Historical files predating the owner's accepted HEAD remain unchanged.

Eight causal/control tests and CSharp/cTrader API compilation passed in both successful phases. All source hashes were checked against the published execution HEADs. Production native API references: [Tick](https://help.ctrader.com/ctrader-algo/references/MarketData/Ticks/Tick/), [MarketData](https://help.ctrader.com/ctrader-algo/references/MarketData/MarketData/), [Symbol](https://help.ctrader.com/ctrader-algo/references/MarketData/Symbols/Symbol/).

No new broker requests, demo/LIVE orders, fills, external market data, protected forward, Stage8 or Cloud deployment. All financial values, per-symbol support and raw records remain encrypted.
