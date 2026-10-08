# Decizie prospectivă și falsificare offline — reîntoarcere la cercetarea V4

Autoritate de pornire: `a6766b31c78cde0d6f159e1db82988a97e2371aa`.
Statut: **STOP_FOR_INDEPENDENT_SCIENTIFIC_AUDIT**. Nu există ARM, candidat
promovabil sau autorizație de deschidere a unui răspuns real.

## Rezultatul concret

Condiția `shared_ready = all5 sources ready` este specifică V2, nu o condiție
universală a descoperirii V4. Protocolul V4 existent permite familii locale și
semne diferite în contexte diferite. Certificatul24 rămâne PASS; certificatul28
rămâne FAIL_AR050. Cele261 de frunze sunt ipoteze plătite, nu261 de strategii.
Stage6/7 au măsurat suport și putere sintetică, nu predictivitate reală.

Au fost construite două exemple legale de ore M5 cu exact același baseline B,
aceleași volume ordonate, aceeași locație orară și aceleași distribuții ale
variației intrabar și locației prețului. În această construcție, ținând fixe ora
anterioară, Qminus1 și peerii, cele cinci hărți V2 coincid. Totuși:

| Hartă diagnostică | Lege exactă pe cele12 bare | Valori în cele două exemple |
|---|---|---|
| Ordine direcțională | u_j=sign(C_j−O_j); sum(u_j*u_(j+1))/11 | 5/11; 9/11 |
| Cuplaj preț–activitate | sum(v_j*u_j)/sum(v_j), nedefinit dacă totalul e0 | 35/39; 12/13 |

Acestea sunt rafinări structurale ale informației păstrate de V2. Exemplul
nu dovedește predictivitate, nu este o familie de experimente și nu certifică
noncoliziunea cu fiecare formulă din toată istoria V3. Nu alegem o sursă,
un simbol, o direcție sau un orizont după rezultate. Ambele hărți sunt numai
instrumente de falsificare, înregistrate simultan înainte de vreo piață nouă.

Prima hartă folosește ordinea pierdută de concentrarea variației și de distanța
dintre distribuțiile sortate. A doua folosește legătura dintre preț și activitate,
nu șocul de volum singur. Sunt diferite de harta V2 de acord Qminus1×H0 și de
regresia ridge B+Phi înghețată. Închiderea primului val V4 privește exact
alinierea semnelor H4/H1/M15; nu devine dovada absenței acestor rafinări.
Închiderile economice și exacte V3 rămân obligatorii; o eventuală ipoteză nouă
trebuie comparată prin întreaga sa semnătură, nu doar prin numele sursei.

## Dependența matematică rămasă

Pentru întrebarea de informație suplimentară autentică, o variantă precisă a
nulului este H0: legea lui Y condiționată de B și Phi coincide cu legea lui Y
condiționată numai de B, pe domeniul și legea de missingness înghețate.
O variantă mai îngustă poate privi numai media condițională. Aceste două nuluri
nu sunt interschimbabile și nu sunt nulul unei comparații între doi algoritmi.

Exemplul exact cu12 atomi din `OFFLINE_RESULT_V1.json` are
Phi independent Y condiționat de B(q). Un comparator B restrâns prezice7/12;
un comparator augmentat prezice9/20 sau19/28 după Phi. Câștigul populațional
Brier este **4/315 >0**, deși nu există informație suplimentară față de B.
Comparatorul oracle B are câștig0. Exemplul este o falsificare a promovării
semantice a câștigului de model la informație sigma(B), nu un rezultat de piață.

Prin urmare, nu există încă o **lege de score identificată pentru acest nul**:
trebuie declarată o clasă justificată de distribuții/nuisance și limitele erorii
de condiționare, sau acceptată explicit întrebarea mai îngustă de skill relativ
la doi algoritmi. Alegerea unui regresor mai mare, a unor bucketuri sau a unei
noi pierderi nu rezolvă singură această dependență. Nu fabricăm un candidat
complet pretinzând că estimatorul baseline este oracle.

Rezultatul Shah–Peters explică de ce nu putem cere simultan test condițional
universal, neparametric, uniform finit și putere utilă fără restricții asupra
distribuției. Teorema privește clasa sa de distribuții continue; **nu afirmăm**
că toate întrebările cu baseline-ul mixt al proiectului sunt imposibile sau că
nu există un design admisibil cu ipoteze explicite. Blockerul acestui livrabil
este lipsa acelor ipoteze și a legii complete, nu un nul de piață.

## Timp cauzal: trei afirmații separate

1. **Cauzalitate structurală:** calcul numai din intervale complet încheiate,
   fără filtre centrate, fără peer viitor și fără label nematurat în fit.
