# MXM — audit semantic al datelor native recuperate, 2026-10-10

Rol în această misiune: EXECUTOR_DIRECTOR_MXM_QUANT_GREENFIELD. Acest raport descrie execuția și verificările efectuate; nu pretinde acceptare de către auditorul independent.

Verdict: **DATA_LIMITED V1 păstrat. Paritatea paginilor salvate, decoderului, ultimelor referințe și formulelor verificate: PASS. Semantica istorică este clarificată; disponibilitatea efectivă în Cloud și fill-urile rămân nedemonstrate. Nu există promovare sau dovadă de avantaj NET.**

## Identitate, integritate și execuție

Repository: `mariancradulescu/mxm-quant-greenfield`; branch: `performance-research-v3-20260922`.

HEAD inițial verificat live prin Git: `6b6aea55021db5941239f4e4365f212afb4d574c`. Este descendent cu 10 commituri al `223117350f65048865815922f23d14102148aa7d`; comparația are exact 33 adăugări și zero modificări/ștergeri ale fișierelor precedente.

Commitul execuției semantice: [`fb0a880e34b48e04f4f3fcb996d447da37618d2a`](https://github.com/mariancradulescu/mxm-quant-greenfield/commit/fb0a880e34b48e04f4f3fcb996d447da37618d2a). Părinte exact: HEAD inițial. Trei fișiere adăugate: runner semantic, autoritate pentru o singură execuție, workflow separat. Publicarea raportului și a recepției este un commit ulterior exclusiv aditiv; HEAD final este în recepția finală și în răspunsul de livrare.

Execuția [`38081134886`](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/38081134886), job [`114298105184`](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/38081134886/job/114298105184), tentativa 1: **SUCCESS**. Logul conține status final PASS și publicare criptată, legate de commitul execuției. Au fost verificate inclusiv bindings SHA256, ancestry, identitatea criptografică și canonică a intrărilor, conservarea tuturor fișierelor inițiale și freeze-urile validate de infrastructura existentă.

| Fișier | SHA256 |
|---|---|
| `native_semantic_audit_v1/runner_v1.py` | `3dfaf2564b2beb9e618831f673ad9af972e0546784e3286ff3dbdf4249970156` |
| `.github/workflows/mxm-native-semantic-audit-v1.yml` | `d5bb3b42fc5a980ce7104f58ab191d83d244c9409e09a2431027a4cda4f1d8bb` |
| `native_executable_qualification_v1/runner_v1.py`, păstrat | `42e60d44d60be017565039fa10e9d373a26b1fa33307f5431f03289119d905c5` |
| `native_executable_qualification_v1/POLICY_V1.json`, păstrat | `75c30ef5b52fad1dc3427b26e4b099220f6b2580886e9c6140c8651fa98c31ac` |
| `m6/cost_evidence.py`, păstrat | `0c267293d7e3ed28ed8d3f8c1183412fc76a658f9afd9a47d6789cda0c25f84d` |

Căile modulelor native abreviate în tabel apar sub `research_core_v4/`. Autoritatea `EXECUTION_V1.json` conține toate căile complete și bindings.

Intrări exclusiv existente: release `409145057`, asset `628756517`, SHA256 `e1562c41ff19febf34c3a216fc32fc3b4cbe67a2219c4e921da26206bbafb1f6`; cost source release `408644252`, asset `626999470`; readback release `409146899`, asset `628764104`. Decoderul existent și documentația oficială au fost citite, fără schimbarea lor.

Au fost reconciliate și joburile existente SUCCESS: `38077972378/114288836403`, `38078431756/114290172267`, `38077813702/114288376169`. Statusurile și logurile finale sunt legate de SHA-urile sursă originale.

Noua livrare criptată: [release `409167114`](https://github.com/mariancradulescu/mxm-quant-greenfield/releases/tag/mxm-owner-frontier-nativesemantics-20261010_sav-38081134886).

| Asset | ID | SHA256 ciphertext |
|---|---|---|
| `nativesemantics-private-result.mxmenc` | `628844151` | `d58a122fb5297be9df13e9505d21e58ae453e04a9e5fe5ee5e52d5d45892f3a5` |
| `nativesemantics-private-delivery.mxmenc` | `628844197` | `bc49c39fa3050c995ada05189a71c95ac6b1162f54aa9ac8af64fee893ff51c0` |
| `nativesemantics-attestation.mxmenc` | `628844250` | `a5c2987f4eb5356051364bc665556d092221cf457de165f97873c8090b46a993` |

Relay criptat: release `409167183`; SHA256 envelope `5e45f909763a71769b39a64551d6992b51488c661cb52ed96a2a6d10a1841319`. Prețurile, timestampurile private și diagnosticele numerice sunt exclusiv în artefactele criptate. Execuția a autentificat și decriptat intrările pe runner; sesiunea locală nu a extras cheia privată.

## A. Barele M5 și momentul deciziei

`qualify()` caută `t-600-i*300`, pentru `i=0..11`. Acestea sunt timestampuri de **deschidere**, nu de închidere. Fereastra rezultată este `[t-3900,t-300)`: exact 60 minute, cu un decalaj de 5 minute înaintea intrării.

| Referință | Prima deschidere | Ultima deschidere | Ultima închidere | Disponibilitate presupusă, închidere + 5 s |
|---|---|---|---|---|
| 09:15:00 UTC | 08:10:00 | 09:05:00 | 09:10:00 | 09:10:05 |
| 13:15:00 UTC | 12:10:00 | 13:05:00 | 13:10:00 | 13:10:05 |

Politica spune literal `LATEST_BAR_CLOSE_AT_ENTRY_MINUS5_SECONDS`. Pe o grilă M5 nu există închidere la 09:14:55. Dacă formularea înseamnă „ultima bară închisă **cel târziu** la intrare minus 5 secunde”, implementarea este consistentă: ultima eligibilă la 09:15 este închiderea 09:10. Nu se poate afirma un defect de indexare doar fiindcă fereastra este mai veche.

Dacă intenția era „bară închisă la 09:15, decizie la 09:15:05”, ar trebui deschideri 08:15..09:10 și referințe de intrare la 09:15:05. V1 nu conține această deplasare: episoadele, tickurile și FX sunt ancorate la 09:15:00, respectiv 13:15:00. Intenția alternativă nu este recuperabilă unic din textul înghețat. Nu o adoptăm retrospectiv.

Momentul presupus de cod este `t`, ca referință de calificare. Nu este un timestamp de decizie live măsurat. Auditul a verificat barele brute din completarea M5 față de decoderul acceptat, filtrarea overfetch-ului și rândurile canonice salvate; a verificat și existența celor 12 bare pentru episoadele deja salvate. Nu a reapelat `qualify()` sau recalculat calificarea.

Documentația [Bar events](https://help.ctrader.com/ctrader-algo/documentation/cbots/cbot-bar-events/) arată că evenimentele barelor depind de sosirea unui tick: închiderea calendaristică nu certifică disponibilitatea callback-ului la aceeași secundă. Historical Open API și roundtrip-ul achiziției nu măsoară livrarea istorică în Cloud. Tamponul de 5 secunde rămâne o ipoteză, nu un SLA demonstrat.

## B. BID/ASK: ce demonstrează paginile

Documentația oficială [GetTickDataRes](https://help.ctrader.com/open-api/messages/#proto-oagettickdatares) și [schema Spotware](https://github.com/spotware/openapi-proto-messages/blob/main/OpenApiMessages.proto) specifică newest-first, primul timestamp absolut Unix ms și următoarele timestampuri relative. Decoderul acceptat însumează delta timestamp și delta preț, apoi inversează lista în oldest-first. Auditul a reconstruit cumulativ rândurile salvate, verificând domeniul temporal, paritatea cu decoderul și cu ultima referință stocată.

Important pentru referința economică: `decoded[-1]` după inversare este primul tick brut al paginii. Timestampul și prețul ultimului tick selectat sunt astfel verificate direct față de primul rând brut, fără a depinde de acumularea deltelor tickurilor mai vechi. [Symbol data](https://help.ctrader.com/open-api/symbol-data/) documentează scala 1/100000 și rotunjirea la digits. Documentația publică este explicită pentru delta timestamp; nu trebuie prezentată drept o specificație la fel de detaliată a recurenței prețurilor. Paritatea internă nu constituie singură o certificare externă a fiecărui preț intermediar.

`hasMore=true` înseamnă că filtrul are mai multe înregistrări decât pagina. `false` certifică epuizarea răspunsului pentru filtrul respectiv conform API, nu sănătatea întregului feed sau istoricul de dinaintea ferestrei. V1 exclude orice pagină trunchiată. Auditul verifică toate cele 600 de recepții de latură din grila originală; nu face 600 de cereri noi. O fereastră goală nu demonstrează că nu exista o cotație precedentă menținută în stare.

Ultimul BID și ultimul ASK sunt observații separate cu timestampuri ≤ `t`. Reunirea lor este o **referință istorică as-of**, condiționată de retenția stării între actualizări. Nu dovedește o cotație atomică, sosirea pe client înaintea deciziei, validitatea neîntreruptă, lichiditatea sau un fill. Egalitatea timestampurilor nu adaugă o ordine globală între cele două fluxuri.

Vechimea unei actualizări este `t-last_side_timestamp`; skew-ul este diferența timestampurilor laturilor. O actualizare mai veche nu demonstrează expirarea prețului. Nici documentația examinată nu permite să etichetăm toate observațiile istorice drept „ultime modificări de preț”: distingem **actualizare arhivată**, **modificare observată de valoare** și **validitate executabilă**.

Toate cele **13 excluderi de vechime și patru de skew** au fost conservate și confruntate cu readback-ul existent. Nicio observație nu este reacceptată, nicio regulă sau fracție de suport nu este relaxată.

[Tick.Time, Tick.Bid, Tick.Ask](https://help.ctrader.com/ctrader-algo/references/MarketData/Ticks/Tick/) descriu un obiect nativ cu timpul tickului și ambele prețuri. Nu sunt două timestampuri de actualizare a laturilor și nici dovada unei corespondențe unu-la-unu cu două pagini historical Open API. [Spot events](https://help.ctrader.com/open-api/symbol-data/) pot avea doar unul dintre câmpurile BID/ASK.

Proba Cloud înghețată urmărește schimbări de valoare prin `q.Bid!=previousBid` / `q.Ask!=previousAsk`, nu toate actualizările aceleiași valori. Ea nu instrumentează bare M5 sau decizii economice. Prin urmare nu poate certifica singură tamponul M5, istoricul complet al laturilor sau fill-urile. Pachetul SHA256 `137259adc7d021272d2415f1887d3a5edb2310c0da8e611e3458690fe0d321a3` și sursa au rămas intacte; nu au fost recompilate sau deployate.

## C. Conversia EURUSD și costurile

Metadata autentică salvată confirmă USD ca monedă cotată pentru EURUSD, GBPUSD și SpotCrude. Pentru cantitatea nativă `u`, un PnL în moneda cotată este în USD; transformarea în EUR folosește EURUSD, indiferent de moneda de bază a instrumentului.

Pentru EURUSD BID=`b`, ASK=`a`, exprimate în USD/EUR:

| Flux USD | Referință EUR înaintea taxei de conversie | Explicație |
|---|---|---|
| Obligație/pierdere de `L>0` USD | `L/b` EUR, pierdere cu semn negativ | Se vinde EUR pentru USD la BID |
| Încasare/profit de `R>0` USD | `R/a` EUR | Se cumpără EUR cu USD la ASK |

Acestea sunt convenții de conversie pe piață, nu dovada ratei efective aplicate istoric de broker. Spreadul EURUSD la conversie și taxa PnL sunt componente diferite; nu se presupune o conversie fizică integrală a notionalului la deschiderea unui CFD.

În V1, `risk=u*pre_entry_range/fx_entry_bid` și `stop_distance=fx_entry_bid/u` folosesc doar referința de la intrare. Paritatea lor cu valorile salvate a trecut. Sunt proxy-uri, nu pierdere garantată la stop: cursul de la închiderea pierderii, gap-ul și slippage-ul sunt necunoscute la intrare.

`notional=u*entry_mid/min(fx_entry_bid,fx_exit_bid)` utilizează și ieșirea, alegând conservator cea mai mare valoare EUR dintre cele două referințe BID. Acesta este un scenariu retrospectiv, nu notional causal de dimensionare. Spreadul mediu la cele două capete, existența cotațiilor/FX la ieșire și session proxy-ul ieșirii sunt de asemenea retrospective. Nu devin filtre de intrare.

V1 calculează `costcash=notional*(half_spread_entry+half_spread_exit+current_commission_bps+2)/10000`. Rata taxei de conversie este citită și prezența ei condiționează gate-ul, însă **nu este adăugată în `costcash`**. Așadar costul nu este NET all-in, chiar când câmpul este cunoscut. Nu adăugăm retrospectiv taxa și nu rescriem verdictul.

Comisionul este scenariu pe termenii nativi actuali, aplicat prețului istoric de la intrare; nu certifică două taxe istorice exacte de execuție. Marja, programul, termenii swap și taxa de conversie actuale nu sunt contract istoric datat. Cei 2 bps sunt stress presupus, nu slippage observat. Costurile istorice, ratele efective de conversie, execuția stopului și fill-urile rămân necunoscute. Necunoscut nu înseamnă zero.

## D. Decizie și design distinct propus

Datele salvate susțin cercetare istorică asupra barelor native și referințelor BID/ASK la grila fixă. Ele nu certifică oportunități independente, live tradability sau NET. V1 rămâne DATA_LIMITED, pragul 95% este intact, iar ceasurile/instrumentele nu sunt selectate după randamente.

Propunere **neexecutată, fără ARM**: protocol distinct de suport cauzal și contabilitate, cu aceleași trei identități și ceasuri 09:15/13:15 UTC, decizie la `t`, fereastră explicită `[t-3900,t-300)`, orizonturi 1h/4h. Se declară de la început lag-ul de 5 minute. Eligibilitatea la intrare poate folosi numai bare și referințe intrare/FX intrare; disponibilitatea la ieșire se tratează separat ca evaluabilitate retrospectivă, cu toate lipsurile raportate, nu ca filtru de tranzacție. Pragul 95% pe blocuri și săptămâni nu se relaxează; eșecul gate-ului oprește promovarea.

Contabilitatea viitoare trebuie să separe long/short, ASK de cumpărare și BID de vânzare la fiecare capăt, obligațiile USD convertite prin BID EURUSD și încasările prin ASK, taxele de conversie, comisioanele pe fiecare latură și scenariile 0/1/2 bps. Marja istorică și funding-ul rămân explicit necunoscute unde lipsesc dovezi. Range-ul nu este semnal, stop sau dovadă de avantaj direcțional. Nu desemnăm acum un model direcțional ori un cohort calificat nou.

Necunoscuta minimă pentru un design executabil în Cloud: **starea efectiv disponibilă clientului la decizie**, inclusiv timpul de recepție și continuitatea după reload, plus disponibilitatea barelor relevante. Dovezi necesare: recepții autentice cu timp server și callback/client, identitate cont/simbol/instanță, ultimul BID/ASK observat și barele disponibile la referința deciziei. Un număr de schimbări de preț sau vârsta ultimei schimbări nu este suficient. Se pot verifica dovezi deja existente ori rezultatul probei deja autorizate, în limitele sale; misiunea aceasta nu autorizează modificarea probei, achiziții sau deploymenturi suplimentare. În lipsa dovezii, rămâne cercetare pe referințe istorice, fără afirmație de implementabilitate live.

## Limite CI și guvernanță

Cele trei workflow-uri generale pornite automat au FAILURE: `38081134790`, `38081134944`, `38081134830`. Joburile publication-state eșuează cu `PUBLICATION_ONLY_FAIL_CLOSED prospective boundary response_execution_authorized`; joburile metodologice din aval sunt SKIPPED. În `V4_STATE.json` la HEAD inițial, câmpul este absent, iar `check_state()` reproduce exact eroarea. Bytes ai stării și verifierului sunt păstrați față de HEAD inițial. Auditul semantic nu a introdus această neconcordanță și nu a modificat starea înghețată ca să facă CI verde. Raportul nu afirmă că întreaga suită CI trece.

Zero cereri noi la broker; zero autentificări Pepperstone noi; zero ordine, protected forward, deploymenturi, replay al exacturilor sau modele direcționale. Verificarea semantică și publicarea criptată sunt încheiate; lipsurile de dovezi live și guvernanța CI sunt declarate, nu mascate.
