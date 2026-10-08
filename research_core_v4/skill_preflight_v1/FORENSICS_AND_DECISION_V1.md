# Preflight independent: skill predictiv, fără răspunsuri reale

Autoritate de intrare: `79a81ded1a7acc1fb0bf6adee2fa70a35b26c113`, părinte
`a6766b31c78cde0d6f159e1db82988a97e2371aa`. Ultima decizie acceptată este
`MAIN_V4_RESEARCH_REENTRY_METHOD_DECISION_AUTHORITY_V1.json`; pointerii mai
vechi V4_STATE sunt istorici. Niciun fișier anterior nu este modificat.

## Rezultat executabil

18/18 oracle-uri deterministe au trecut, exit 0. Prima execuție, cu primele
16 verificări, este de asemenea păstrată, exit 0. Comenzi, stdout, stderr și
hash-uri sunt în COMMAND_EVIDENCE_V1.json. Niciun generator aleatoriu și nicio
funcție `certify.verify`, `certify.run`, `run_power`, `derive` sau recuperare
de piață nu au fost executate. Citirile git istorice sunt masca Booleană deja
publicată, limitele sintetice deja publicate și certificatul deja publicat.
Nu sunt replay Stage7 sau certificare nouă. Zero OHLC reale, răspunsuri,
broker, protected forward, ordine și telemetry.

## Defecte și limitări, separat

| Cale examinată | Probă exactă | Concluzie |
|---|---|---|
| `operational_v2/masks.py:12` | `28<=days<=196` respinge 224; înlocuirea numai a 196 cu 224 reproduce byte-exact `masks_calendar224_v1.py` | Defect operațional istoric confirmat, deja corectat prin succesorul înghețat; nu defect al rezultatului recuperat |
| `resume_stage7_attempt2_v1.py` | Importă succesorul; începe de la identitatea 64; autoritatea păstrează hash-ul primelor 64 și UNKNOWN pentru coada I/O necomisă | Recuperarea nu implică reinterogarea primelor 64; nu se inventează totalul fizic |
| `operational_v1/inference.py:bootstrap_max` | Oracle scalar: mean/SEM al vectorului de reziduuri semnat coincide cu formula vectorizată | Niciun defect al studentizării demonstrat în calea inspectată |
| `cluster`, masca cumulativă | Masca autentică are 168×261, digest exact; 24 săptămâni, treimi calendaristice 8/8/8; 242 frunze susținute | Zilele absente nu comprimă calendarul; numărul de identități nu devine N independent |
| `power_stage7.py` | 783 limite Wilson independente coincid cu valorile publicate; zero frunze trec simultan cele trei cazuri ≥0,8 | Limita de putere a procedurii sintetice, nu descoperire sau nul de piață |
| `operational_v2_extended/certify.py:run` | `lead.any(1).sum()` numără încercări cu ≥1 lead; oracle de egalități verifică rangul și +1 | Controlul familiei se referă la false lead în oricare frunză, nu la numărul total de frunze false |
| AR050 | rho=0,5 zilnic, burn-in128, inovații comune/context/proprii; aceeași bancă de semne pe frunze | Dependența între frunze este păstrată contemporan; semnele săptămânale independente nu reproduc dependența dintre săptămâni |
| AR050 între săptămâni | Corr(medii a două săptămâni adiacente)=16129/139520≈0,11560 pentru AR(1) staționar rho=0,5 | Ipoteză de aproximare statistică, nu eroare de indexare; nu justifică retuning |
| Certificat28 | Raw result la `ba6557481f3c32f5d07cf841dac3d9b280f1e4f9` are hash exact; 714/16384, upper Wilson=0,05165277915188845 | FAIL_AR050 păstrat; rata punctuală 0,043579 nu satisface regula bazată pe upper≤0,05 |

Aceste verificări exclud defectele algebraice enumerate pe oracle-uri și pe
rezultatele legate prin hash; nu reprezintă demonstrația că întregul proiect
nu conține alte defecte. Oracle-ul nu poate autentifica retroactiv fiecare
operație a unei execuții stocastice. Certificat24 PASS și certificat28 FAIL,
k15, alpha=15/1024 și regula all10 rămân neschimbate. Stage6:196/140,241;
Stage7:224/168,242; ambele NOT_SHARED_READY. All-five shared_ready este doar
contractul V2, nu o condiție universală pentru skill V4.