2. **Analiză condițională a arhivei:** se poate cerceta ipoteza explicită
   „valorile arhivate erau disponibile și nerevizuite la decizie”, cu întârzieri
   predeclarate și selecția tuturor analizelor plătită. Aceasta nu certifică
   recepția și nu autorizează execuția acum.
3. **Recepție istorică autentică:** UNKNOWN. Două lumi cu același OHLC,
   aceleași open-times și volume pot avea recepție la timp sau întârziată.
   Proiecția în arhivă este identică, dar baseline-ul strict acceptă numai
   prima lume. Nici close_time, nici data achiziției nu se substituie recepției.

Lipsa recepției originale nu impune repararea telemetriei și nu interzice orice
întrebare condițională despre arhivă. Telemetria rămâne parcată și carantinată.
Informația de sesiune/quote/factor/relational/curve/carry rămâne în cele6 clase
parcate; nu le reclasificăm în nul. Universul rămâne1576, cohorta structural
eligibilă1575; PRIMARY145 este development, niciodată confirmare disjunctă.
Stage7 a păstrat măști, nu un corpus raw224-zile reutilizabil pentru răspunsuri.

## Legea de inferență examinată și limitele sale exacte

Alternativa matematică utilă pentru o **întrebare de skill**, nu pentru nulul
sigma(B), este compararea unor scoruri proper bornate. Pentru o frunză j,
X_(j,n)∈[−1,1] este diferența de pierdere între două previziuni înghețate înaintea
labelului. Mu_(j,n)=E[X_(j,n)|F_(n−1)], cu F calendar comun, inclusiv informația
deja maturată despre toate instrumentele. Estimandul este media condițională
cumulativă Delta_(j,n)=sum(Mu_(j,k))/n; alternativa este Delta>0 la look-ul
predeclarat. Nu este un test al absenței informației față de întregul B.

Pentru greutăți prospective w_j>0 cu sum(w_j)≤1 și alpha nou explicit,
beta_(j,n)=alpha*w_j/[n(n+1)]. O limită inferioară simultană este

    L_(j,n) = mean(X_(j,1:n)) − sqrt(2*log(1/beta_(j,n))/n).

Derivare: Hoeffding condițional dă
E[exp(lambda*(X−Mu))|Fprev]≤exp(lambda²/2). Iterarea și Chernoff dau
P(sum(X−Mu)≥sqrt(2*n*log(1/beta)))≤beta. Suma pe toate frunzele și look-urile
este≤alpha. Pentru un singur look fix, beta_j=alpha*w_j. Nulul local la look
este Delta≤0; în orice configurație de nuluri parțiale, L>0 pentru un nul
implică o eroare de acoperire. Nu presupunem independența instrumentelor,
independența blocurilor sau semne săptămânale iid. Filtrarea, limitele scorului
și predictibilitatea trebuie însă să fie reale și verificabile.

Scorurile orizonturilor suprapuse nu se numără ca observații independente.
Un update complet de calendar poate agrega vectorul sincronizat la maturarea
ultimului label; regulile de agregare și de fit trebuie înghețate. Dacă forecasturile
sunt emise în interiorul blocului, estimandul este cel condiționat de filtrarea
blocului, nu automat suma utilităților condiționate la fiecare emitere.
Un protocol adaptat după rezultate istorice nu devine predictibil doar fiindcă
un backtest sortează cronologic rândurile. Corpul development reutilizat oferă
cel mult un rezultat exploratoriu; confirmarea și orice afirmație formală
ulterioară cer dovezi disjuncte și freeze înainte de observare.

Un produs simplu de factori(1+lambda*X) cere nul condițional potrivit. Lanțul
exact±1 cu probabilitate3/4 de păstrare a semnului are autocorelație1/2 și
medii marginale0; totuși produsul cu lambda1/2 are E[E_2]=**9/8>1**.
Aceasta falsifică importarea unui e-process sub simpla medie marginală0.
AR050 este un martor structural independent, nu o țintă de recalibrare V2.

Missingness poate schimba nulul: exemplul±1 cu răspuns observat numai la+1
transformă media completă0 în media observată1. Nicio imputare și niciun
denominator ales după răspuns nu sunt acceptate ca păstrare a estimandului.
Trebuie înghețate scorul, eligibilitatea, ponderile și ținta de utilitate pe
domeniul observabil; no-data nu este null și un label lipsă nu este zero.

Acesta este un component matematic complet, nu un experiment complet.
Scorul proper, predictorii, familia, calendarul și alpha nou nu sunt alese prin
exemplul diagnostic. Nu am schimbat k15, alpha V2 sau regula all10. Limitele
calculate pentru224 de observații și261 de ipoteze sunt numai ilustrații de
precizie în unități de score; nu sunt putere80%, MDE economic sau durată aleasă.
Nu există justificare pentru a lansa încă o campanie sintetică generală aici.

## Selecție, suport, stabilitate și oprire

