# MXM — B: suportul cotațiilor și autoritatea temporală a costurilor

19 octombrie 2026. Continuarea finală, prospectivă, a FRONTIER_SUPPORT_PREGATE_B. Nu este o reluare V4–V6, C033 sau a recepției; s-a reutilizat numai cititorul corpusului păstrat, fără funcțiile lor de cercetare/replay.

## Constatări verificate machine-side

Eșantion fix: aceiași 29 de identificatori din 29 de clase. Cache-ul exact păstrat conține **1.284 de momente unice de cotație pentru 9 identificatori**; **493 de momente pentru 8 identificatori** trec verificarea bilaterală autentică, cauzală, de vechime și sincronizare. Nu există conflicte între chitanțele aceluiași moment.

Dintre celelalte momente: 634 sunt prea vechi pentru limita de 5 secunde, 22 au decalaj bid/ask peste 2 secunde, iar 135 nu au ambele laturi în starea autentică-cauzală necesară. Aceste numere sunt suport de date, NU tranzacții sau rezultate economice.

**Niciuna dintre cotațiile examinate nu acoperă perioada M5 20–26 august 2026.** Cele 22.571 de bare măsurate în prima execuție B nu pot fi combinate arbitrar cu cotații din alte date pentru a declara costuri realizabile. Domeniul constatării este acest cache de recovery, NU toate arhivele autorizate și NU întregul broker.

Toți cei 29 de identificatori au în catalog câmpurile native de volum și cele cinci câmpuri verificate de comision/conversie; sunt prezente și holiday, schedule și scheduleTimeZone. Prezența nu înseamnă valabilitate temporală. Eticheta nativă este:

CATALOG_2026OCT11_CURRENT_REFERENCE;HISTORICAL_COMMISSION_MARGIN_FUNDING_AND_REAL_FILLS_UNKNOWN

Prin urmare, această referință din 11 octombrie nu certifică taxele, marja, finanțarea sau calendarul efectiv din august. Nu am calculat comisioane istorice prin imputare, randamente, PnL sau feasibility EUR200 pe baza ei.

## Suport per instrument

| Instrument | Clasă | Momente în cache | Bilaterale valide | Valide în perioada M5 |
|---|---|---:|---:|---:|
| EBS.AT | AT Equities | 160 | 29 | 0 |
| AGL.AU | AU Equities | 0 | 0 | 0 |
| ABI.BE | BE Equities | 160 | 20 | 0 |
| NESN.CH | CH Equities | 160 | 21 | 0 |
| Sugar | Commodities (Cash) | 0 | 0 | 0 |
| LTCUSD | Crypto Currency (Spot) | 0 | 0 | 0 |
| USDX | Currency Index (Spot) | 0 | 0 | 0 |
| AIXAd.DE | DE Equities | 0 | 0 | 0 |
| NOVOB.DK | DK Equities | 160 | 112 | 0 |
| ITX.ES | ES Equities | 0 | 0 | 0 |
| AAXJ.US | ETFs | 0 | 0 | 0 |
| NatGas | Energies (Spot) | 4 | 0 | 0 |
| NDA.FI | FI Equities | 160 | 14 | 0 |
| OR.FR | FR Equities | 0 | 0 | 0 |
| EURJPY | Forex (Spot) | 168 | 152 | 0 |
| XAUUSD-F | Forwards - Commodities | 0 | 0 | 0 |
| JPN225-F | Forwards - Indices | 156 | 132 | 0 |
| EUBobl-F | Forwards - Treasuries | 0 | 0 | 0 |
| III.GB | GB Equities | 0 | 0 | 0 |
| 0001.HK | HK Equities | 0 | 0 | 0 |
| RYA.IE | IE Equities | 0 | 0 | 0 |
| CN50 | Indices (Spot) | 0 | 0 | 0 |
| XAUUSD | Metals (Spot) | 0 | 0 | 0 |
| DNB.NO | NO Equities | 0 | 0 | 0 |
| EDP.PT | PT Equities | 156 | 13 | 0 |
| WTOIL-PERP | Perpetual Commodity | 0 | 0 | 0 |
| SPCX.US-PERP | Perpetual Stock | 0 | 0 | 0 |
| ATCOA.SE | SE Equities | 0 | 0 | 0 |
| AMD.US | US Equities | 0 | 0 | 0 |

