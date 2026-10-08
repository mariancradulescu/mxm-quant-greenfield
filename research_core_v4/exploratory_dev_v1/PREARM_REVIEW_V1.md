# PRIMARY145: prearm exploratoriu, fără execuție de piață

Mandatul autorizează freeze, implementare și fixture-uri offline. Nu există
ARM activ, workflow nou sau permisiune de deschidere a răspunsurilor reale.
Statut final: **STOP_FOR_INDEPENDENT_PREEXECUTION_AUDIT**.

## Corpus și istoric

HEAD-ul de intrare este `3a7bd64c2f4168d93f1b64e7d690552d4ee19bea`, cu
părinte direct `79a81ded1a7acc1fb0bf6adee2fa70a35b26c113`. Cele 12 fișiere
publicate la acel HEAD și toate legăturile din INPUT_BINDINGS anterior au
fost reconciliate. Citirea GitHub live a găsit zero runs in progress și
zero queued. Ultimul workflow de metodologie este eșecul istoric la
`114dd0a…`; nu este reparat sau rerulat.

Ambele arhive sunt fizic accesibile și coincid integral cu digesturile
originale. Arhiva SELECTED are 36.621.686 bytes și SHA256
`09d999a595436de73c5edbb3d4a84002dc8b8779dc94393473d43afe1c3d9259`;
arhiva DELTA are 254.078.601 bytes și SHA256
`37a47cb9ff8bc9cce50aee830c1bd286b9db359df1200d4e4b9a0ce35f8fd12e`.
Toate cele 145 de membri canonici, 17 originali și 128 delta, au fost
decomprimați doar ca bytes opaci și verificați față de series_sha256.
Niciun câmp numeric real nu a fost convertit și niciun răspuns real nu a
fost calculat. Header-ul verificat este schema CSV publicată cu șase coloane.
Ruta minimă este același cititor ZIP pentru ambele arhive, apoi numai
membrii exact desemnați de manifest. Reader-ul FX75 anterior nu este
prezentat drept reader complet PRIMARY145.

Stage6/7 NOT_SHARED_READY, certificat24 PASS, certificat28 FAIL_AR050,
261 frunze istorice, toate 1576 identități de frontieră și închiderile
anterioare rămân neschimbate. PRIMARY145 nu rerankează frontiera.
V4_ADAPTIVE_SELECTION_HISTORY_V3 documentează expunerea și selecția anterioară;
global_effective_trials rămâne NOT_IDENTIFIED_NOT_INVENTED. Nicio corecție
locală pentru 18 comparații nu plătește automat acest istoric.

## Contractul complet

DESIGN_FREEZE_V1.json este autoritatea executabilă de design. Familia este
produsul cartezian al celor trei variante CHRONOLOGY, COUPLING, COMBINED,
al orizonturilor 1/12 M5 și al lag-urilor 0/300/900 secunde. Se raportează
toate cele 18 comparații; nu există winner-first, selecție de simboluri,
praguri de succes, alocare alpha, p-value, interval de încredere sau verdict
formal. Întrebarea este îmbunătățirea de scor a algoritmilor fixați, nu
Y independent de Phi condiționat de sigma(B), avantaj economic sau profit.

B este exact harta cu zece coordonate din compact_baseline_v2. Cele două
rafinări sunt semnele produselor succesive de direcție intrabar pe ora
calendaristică completă și media semnelor intrabar ponderată cu tick_volume.
Funcția diagnostic_maps este reutilizată prin translația timestamp-urilor
în grila fixture-ului; valorile, ordinea și formulele sunt neschimbate.
Combinația adaugă ambii scalari. Cutoff-ul este t-lag; ora anterioară
incompletă nu este înlocuită cu o oră mai veche.

Comparatorul B, suportul, response normalization și prefixul de fit sunt
identice pentru cele trei variante în fiecare caz horizon/lag/refit.
Suportul comun cere ambele features, inclusiv tick_volume total pozitiv.
Această decizie conservatoare este prospectivă: lipsa cuplajului produce
abstention comun, inclusiv pentru cronologie. Legea B este comună tuturor
celor 18 cazuri; coeficienții diferă între horizon/lag pentru că problema
predictivă și disponibilitatea asumată diferă.

Calendarul brut este [2025-09-16, 2026-09-17), inclusiv weekend-uri.
Clock-ul este 00/06/12/18 UTC, warm-up 56 zile, primul score 2025-11-11;
sunt exact 1240 unități și 179800 oportunități fixe per comparație.
Fit-ul rulează pe prefixul mobil de 56 zile, cu refit la fiecare șapte
zile. Sunt excluse întreaga zi UTC de refit, deciziile fără purjarea strictă
de 245 minute și orice label care nu este strict matur înainte de refit.
Sunt reutilizate fit_prefix, predict și solve_ridge; vechiul aggregator
prequential, care comprimă calendarul lipsă, nu este folosit.

Response este log(close final al ferestrei complete viitoare / close al
barei precedente). Maturity este t+300h+lag și nu poate depăși limita
dezvoltării. Predictorii și răspunsul sunt standardizați numai din prefix,
cu ridge slopes0.5/intercept0.05 și clip[-8,8]. Scorul este diferența
erorilor pătratice /256, deci în[-1,1]. La fit sunt înlocuite cu zero
etichetele nemature înainte de a fi transmise fitter-ului și nu sunt
eligibile pentru training. În simularea retrospectivă, derive creează un
cache de răspunsuri sigilat logic; acesta nu certifică disponibilitate
istorică. La evaluare, forecast-urile sunt calculate și legate prin hash
înainte de eliberarea etichetei curente către evaluator.