Certificarea istorică este o anvelopă finită a DGP-urilor sintetice declarate,
cu inovații independente între trials și o bancă comună fixată; nu este o
demonstrație uniformă peste toate legile pieței sau peste orice bancă posibilă.
Wilson este interval score bazat pe cuantila normală, cu ajustarea multiplică
înghețată; algebra verificată nu îl transformă într-un interval binomial exact
distribution-free. Validitatea aproximării și puterea statistică sunt
probleme metodologice distincte de un defect de cod. FAIL-ul în chiar această
regulă finită este suficient pentru stop-ul V2, indiferent de aceste limite.

## Paritate directă și coliziuni

Sunt apelate direct `baseline` și cele patru funcții din
`prospective_exact_semantics_v3.feature`, cu ora precedentă și Q explicit
construite. A cincea lege este implementată literal din autoritatea frozen:
Var(L_j) pe doi peers cauzali fixați, excluzând own. V2 a implementat măști,
nu un runner numeric al acestei Phi; nu afirmăm paritate cu un runner inexistent.
Var=1/9 în ambele lumi, deci sqrt(Var)=1/3 în ambele. Toate cinci hărțile și
cele zece coordonate B coincid. Cele două ipoteze publicate, încă neselectate,
diferă: cronologie5/11 vs9/11; cuplaj35/39 vs12/13. Calculele Decimal ale
volatilității coincid în fixture; autoritatea matematică rămâne logaritmul real.
Aceasta demonstrează rafinare structurală locală, niciodată skill predictiv.

Auditul semnăturii folosește întregul ledger de 50 închideri și istoricul
adaptiv, plus designurile V4 cross-scale, variance-composition, online-change,
residualized-dispersion. Q de variance-composition este invariant la permutare;
cross-scale folosește semne de agregate pe alte scale; online-change folosește
detector și reset; residualized-dispersion folosește panou/OLS; mecanismele V3
închise includ entry/exit și fricțiuni. Niciuna dintre aceste specificații
închise nu este semnătura completă a comparației propuse mai jos: pereche de
algoritmi B/B+map, unitate cronologică6h, scor bounded normalizat și oportunități
fixe din cohorta145. Nu se redeschide nicio închidere. Această constatare este
despre specificații înregistrate, nu despre toate formulele posibile sau despre
o independență statistică între cercetări care reutilizează aceleași prețuri.

## Întrebarea și geometria examinată, fără experiment certificat

Întrebarea admisibilă este numai îmbunătățirea de scor a unor algoritmi complet
fixați față de același comparator cauzal B, cu suport pereche identic. Nu este
test de independență condiționată Y ⟂ Phi | sigma(B). Contraexemplul anterior
cu gain Brier4/315 sub acel nul rămâne obligatoriu. Niciun scor pozitiv nu
certifică profit sau implementare tranzacționabilă.

Pentru analiza de fezabilitate am examinat o singură geometrie, nu o serie de
optimizări: toate145 identități din PRIMARY_145_INPUT_MANIFEST, un singur pool
cu greutăți egale pe identitate; ambele hărți separat și împreună; h=1,12 M5;
sensibilități de întârziere asumate0,300,900sec. Total18 comparații; fără
simboluri sau contexte câștigătoare și fără a reutiliza automat cele261 frunze.
Aceste dimensiuni descriu numai întrebarea locală aleasă pentru calcul, nu o
pretenție că toate orizonturile economic posibile au fost epuizate.

Clock propus00/06/12/18 UTC; intervalul brut2025-09-16 inclusiv până la
2026-09-17 exclusiv, warm-up56 zile, cel mult1240 unități de scor. Horizonul
maxim1h și latența15min se maturizează înaintea următorului clock6h. Prefixul
de fit56 zile, refit săptămânal, purjare strictă245min și maturity<refit reuse
`prequential_score.fit_prefix` și `predict`: standardizare comună B, ridge
slopes0,5/intercept0,05, response standardizat și clipped[-8,8], predictions
clipped[-8,8]. Oracle-ul verifică maturity, greutățile și invarianta la
perturbarea etichetelor viitoare. Nu se execută fitter pe piață.