Poarta de suport impune timestamps cauzale, age=boundary−timestamp, age între 0 și 5.000ms, lipsa paginării restante, bid/ask sincronizate în maximum 2.000ms, prețuri finite pozitive și bid≤ask. Cele patru teste noi au verificat inclusiv viitor/age negativ, neconcordanță age/timestamp, paginare necunoscută, NaN, conflicte și separarea ferestrelor. Nu a fost modificat retrospectiv niciun rezultat economic istoric.

## Dovezi și limitare operațională

Sursa: 1340ab28cc645f3a05acd75838de1618b0d18067; trigger: a3e609779c2f1dcc069e96b23797b27d63c1fe5a; run: 39278529554; worker job: 118148506560. Jurnalul nativ conține rezultatul la 2026-10-19T15:31:03Z și confirmă încărcarea artefactului 12197614203. Rezultatul și proveniența au fost criptate și recitite înaintea încărcării. SHA256 ciphertext: b087ebcae103ff4780b41da4cb6623593bd18b52de68dd9262a0c96236391ad4.

La ultima verificare, endpointurile GitHub raportează încă runul și joburile queued, deși jurnalul workerului și artefactul sunt deja disponibile. Jurnalul publisherului nu este disponibil (404), iar ref-ul de dovezi este încă ffaac1428220926509299d8cbca0f9d9fee35d3a. **Nu declarăm SUCCESS integral sau arhivare criptată durabilă în ref-ul de dovezi.** Rezultatul public din jurnal este salvat aici și în fișierul EVIDENCE, fără a pretinde că înlocuiește arhivarea detaliului criptat.

Acesta este un statut de publicare neconfirmat, nu un eșec economic și nu motiv de relansare. Următoarea continuare verifică întâi același run și publisherul, fără a dubla calculul. O eventuală remediere de transport nu va redeschide analiza sau reseta bugetele.

## Bugete și protecții

B a utilizat cele două execuții prevăzute și opt arhive M5 în prima execuție. În această continuare: zero descărcări suplimentare de arhive release; numai citirea cache-ului inclus în sursa versionată, zero cereri broker, zero identități/rezervări economice, zero outcomes, zero ordine. Limita B este atinsă și nu va fi mărită sau ocolită prin redenumire.

V2 rămâne 21 de identități taxate la outcome, 29 de observații, rezervarea C033 păstrată și contorul tehnic 22. Nu au fost restituite încercări. Plafonul 84 nu este global. Checkpointul 16 rămâne separat, pending=null și safe_stop=true; OWNER1807 și autoritatea activă nu au fost schimbate. Nu s-a deschis confirmare sau protected forward și nu s-a calificat un cBot.

## Decizia științifică și pasul următor

B se oprește finit cu QUOTE_WINDOW_GAP și HISTORICAL_COST_AUTHORITY_UNRESOLVED pentru o evaluare economică pe fereastra M5 examinată. Acesta NU este verdict asupra profitabilității unei strategii, familiei sau clase.

După clarificarea publicării, următorul pas legitim este localizarea cotațiilor și condițiilor datate în celelalte manifeste deja inventariate, prin căutare de metadate și timestampuri, nu reexecuția B. Dacă nu există, orice colectare Pepperstone read-only trebuie să aibă o întrebare informațională distinctă, un registru exact de lipsuri, ceasuri/identificatori și buget finit prospectiv. Nu presupunem că API-ul de condiții curente poate repara istoria comisioanelor/marjei.

Un viitor screening poate folosi numai costuri autentice sau limite justificate declarate prospectiv, cu necunoscutele explicite; nu poate transforma ipotezele convenabile în net realizabil. Nicio nouă identitate economică nu este admisă pe baza acestei constatări.