Orice viitoare familie completă trebuie să plătească toate mecanismele,
contextele, cohortele, orizonturile, orientările, specificațiile de fit,
sensibilitățile de lag și criteriile folosite la alegerea unui lead. Numărul261
este istorie adaptivă V2, nu mărimea automată a familiei noi și nici un contor
de strategii independente. Nu există penalizare globală inventată dintr-un
număr efectiv de trials necunoscut. Istoria surselor rămâne logată; fiecare
survivor intră în confirmare disjunctă înghețată, cu control asupra întregii
familii selectate și a încercărilor de confirmare.

Pentru comparația de skill, legea de mai sus plătește look-uri și nuluri
parțiale; suportul și stabilitatea sunt gate-uri restrictive suplimentare,
nu schimbări de estimand după rezultat. Numărul minim de evenimente,
cohort breadth/concentration, segmentele temporale, toleranța de precizie,
alternativa relevantă și stopping rule trebuie fixate din mecanism înainte de
date. **Rămân neidentificate aici**, deci nu emitem o specificație experimentală
executabilă. Faptul că formula este validă nu certifică puterea sau baseline-ul.
Un gate all-five și un gate universal de cost/bps nu sunt prerechizite locale.

## Primul rezultat real și limita de autorizare

Cel mai apropiat milestone justificabil, după rezolvarea explicită a întrebării
de score, este **un singur rezultat complet de development pentru familia
înghețată**, pe un corpus M5 deja acceptat: toate frunzele, suportul comun,
diferențele de previziune, incertitudinea și stabilitatea, inclusiv eșecurile.
Acest rezultat ar arăta skill în sensul exact declarat; singur nu dovedește
informație sigma(B), profit sau disponibilitate istorică autentică.
Pentru informație sigma(B), milestone-ul trebuie să includă întâi identificarea
nuisance/conditional-null și limitele erorii sale; nu putem sărim acel pas.

Bugetul propus pentru următoarea autorizare de IMPLEMENTARE/PREFLIGHT:
un design complet, o singură înghețare înainte de fixture, un proces determinist,
≤1CPU-oră,≤4GiB RAM, zero broker, zero corpus numeric, zero Monte Carlo.
Nu este un buget de empiric mascat. Pentru eventualul prim development real,
plafonul propus este un singur pass asupra unui corpus acceptat ales prin
proveniență,≤2CPU-ore,≤8GiB RAM, zero noi requests; fezabilitatea exactă trebuie
verificată din schema/manifeste înainte de ARM, nu promisă acum. O depășire
oprește, fără micșorare a familiei după rezultat. Niciun corpus nu e selectat aici.

Următoarea autorizare separată trebuie să lege HEAD-ul publicat de hash-ul
deciziei și de semnătura completă a noului design. Pentru response, trebuie în
plus un allow-scope independent și un guard fail-closed la entrypointul efectiv
înainte de date, secret sau model. Absența/mismatch oprește. Fixture-ul de guard
din acest livrabil **nu este instalat pe workflow-uri legacy**; nu pretindem
acoperire operațională. Nu avem ARM și nu există autorizare automată de continuare.

Economicul rămâne după informație și confirmare: bid/ask datate, spread,
comision, conversie, slippage, volum minim/pas, marjă/free margin EUR200,
frecvență, dependență și supraviețuire. Costurile necunoscute nu sunt0. HARD21
se aplică portofoliului final; cBot-ul final este C#/.NET cTrader Cloud.
Aceste cerințe nu sunt un motiv de a bloca orice descoperire condițională locală.

## Dovezi și referințe

`INPUT_BINDINGS_V1.json` leagă autoritățile păstrate; `OFFLINE_RESULT_V1.json`
conține12/12 verificări, patru presupuneri falsificate și zero market ingress.
Codul folosește baseline-ul existent; nu reconstruiește infrastructura.
Workflow-urile Stage7 și certificare28 au fost citite live, fără dispatch/rerun;
jobul AR050 a încheiat cu succes operațional, dar verdict științific FAIL.

- Shah & Peters, *The Hardness of Conditional Independence Testing and the
  Generalised Covariance Measure*, Annals of Statistics2020, versiunev6:
  https://arxiv.org/abs/1804.07203v6 . Restricțiile teoremei nu sunt ignorate.
- Choe & Ramdas, *Comparing Sequential Forecasters*, versiunev6:
  https://arxiv.org/abs/2110.00115v6 . Comparația de skill are țintă proprie;
  nu este test universal de informație condițională. Limita Hoeffding simplă
  din acest livrabil este derivată explicit, nu o implementare a tuturor
  metodelor adaptive la varianță din articol.

**Oprire:** hărți structurale noi identificate; testul pentru informație
condițională autentică și experimentul complet rămân neidentificate. Nu afirmăm
inexistența tuturor designurilor admisibile. Nu emitem un candidat incomplet și
nu deschidem vreun răspuns real.