Greutățile de fit sunt egale între identitățile cu prefix eligibil și apoi
între evenimentele aceleiași identități. Identitățile absente nu sunt
substituite; auditul de fit le face identificabile. La score denominator-ul
rămâne 145, iar unitățile calendaristice rămân 1240. Oportunitatea absentă
are gain0 ca abstention pentru pereche, niciodată response0 imputat.
Raportul conține gain pe identitate și clock, suport și motive de absență,
inclusiv cazuri negative și unsupported. Covarianța descriptivă a celor
18 vectori comuni de calendar păstrează agregarea identităților corelate;
145 nu este un N de observații independente. Nu se presupune independență
serială pentru o inferență formală, pentru că nu se face o astfel de inferență.

Receipt-ul original este UNKNOWN. Lag-urile sunt lumi condiționale
as-if-available. Barele arhivate nu demonstrează lipsa reviziilor sau
timestamp-uri autentice de receipt. Stabilitatea sensibilităților trebuie
raportată integral; nu se alege ulterior lag-ul favorabil.

## Gate, resurse și recuperare

entrypoint.py este singurul entrypoint de producție. Înainte de reader,
acesta cere o cheie Ed25519 provisionată independent în
/etc/mxm-independent-audit/primary145-ed25519.pub și un payload semnat
care leagă HEAD-ul de execuție de HEAD-ul GitHub live, toate hash-urile,
runtime-ul fixat, repo/branch, cele două arhive, căile și scope-ul exact.
Un JSON nesemnat sau un obiect Permit construit direct nu autorizează.
Cheia și payload-ul valid NU sunt instalate în această etapă. Modelul de
încredere presupune executorul exact auditat; nu pretinde că poate opri un
operator privilegiat care modifică interpreterul sau sistemul de fișiere.

După singura citire de metadata live, socket-urile sunt dezactivate.
RLIMIT_CPU=7200 și RLIMIT_AS=8GiB sunt instalate înainte de reader; BLAS
rulează cu un thread. Infrastructura, bibliotecile și CPU-ul influențează
reproductibilitatea; nu revendicăm bit-parity între platforme diferite.
Reader-ul refuză digesturi, dimensiuni, timestamp-uri, OHLCV sau endpoint-uri
neașteptate; nu filtrează, sortează, deduplicatează, forward-fill sau
re-achiziționează. O eroare de ZIP/decrypt/CRC este fatală, fără fallback.

Exact o invocare rezervă întregul buget CPU și consumă acest ARM la
checkpoint_directory semnat. Se păstrează atomic cache-ul derivat per
serie, SHA256 și numărătoarea seriilor/rândurilor. Un crash păstrează
checkpoint-urile pentru audit, dar aceeași autorizație nu poate re-intra,
re-citi corpusul sau reseta bugetul CPU. Recuperarea neautomată cere
rezolvarea independentă a evidenței și a bugetului; nu implică o a doua
execuție autorizată. Nu există procedură care să oprească pe scor favorabil.

## Verificare și limitări

Log-urile păstrează fiecare invocare de teste și exit code-ul aferent.
Fixture-urile includ ambele rute ZIP, fiecare horizon/lag/map, contaminare
viitoare, etichete nemature, purjare, duplicate, dimensiuni și artefacte
greșite, bare întârziate, lipsă horizon, zero activity, suport pereche,
agregare cu greutăți fixe, toate18 output-uri negative/unsupported,
semnătură alterată și refuz înainte de acces fără gate.

FULL_SYNTHETIC_REPORT_V1.json.gz păstrează raportul complet al calendarului
înghețat cu 145 identități. Datele sunt fabricate determinist din două
prototipuri, deci nu reprezintă dovadă de skill sau un stress universal al
eterogenității reale. Mai multe tipuri de lipsă/invaliditate sunt verificate
separat în testele adversariale. Hash-ul forecast-urilor nu se schimbă la
perturbarea etichetelor viitoare. No-lookahead este verificat pentru ruta
de simulator și fixture-uri; autenticitatea receipt-urilor reale nu este
demonstrată de aceste teste.

Preflight-ul dovedește accesul byte-integral și execuția offline a worker-ului
pe familia completă. Nu deschide outcome-uri reale pentru a estima durata
pe corpusul real, scorurile, missingness empirică, fezabilitatea economică
sau puterea. Limitele CPU/RAM sunt hard stops, nu garanții de finalizare.

## Următoarea graniță unică

FUTURE_SINGLE_ARM_TEMPLATE_V1.json descrie o singură campanie PRIMARY145:
maximum o trecere numerică, CPU≤2h, RAM≤8GiB, zero broker, zero protected
forward, zero orders/trading. Template-ul este PENDING și nu poate arma.
Următorul auditor trebuie să verifice live HEAD-ul publicat, fișierele și
hash-urile, contractul, log-urile, scope-ul, entrypoint-ul, cheia independentă
și payload-ul exact înainte de orice autorizare. Nicio confirmare este
presupusă sau solicitată de executor în această etapă.

Confirmarea reală rămâne separată: domeniu prospectiv și realmente disjunct,
proveniență și receipts autentice, purjarea tuturor suprapunerilor de labels
și fit, freeze anterior observațiilor, ledger complet de selecție și
alocare explicită de eroare pentru familia confirmatorie. Alternativ este
necesară o lege selectivă validă care plătește întreg istoricul expus,
nu un număr efectiv inventat sau Bonferroni18 retroactiv. Protected forward
existent nu este deschis prin această cerință. Rezultatele exploratorii nu
pot fi reclasificate ca disjoint confirmation sau formal significance.
