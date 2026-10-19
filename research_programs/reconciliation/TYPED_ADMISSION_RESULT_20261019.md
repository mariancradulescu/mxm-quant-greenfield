# Corecție prospectivă a contabilizării — 19 octombrie 2026

## Rezultat executat

Sursa protejată `mxm-o04-successor-code-typed-admission-r1`, commit
`1be8c56f1c132e16a5be292bf69c5747933d77e7`, conține registrul tipizat nou,
adaptoarele de deschidere a rezultatului și validarea prospectivă a manifestelor.
GitHub Actions `39302416790` a încheiat cu SUCCESS ambele joburi:
`unit` (18 teste noi, exclusiv artificiale) și `readback` (citire autentică,
fără recalcularea strategiilor). Execuția s-a încheiat la 18:26 UTC.

Dovezile sunt păstrate append-only în commitul
`e8e751007d0300f0fa5a232f3e440deb6113aee7`, la
`diagnostics/typed-admission-proof/receipt.json` și
`diagnostics/typed-admission-proof/native-unit-summary.json`.
Artefactul nativ: `12210943308`, ZIP SHA256
`0d353a113704537e8ce5eaf3087bcd442f66b74c48e74c73dc27de2c62c88f05`.

## Ce s-a corectat efectiv în codul succesor

1. Rezervarea, deschiderea rezultatului economic și înregistrarea observației
   sunt evenimente distincte, cu jurnal verificabil. Înghețarea nu mai pretinde
   automat că a fost deschis un rezultat economic.
2. Plafoanele finite sunt separate pe linie, familie și program. Programele
   împart plafonul familiei; redenumirea nu îl resetează. Limita 84 rămâne V2,
   nu plafon universal. Amprentele semantice blochează relabelarea exactă între
   linii; noutatea substanțială și dependența statistică necesită în continuare
   decizie științifică explicită, nu doar trecerea unui validator formal.
3. Deschiderea economică în adaptorul nativ este legată de existența unui
   rezultat, nu de simpla invocare. Lipsa semnalelor/cotațiilor/contului calculabil
   nu consumă o identitate cu rezultat; expunerea la gross contează inclusiv
   când costurile rămân necunoscute. Replay deschide conservator înaintea
   calculului; insuficiența ulterioară nu șterge expunerea.
4. Capacitatea de observații este verificată înaintea expunerii și la înregistrare.
   Duplicatele, modificarea jurnalului, schimbarea manifestului și încercările de
   schimbare a plafonului înregistrat sunt respinse.
5. Noile admiteri economice schema-v1 sunt închise în sursa nouă. Schema-v2
   necesită manifest înregistrat și registru tipizat. Operatorii fără integrarea
   exactă a expunerii rămân interziși pentru cercetarea tipizată. Modulul nou
   intră în digestul sursei; restaurarea recunoaște separat ambele formate.

## Reconcilierea confirmată pe checkpointul autentic

| Unitate | Valoare păstrată |
|---|---:|
| Identități V2 cu rezultat economic deschis | 21 |
| Observații economice istorice | 29 |
| Rezervare C033 fără rezultat/PnL | 1 |
| Contor brut legacy, inclusiv rezervarea | 22 |
| Limită contractuală V2 | 84 |
| Capacitate neîncărcată cu rezultat | 63 |
| Capacitate conservator neangajată | 62 |
| Restituiri/resetări | 0 |

Au fost legate semantic cele 32 de specificații istorice și C033. Registrul nou
a fost construit și restaurat numai în memorie, cu zero evenimente noi;
digestul exportului este
`a10c6754da01fcb7140f6f459e4982ad77da8790cb5adf83aa041154880e7829`.
Checkpointul 16 nu a fost migrat sau înlocuit. SHA256 al stării publice rămâne
`1f8d3ed42a276ad6c28a29d9c19d406fe45971dcdf8a239c589b090feff70e83`,
iar ciphertextul original rămâne
`eb031d18ee5b517ea1d4c3e6378cb276c4f3f46e2da810b86b8aabcc01a3ba8f`.
Nu s-au schimbat contractele înghețate, verdictul C033, bugetele programului B,
sursa recepționată, OWNER1807 sau autoritatea activă.

Prima lansare `39302317662` a fost respinsă de YAML înaintea oricărui job.
Corecția scalarului a fost versionată; workerul acceptă exclusiv această
lansare anterioară demonstrabil fără joburi, nu o a doua evaluare științifică.
Rularea reușită reprezintă o singură invocare efectivă de citire.

## Limite și următoarea admitere legitimă

Acesta este cod succesor verificat, nu activarea lui peste checkpointul canonic.
Nu există încă migrare forward criptată și verificată, program economic nou
înregistrat sau eliberare a workflow-ului economic. Durabilitatea expunerii
ambigue și sursa/admiterea succesoare trebuie legate explicit înaintea utilizării
economice; nu se va relua automat o etapă cu rezultat posibil deschis.

În această lucrare: zero identități rezervate, zero rezultate economice noi,
zero cereri Pepperstone, zero ordine, zero confirmări/protected forward.
Testele artificiale nu sunt observații de piață și nu susțin profitabilitatea.

Reconcilierea datelor anterioară rămâne valabilă, cu limitele ei: 1.576 identități
istorice și nucleul 145 nu sunt limite permanente; eșantionul fix29 nu reprezintă
întregul univers. Cele 17 momente bilaterale stricte regăsite în intervalul M5
nu certifică perechi intrare/ieșire/FX sau costuri istorice. Nu există o strategie
nouă justificată pentru test economic doar din aceste numere. Următoarea
decizie trebuie să lege exact mecanismul, suportul temporal, FX, costurile și
fezabilitatea EUR200, cu oprire la o lipsă iremediabilă și buget finit separat.
Nu se vor impune cele șase instrumente C033 și nu se va relaxa C033 retrospectiv.

Metodologia prospectivă completă a acestei corecții:
`research_programs/reconciliation/TYPED_ADMISSION_POLICY_V2.md`.