Y propus=ln(close al ultimei bare din [t,t+300h)/close al barei [t-300,t)),
toată fereastra viitoare completă, endpoint-uri pozitive. Features/B se
evaluează pe informația structural completă la t-lag, fără fallback. Fiecare
pereche folosește aceeași normalizare a Y și același domain; zerovolume face
cuplajul indisponibil. Nu se forward-fill, nu se completează etichete, nu se
înlocuiesc simboluri. Pentru a evita denominatoare alese prin răspuns, ținta
examinată este câștigul pe oportunități fixe: o oportunitate inaccesibilă
contribuie câștig0 pentru ambele modele, ca regulă de abstention, nu Y=0.
Nu este estimandul câștigului latent pe toate răspunsurile lipsă. Raportul
trebuie să arate separat suportul și motivele absenței, fără compresie temporală.

Aceste legi sunt o geometrie completă pentru calculul de sensibilitate, NU un
freeze inferențial/runner empiric: blocajul unic de mai jos rămâne deschis.
Nu am implementat un nou motor empiric înainte de închiderea lui.

## Dovada controlului erorii și condiția care nu poate fi presupusă

Pentru predictions pb,pa∈[-8,8], z=clip((Y-ymean)/ysd,-8,8), definim
X=((z-pb)^2-(z-pa)^2)/256. X∈[-1,1]. Diferența este afină în z;
range-ul exact se obține la z=±8, conține0, iar lățimea este |pa-pb|/8≤2.
Media cu greutăți fixe pe identități și abstention0 păstrează aceste limite.
Numărul de identități, de ticks sau de orizonturi suprapuse nu multiplică N.

Într-o filtrare comună autentic cronologică F_(k-1), designul și forecasts
trebuie să fie previzibile înaintea etichetei. F_k conține toți factorii,
identitățile și etichetele mature până la următorul clock. Fie
mu_jk=E[X_jk|F_(k-1)] și Delta_j=N^-1 sum(mu_jk). Hoeffding condiționat dă
E[exp(lambda(X_jk-mu_jk))|F_(k-1)]≤exp(lambda²/2). Prin iterație,
P(sum(X-mu)≥N*r)≤exp(-N*r²/2), inclusiv când drifturile sunt aleatoare și
serial dependente. Pentru familia fixă cu sum w_j≤1, beta_j=alpha*w_j,
LB_j=mean(X_j)-sqrt(2log(1/beta_j)/N). Nul exact la look: Delta_j≤0;
alternativă Delta_j>0. P(există j cu LB_j>Delta_j)≤alpha. Orice subset de
nulls are aceeași garanție; nu presupune independență între frunze. AR050
este cuprins numai dacă filtrarea/previzibilitatea sunt reale; un nul marginal
nu este automat nul condiționat. Un look final fix este suficient aici;
look-uri repetate ar necesita beta_jn=alpha*w_j/[n(n+1)] și slăbesc limita.
Nu este folosit wild bootstrap-ul săptămânal eșuat pentru a certifica noua lege.

Această dovadă este validă pentru experimentul prospectiv cu design previzibil.
Nu dovedește validitatea inferenței retrospective cu mecanism ales după
informații despre aceeași arhivă. Testul17 arată matematic eroarea: n=16
semne corecte independente și 2^16 vectori de scor fixați au fiecare mean0.
Alegerea retroactivă a vectorului care coincide cu semnele produce mean1
în orice lume. Radius calculat ca pentru L=1 este<1 și respinge întotdeauna;
familia completă2^16 are radius>1. Nu au fost generate observații sau încercări
noi. O family18 nouă nu plătește automat selecția istorică necunoscută.

## Precizie și putere: numai calcule analitice

La N≤1240,L=18 și alpha exemplificativ0,025 (NU alocare nouă de proiect),
radius final=0,1030130841. Pentru drift mediu≥radius+sqrt(2log5/N)=0,1539627416,
aceeași inegalitate în coada opusă dă probabilitate de detecție≥80% în cazul
max-range și al condițiilor de mai sus. Este o condiție suficientă conservatoare,
nu MDE exact și nu garanție pentru efectele pieței. Pentru radius0,01 sunt
necesare≥131586 unități, peste suportul calendaristic al arhivei; scenariul
de precizie1% este DATA_OR_POWER_LIMITED pentru această limită. Abstention și
diferențe mici între predictors pot reduce range-ul sau efectul; fără răspunsuri
nu inventăm efect realist, putere empirică sau conversie în bps. Nu selectăm
noi praguri după rezultate. Alpha exemplificativ nu rezolvă budget-ul adaptiv.

