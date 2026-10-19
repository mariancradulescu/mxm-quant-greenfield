# MXM — FRONTIER_SUPPORT_PREGATE_B: suport M5 măsurat

19 octombrie 2026. Programul înregistrat prospectiv la ac4c24e11c04e77be5c94fc176d02a23e9d1207a a fost executat, fără deschiderea unor rezultate economice. Nu s-au reluat C033, V4–V6 sau recepția.

## Rezultat material

- 22.571 de bare M5 autentice reutilizate pentru 25 de instrumente din 25 de clase native ale brokerului; eșantionul fix conține 29 de clase, nu doar cele șase instrumente C033.
- Fereastra examinată: 20–26 august 2026, numai primul segment istoric. Nu pretindem verificarea integrală a celor 28 de zile, a nucleului 145 sau a întregii frontiere 1.576.
- Opt arhive existente, 6.064.783 octeți criptați: verificare digest release/ciphertext/plaintext, identitate segment/shard și numărul original de rânduri. Nicio achiziție nouă Pepperstone. Acest volum este reutilizare, nu colectare nouă.
- Toate cele 25 de instrumente examinate au cel puțin o fereastră de 13 bare continue. Totalul de 20.105 ferestre suprapuse măsoară suportul pentru features; NU reprezintă semnale, tranzacții sau încercări independente.
- Volume pozitive și variabile pe toate cele 25 de instrumente examinate; niciun rând cu volum zero în subeșantionul citit. Nu este o afirmație despre toate instrumentele/perioadele.
- Patru clase rămân NEVIZITATE la limita finită: AU Equities (AGL.AU), ETFs (AAXJ.US), Forwards - Treasuries (EUBobl-F), GB Equities (III.GB). Nu sunt respinse și nu li se impută lipsă de date.

## Execuție și conservare

Run GitHub Actions: 39269194595, ambele joburi pregate și durable-pregate în SUCCESS. Sursa versionată: 7e3474365ea4d846ab17d4e4209d236d2134a1b4. Patru teste noi de suport/limite au trecut; nu s-au reluat teste de recepție. Planul de opt arhive a fost fixat înainte de executarea măsurătorilor, fără selecție după randamente sau frecvențe observate.

Dovadă durabilă: ffaac1428220926509299d8cbca0f9d9fee35d3a; director diagnostics/frontier-support-pregate-B/. Chitanța publică a fost recitită și concordă cu rezultatul nativ. Ciphertext SHA256: 8a3947db2645501c85f9601848f84c1a641f32636f61cfd68387c6efac84a21c. Rezultatul detaliat, proveniența arhivelor și referințele de catalog sunt criptate, cu readback verificat.

program-state.json este identic octet cu octet cu checkpointul 16; hash 1f8d3ed42a276ad6c28a29d9c19d406fe45971dcdf8a239c589b090feff70e83. pending=null și safe_stop=true sunt păstrate. Sursa recepționată, arhiva C033, OWNER1807 și autoritatea activă nu au fost modificate. Workerul nu a primit credențiale Pepperstone sau App; publisherul nu a primit cheia de decriptare. Nu exista o execuție de cercetare concurentă și s-a păstrat grupa comună de concurență.

## Măsurători pe eșantionul prospectiv

