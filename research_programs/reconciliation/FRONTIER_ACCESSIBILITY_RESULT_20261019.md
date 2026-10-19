# Frontiera curentă a contului Pepperstone — 19 octombrie 2026

## Rezultat executat și păstrat

GitHub Actions `39311067282` a încheiat SUCCESS joburile `census`
(`118260467238`) și `durable-census` (`118260673022`). Sursa protejată este
`18453ac349b527040354c15520ebfde1e8e9cb61`, pe
`mxm-o04-successor-code-frontier-accessibility-r1`; triggerul este
`34ae3ae9bdfb1beb91ce9b8dea6820f531a3d395`.
Publicarea durabilă și recitirea remote au fost confirmate la 19:27:50 UTC.

Au fost executate exclusiv două cereri de date read-only: o listă de simboluri
cu arhivate incluse și o cerere de detalii pentru cele 29 de identități fixate
anterior, câte una pe clasă. Separat au existat trei cereri de autentificare.
Autentificarea existentă a confirmat explicit VIEW și amprenta exactă a aceluiași
cont LIVE. Nu s-au folosit alt cont, alt furnizor, cheie App sau cost extern nou.

| Observație autentică actuală | Număr |
|---|---:|
| Simboluri în lista curentă returnată pentru cont | 5.329 |
| Simboluri în lista arhivată returnată | 1.707 |
| Identități din frontiera istorică regăsite cu aceeași denumire | 1.576 / 1.576 |
| Dintre acestea, marcate enabled în lista curentă | 1.575 |
| Dintre acestea, marcate disabled | 1 |
| Identificatori curenți din afara rosterului istoric de 1.576 | 3.753 |
| Detalii curente primite pentru eșantionul fixat | 29 / 29 |

Singura identitate istorică disabled aparține clasei AU Equities. Celelalte
28 de clase istorice nu au o identitate disabled în această comparație.
Nu s-a observat schimbarea denumirii vreuneia dintre cele 1.576 de identități.
Cei 3.753 nu sunt declarați listări apărute recent: sunt doar identificatori
prezenți acum care nu apar în rosterul istoric analizat. Clasificarea lor
completă, suportul istoric și valoarea economică nu sunt încă determinate.

Pentru toate cele 29 de detalii sunt prezente câmpurile native de precizie,
volum minim/pas/maxim, comision/tip/minim, swap long/short, program/fus orar
și tradingMode. Prezența câmpurilor nu este certificare a valorilor istorice,
a lichidității sau a fezabilității EUR200. Nu au fost cerute marje așteptate.

## Metodă și resurse

Programul `CURRENT_FRONTIER_ACCESSIBILITY_20261019` a fost fixat înaintea
colectării în `FRONTIER_ACCESSIBILITY_20261019.json`. Refolosește rosterul
istoric și exact eșantionul stratificat B, fără alegere după randament sau semnal.
Păstrează întreaga listă curentă returnată, nu doar nucleul 145 sau cele șase
instrumente C033. Nu interpretează 1.576, 145, 29 sau 5.329 drept plafon permanent.

Bugetul finit: o invocare nativă, o listă, cel mult o cerere cu 29 de detalii,
zero reluări automate. Bugetul este epuizat/închis după această citire.
Nu este prelungirea sau resetarea programului istoric B: întrebarea este
accesibilitatea curentă, nu redeschiderea suportului M5 ori a rezultatelor lui.
Șapte teste artificiale noi verifică separarea enabled/disabled/arhivat/absent,
schimbarea identității, duplicatele și interdicția de a promova metadatele la
dovadă economică. Ele nu sunt observații de piață sau confirmări independente.

Cereri de preț, istoric, ordine și rezultate economice: zero. Nu au fost
colectate date de preț protected-forward și nu s-a deschis confirmarea.

## Custodie și continuitate

Dovezi append-only la `ebabf46fb859bf0be6fbe1ee733356886f4c5f04`, în
`diagnostics/frontier-accessibility-20261019/receipt.json` și
`diagnostics/frontier-accessibility-20261019/checkpoint.parts.json`.
Datele brute native, cererile, răspunsurile, detaliile și îmbinarea identităților
sunt criptate cu cheia existentă. SHA256 ciphertext:
`3b656f0fe0abfdbf6b73ce9f656929adff03c3a4c3729f434d3402c37313bb51`.
Workerul a verificat decrypt/readback, iar publisherul separat, fără chei
private sau credențiale broker, a recitit ciphertextul salvat remote.

Checkpointul 16 este identic byte-for-byte, SHA256 al stării publice:
`1f8d3ed42a276ad6c28a29d9c19d406fe45971dcdf8a239c589b090feff70e83`.
OWNER1807 și autoritatea activă nu au fost modificate. Sursa recepționată,
contractele înghețate și arhivele vechi sunt păstrate. Nu s-au relansat V4–V6,
recepția, C033 sau strategiile respinse.

Contabilizarea economică rămâne: 21 identități V2 cu rezultat deschis,
29 observații, rezervarea C033 fără PnL separată, contor legacy 22,
62 unități conservator neangajate din limita V2=84. Zero identități sau
rezultate economice noi; zero restituiri și zero resetări.

## Consecințe economice și decizia următoare

Verificarea îndepărtează presupunerea că rosterul istoric reprezintă întregul
univers disponibil acum. Nu demonstrează însă 5.329 instrumente tranzacționabile
sau profitabile. Enabled nu certifică sesiunea deschisă, fills, lichiditatea,
marja, costurile totale, dimensiunea minimă ori valoarea informațională.
Lista arhivată nu este un corpus de prețuri istorice.

Următoarea lucrare justificată este îmbinarea metadatelor proaspete cu
clasificările și acoperirea deja păstrate: clasificarea identificatorilor din
afara rosterului acolo unde metadatele permit, separarea necunoscutelor și
evaluarea costurilor/minimum-ticket pentru familii cu suport autentic reutilizabil.
Orice cerere suplimentară de marjă sau metadate va necesita un program finit
prospectiv separat, justificat de această hartă; nu o colectare exhaustivă.

Nicio strategie nouă nu este încă admisă. Lipsesc în continuare dovada exactă
feature/evenimente–entry/exit–FX și autoritatea costurilor istorice sau limite
conservative justificate; metadatele din 19 octombrie nu repară costurile din
august. Codul contabil tipizat verificat nu a fost activat peste checkpointul
canonic. Migrarea forward și tratarea durabilă a expunerii ambigue rămân condiții
operaționale înaintea unei execuții economice, nu motive de a relua recepția.
Nu există verdict nou de PnL, candidat calificat, portofoliu HARD21 sau cBot.
