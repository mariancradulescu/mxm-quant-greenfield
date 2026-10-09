# MASTER1576 — prima măsurătoare numerică istorică autentică

Execuție unică completă, livrare criptată verificată. Verdict descriptiv: răspunsul brut A este negativ la toate cele trei laguri. Superioritatea relativă A−B este pozitivă agregat, dar nu demonstrează un răspuns predictiv brut pozitiv al lui A sau un avantaj economic net. Nicio alegere retrospectivă de lag, instrument sau săptămână.

Aprobarea independentă furnizată în task a fost publicată mecanic. Commit aprobare: `fcf42eb9a2c87f0701c120ffb41fc63d01cb87be`, exact un fișier. Receipt anterior: `9731efcf000393858b65afa250d7e4a8a5741907`; SHA256 `7f8120907f7f94e03da1ec2e6de5ec8669c08ba2ccf2762d5d4c25e9d84754dc`. ARM neschimbat: `f982857d38a385ca77c7d3944587bf20a1669ceb062c0d807ed5e53238021749`. Sursa: `3b4d099f1bd77419056b590d47580f56149c651d`, 72/72 bindings păstrate.

Run real [37927463493 / job 113809733431](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/37927463493/job/113809733431), attempt 1, SUCCESS. HEAD execuție `fcf42eb9a2c87f0701c120ffb41fc63d01cb87be`. Claim real consumat exact o dată. 100/100 shard-uri, 3.355.389 rânduri, 1.576 identități; QUB.AU rămâne în frontieră cu clasificarea istorică support-limited. Patru segmente: 861.415, 850.382, 783.205 și 860.387 rânduri.

Mediile sunt gross log bps, în ordinea A, B, A−B. Numitor calendaristic: 1.059.072 oportunități la fiecare lag. Abstinența comună contribuie zero la numitorul operațional, fără imputarea unui randament neobservat.

| Lag (s) | Suport comun | A calendar | B calendar | A−B calendar | A suport | B suport | A−B suport |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 176799 | -0.12753956339041156 | -0.20186797533273546 | 0.07432841194232365 | -0.7639951610530034 | -1.2092416833329986 | 0.44524652227999356 |
| 300 | 155010 | -0.015411048129882626 | -0.13096370358965917 | 0.11555265545977648 | -0.10529262347597608 | -0.8947809269602446 | 0.7894883034842681 |
| 900 | 155476 | -0.0028725988038121844 | -0.002894877418630301 | 0.00002227861481809693 | -0.01956757930710192 | -0.019719336859088415 | 0.0001517575519863616 |

Cele patru săptămâni cronologice fixe: 20–27 august, 27 august–3 septembrie, 3–10 septembrie și 10–17 septembrie 2026, UTC, capăt exclusiv. Sunt păstrate toate cele 12 rezultate; nu sunt selectate săptămânile favorabile.

| Lag (s) | Săptămână | Suport | A calendar | B calendar | A−B calendar |
|---:|---:|---:|---:|---:|---:|
| 0 | 1 | 45277 | -0.13417450463949768 | -0.09986989460662958 | -0.034304610032868055 |
| 0 | 2 | 44913 | -0.07274856189463151 | -0.26486817372744215 | 0.19211961183281098 |
| 0 | 3 | 41013 | -0.1696713206967356 | -0.12131429112318652 | -0.048357029573549086 |
| 0 | 4 | 45596 | -0.13356386633078157 | -0.3214195418736822 | 0.18785567554290078 |
| 300 | 1 | 39482 | 0.10748586322862125 | -0.11000640739208746 | 0.21749227062070822 |
| 300 | 2 | 39164 | 0.0006655103180763366 | -0.08982272412378563 | 0.09048823444186208 |
| 300 | 3 | 36310 | -0.07862002460732892 | -0.18678881389458532 | 0.10816878928725625 |
| 300 | 4 | 40054 | -0.09117554145889947 | -0.13723686894817833 | 0.04606132748927918 |
| 900 | 1 | 39566 | 0.10806240822063069 | -0.1232437415059446 | 0.2313061497265756 |
| 900 | 2 | 39414 | 0.01890981395853059 | 0.036923457496784155 | -0.018013643538253504 |
| 900 | 3 | 36277 | -0.066592098630284 | 0.021189262994062742 | -0.08778136162434683 |
| 900 | 4 | 40219 | -0.07187051876412623 | 0.053551511340576674 | -0.12542203010470288 |