| Clasă | Instrument | Bare M5 verificate | Ferestre continue 13 bare | Zile observate |
|---|---|---:|---:|---:|
| AT Equities | EBS.AT | 474 | 177 | 5 |
| AU Equities | AGL.AU | Nevizitat | — | — |
| BE Equities | ABI.BE | 504 | 384 | 5 |
| CH Equities | NESN.CH | 499 | 439 | 5 |
| Commodities (Cash) | Sugar | 569 | 509 | 5 |
| Crypto Currency (Spot) | LTCUSD | 2015 | 1991 | 7 |
| Currency Index (Spot) | USDX | 1283 | 1223 | 6 |
| DE Equities | AIXAd.DE | 507 | 429 | 5 |
| DK Equities | NOVOB.DK | 475 | 415 | 5 |
| ES Equities | ITX.ES | 508 | 436 | 5 |
| ETFs | AAXJ.US | Nevizitat | — | — |
| Energies (Spot) | NatGas | 1363 | 1159 | 6 |
| FI Equities | NDA.FI | 503 | 431 | 5 |
| FR Equities | OR.FR | 509 | 449 | 5 |
| Forex (Spot) | EURJPY | 1439 | 1415 | 6 |
| Forwards - Commodities | XAUUSD-F | 1379 | 1307 | 6 |
| Forwards - Indices | JPN225-F | 1379 | 1307 | 6 |
| Forwards - Treasuries | EUBobl-F | Nevizitat | — | — |
| GB Equities | III.GB | Nevizitat | — | — |
| HK Equities | 0001.HK | 301 | 63 | 5 |
| IE Equities | RYA.IE | 508 | 436 | 5 |
| Indices (Spot) | CN50 | 1170 | 1050 | 5 |
| Metals (Spot) | XAUUSD | 1379 | 1307 | 6 |
| NO Equities | DNB.NO | 425 | 266 | 5 |
| PT Equities | EDP.PT | 508 | 436 | 5 |
| Perpetual Commodity | WTOIL-PERP | 2015 | 1991 | 7 |
| Perpetual Stock | SPCX.US-PERP | 1970 | 1752 | 7 |
| SE Equities | ATCOA.SE | 499 | 403 | 5 |
| US Equities | AMD.US | 390 | 330 | 5 |

Distribuțiile orelor UTC, golurile grilei, numărul valorilor distincte de volum și hashurile rândurilor sunt în receipt.json. Golurile observate nu certifică închiderea unei sesiuni și nu demonstrează singure date lipsă. Timpurile barelor nu devin certificate ale recepției istorice.

## Costuri și EUR200: ce știm și ce nu

Catalogul păstrat din octombrie conține toți cei 29 de identificatori selectați. Sunt păstrate avertismente de marjă față de politica de rezervă 40% pentru Sugar, USDX, XAUUSD-F, CN50 și XAUUSD; ruta FX nativă până la patru muchii era nerezolvată pentru 0001.HK, WTOIL-PERP și SPCX.US-PERP. Acestea sunt referințe istorice de catalog, nu verificare broker LIVE nouă, imposibilități permanente sau concluzii economice.

Pentru restul instrumentelor, absența unui avertisment nu certifică fezabilitatea EUR200. M5 și catalogul curent nu certifică taxele/marja la momentul istoric, spreadul realizabil, sesiunea exactă sau fill-ul. Nu au fost calculate PnL, randamente, strategii sau un nou rezultat după costuri. Portofoliul EUR200/HARD21 și cBot-ul rămân necalificate.

## Bugete și continuare

V2 rămâne separat: 21 de identități taxate la outcome, 29 de observații, o rezervare C033 păstrată și contor tehnic legacy 22. În acest program: zero identități/rezervări economice, zero outcomes, zero cereri broker, zero ordine. Nu există plafon global 84 și nu s-a creat o linie economică prin redenumire.

Limita de opt arhive este consumată. Programul nu este complet pentru toate obiectivele: suportul M5 este măsurat parțial, poarta economică NU este trecută. Nu extindem retroactiv bugetul și nu înlocuim instrumente după ce am văzut suportul. Din cele două execuții prospective, a fost folosită una.

Pasul următor în bugetul rămas este citirea catalogului și cotațiilor DEJA păstrate pentru același eșantion, fără alte descărcări shallow, pentru un registru exact de suport bid/ask, FX, sesiuni și autoritate temporală a costurilor. Registrul de lipsuri salvat nu afirmă că o informație neexaminată este definitiv indisponibilă. Numai lipsurile documentate justifică ulterior o colectare read-only nouă.

Suportul existent justifică investigarea prospectivă a mecanismelor de sesiune/sincronizare, nu încă testarea profitabilității lor. O eventuală admitere economică necesită mecanism realmente distinct de cercetările închise, suport cauzal și costuri, buget finit per familie/program, istoric de adaptivitate/multiplicitate și contabilizarea separată rezervare–outcome. Alegerea acestui eșantion a folosit metadate și istoricul deja expus: nu este confirmare independentă, eșantion statistic reprezentativ sau nou plafon al universului.