## Blocajul precis și ruta minimă

**OUTCOME_INDEPENDENT_INFERENCE_DOMAIN_UNIDENTIFIED**: nu este identificată
o lege care plătește adaptarea proiectului pe aceeași arhivă și păstrează
filtrarea prospectivă pentru noua afirmație formală. V4_ADAPTIVE_SELECTION_HISTORY_V3
documentează că panelul provine din selecție winner-first, existența răspunsurilor
V3/V4 deja deschise și `global_effective_trials=NOT_IDENTIFIED_NOT_INVENTED`.
Intervalul PRIMARY145 se suprapune dezvoltării deja expuse. A adăuga18 teste
și un alpha local nu reconstruiește numărul sau legea tuturor încercărilor.
Nu afirmăm că toate cele145 etichete au fost privite individual sau că orice
design valid este imposibil; afirmăm că independența necesară nu a fost probată.
Blocajul este pentru un freeze inferențial complet, nu pentru calculul exploratoriu.

Rezolvare concretă: un singur rezultat de dezvoltare exploratoriu pe corpusul
acceptat poate informa un freeze ulterior; raportul complet include toate18
comparații, toate eșecurile, suportul și sensibilitățile, fără verdict formal
de respingere/profit. Nu se relabel-ează ca untouched. După aceea, independent,
se desemnează un domeniu realmente disjunct și prospectiv, de după freeze,
cu toate suprapunerile de etichete purjate, acces/receipts verificabile și
alocare explicită de eroare în ledger înaintea observațiilor; sau se furnizează
o lege selectivă validă pentru întregul istoric adaptiv. Nu deschidem domeniul
protected existent și nu solicităm achiziție în acest task. Pot fi suficiente
date acceptate deja, dacă o autoritate independentă probează că sunt realmente
disjuncte și nu au fost folosite în selecție; acest lucru nu este presupus.

Available_at original rămâne UNKNOWN. Datele arhivate conțin open-time și
OHLC/counts, nu receipt/revision certificate. Lag0/300/900 sunt lumi ipotetice
as-if-available, nu reconstruiri de receipt. Rezultate sensibile la lag sunt
eșecuri de stabilitate a ipotezei de timing, nu permisiune de a alege lag favorabil.
O confirmare cauzală autentică necesită receipt verificabil, nu numai bar-close.

Primul milestone real permis DOAR după un alt mandat: un raport complet de
dezvoltare pe PRIMARY145, cel mult o citire a corpusului, CPU≤2h,RAM≤8GiB,
zero broker/protected/acquisition, toate combinațiile și absențele păstrate,
fără refreeze sau iterare pe rezultate. Archive hashes și series hashes sunt
exact cele din manifest; ruta existentă este recover_integrity_v1.py și cele
două arhive numite acolo (scriptul existent este FX-only, deci nu poate fi
prezentat ca reader deja complet pentru145). Existența manifestului nu probează
automat că bytes sunt accesibili acum; mandatul următor trebuie să probeze
integritatea/accesul înainte de ARM, fără a face broker fallback. SHA-urile
archive09d999… și37a47c… rămân cele acceptate, fără corpus alternativ.

Un score pozitiv ar constitui indiciu exploratoriu de skill al algoritmilor
fixați, condiționat de arhivă/timing/support, nu dovadă formală project-wide.
Prima dovadă formală predictivă ar cere LB>0 în confirmarea cu domeniu și
selecție realmente validate, cu raportarea întregii familii și stabilității.
Nici acest rezultat nu dovedește sigma(B), avantaj economic sau profit.

Înainte de orice răspuns real: audit independent al HEAD final, un freeze
complet și un entrypoint efectiv fail-closed care validează live HEAD, hashes,
scope și autorizarea independentă înainte de raw bytes/secret/model. Guard-ul
din taskul anterior era numai fixture și nu este suficient. Nu există workflow
nou armat în această publicație. Pasul economic ulterior cere confirmare
disjunctă, costuri autentice side-aware, margin/free-margin/survival EUR200,
frecvență/portofoliu, HARD21 pe portofoliul final și cBot cTrader Cloud.

**STOP_FOR_INDEPENDENT_SCIENTIFIC_AUDIT. Oprire înaintea oricărui răspuns real.**