Instabilitate descriptivă: incrementul la lag 0 are semne −,+,−,+; la 300 secunde +,+,+,+, însă A devine negativ în ultimele două săptămâni; la 900 secunde +,−,−,−, cu increment total doar 0,00002227861481809693 bps pe calendar. A și B sunt negative agregat la toate lagurile. Nu există test confirmator sau inferență iid.

| Motiv | Lag 0 | Lag 300 | Lag 900 |
|---|---:|---:|---:|
| SUPPORTED | 176799 | 155010 | 155476 |
| FEATURE_GAP | 831302 | 853566 | 853360 |
| FEATURE_RECEIPT | 0 | 0 | 0 |
| ZERO_ACTIVITY | 0 | 0 | 0 |
| COMMON_ZERO_DIRECTION_ABSTENTION | 23344 | 20432 | 20013 |
| LABEL_GAP | 27627 | 29973 | 30132 |
| LABEL_RECEIPT | 0 | 0 | 0 |
| DOMAIN_CENSOR | 0 | 91 | 91 |

Suportul este comun și identic pentru A și B la fiecare lag; cohortele diferă între laguri conform regulilor înghețate. Valorile zero și negative, toate abstinențele și censoring-ul sunt păstrate. Invaliditatea numerică a fost fail-closed, nu eliminată retrospectiv. Agregatele săptămânale, mediile pe suport și toate motivele săptămânale sunt în `APPROVED_GLOBAL_AGGREGATES_V1.json`; identitățile, vectorii temporali, covarianțele și starea completă sunt exclusiv criptate.

Reader separat [37928180241 / job 113812098462](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/37928180241/job/113812098462): SUCCESS, fără descărcare de input istoric și fără apel de reducer științific. Verifică toate cele 13 active criptate originale, accounting-ul identităților/rândurilor, acumulatorii, suportul, cele trei laguri și cele patru săptămâni. Evidența citirii este criptată separat. Proiecția publică permite numai agregatele globale solicitate în task, printr-o allowlist distinctă, fără a modifica guard-ul original sau cele 72 de surse. Un test local cu proiecție sintetică a verificat acceptarea schemei și respingerea a șapte forme de divulgare/invaliditate; zero date de piață.

Ref autoritativ: `refs/tags/mxm-numeric-v3-complete-real-40eed7455c8f149efa1ee2116154060d0bdadc16e81b050feb48fe21da1aa584`, commit `1ce3781966f3d00c3c9c02d19ff05c065ee8a907`. Cele patru checkpoint-uri, report, state, journal, receipt și attestation au readback autentificat. Release body rămâne intenționat `NOT_PERSISTED`; ref-ul autoritativ împreună cu verificarea tuturor octeților referiți stabilește completion. Hash-uri Git: delivery `5f9e88ad1860bc6b7642a47284edf639475d2f203ae0e82971016be4f7c51ec3`, completion `697b474d534529807f5370365a217d66b6d0b94c8d298382a152db73cc039955`. Identitățile SHA256 ale tuturor activelor sunt în `EXACT_ENCRYPTED_DELIVERY_AND_READBACK_V1.json`. Nu este revendicată decriptare manuală externă.

Consum real măsurat: wall 300,895721412 s; CPU 184,988620219 s; peak RAM 259.280 KiB; un worker, zero retry/recovery. Reader: wall 17,943810858 s; CPU 5,002845364 s; peak RAM 176.856 KiB. Măsurătorile originale includ finalizarea/readback-ul; sunt diferite de bugetele autorizate.

Receipts istorice și costuri rămân nerezolvate. Close marks sunt referințe de măsurare, nu fill-uri executabile. Gross response nu este net PnL. Fără certificat EUR200, HARD21, portofoliu, alpha confirmator sau broker/live orders. Incidentul istoric de timestamp rămâne neschimbat; nu au fost publicate noi rânduri OHLCV, chei sau vectori individuali.

Singura decizie următoare: audit independent al acestui prim rezultat autentic și al lipsei suportului pentru ipoteza conjunctă A pozitiv și increment pozitiv în domeniul DEVELOPMENT testat, înaintea oricărui nou experiment sau demers economic. Nu se inversează direcțiile și nu se retunează specificația pe baza rezultatului.

`STOP_FOR_INDEPENDENT_FIRST_AUTHENTIC_MASTER1576_NUMERIC_DEVELOPMENT_RESULT_AUDIT`. `NO_LIVE_TRADING`.
