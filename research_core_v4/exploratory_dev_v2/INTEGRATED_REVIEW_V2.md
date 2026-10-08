# PRIMARY145 V1 — succesor operațional V2, fără outcome-uri reale

Mandatul de intrare este auditul independent al HEAD-ului
`84af51091046d663575433dcedaba87b5af295c9`. Toate cele 26 de fișiere V1,
manifestul însuși și dependențele înghețate coincid cu publicația GitHub.
V1 rămâne istoric imuabil. Nicio lege de features, baseline, fit, response,
normalizare, score, calendar, suport, latență sau selecție nu este schimbată.
Cele 18 comparații rămân exclusiv exploratorii, fără alocare alpha.

## Modificarea minimală

gate.py închide scope-ul semnat peste toate dependențele V1 și cele patru
fișiere operaționale V2, plus CODE_BINDINGS_V2 însuși. Scope-ul exact are
75 de hash-uri. Omisiunea unei dependențe sau înlocuirea hash-ului moștenit
este refuzată chiar cu o semnătură validă. Știința este importată direct
din worker.py V1; reader.py V2 schimbă doar integrarea cu noul Permit,
validarea inventarului complet și evidența operațională.

Noul payload are schema v2 și campania
PRIMARY145_EXPLORATORY_V1_OPERATIONAL_V2_SINGLE_PASS. Scope-ul fixează
repo/branch, HEAD live și local, runtime, limite, trei căi exacte și host.
Căile sunt în HOST_LAYOUT_V2.json; căile relative, alternative și symlink-urile
sunt refuzate. Host-ul trebuie să coincidă cu hostname, device și tipurile
de filesystem semnate, iar durabilitatea trebuie aprobată independent cu
un digest de evidență. Overlay/tmpfs/ramfs/erofs sunt refuzate. Tipul unui
filesystem nu demonstrează singur durabilitatea unei mașini sau a unui cloud
runner; dovada lifecycle-ului/storage-ului rămâne obligația auditorului care
semnează host_binding, nu o presupunere a acestui cod.

O singură invocare rezervă întregul buget de 7200 secunde CPU. Linux
RLIMIT_CPU și RLIMIT_AS=8GiB sunt instalate efectiv; după lookup-ul de
metadata GitHub, socket-urile sunt dezactivate. Rezervarea, cache-urile și
raportul folosesc flush/fsync/rename și sincronizarea directorului. Un crash
păstrează seriile finalizate și motivul opririi, dar nu poate re-intra sau
reseta bugetul. Aceste apeluri nu transformă storage-ul volatil în storage
persistent; de aceea host-ul actual nu poate fi folosit pentru ARM real.

## Ruta integrală sintetică

integrated_offline.py construiește două arhive ZIP fabricate determinist,
cu cele 145 identități și aceeași împărțire 17/128. Datele au cartiere complete
de features/labels pe 84 de zile și lipsuri pe restul calendarului înghețat.
Calendarul de 366 zile, warm-up56 și toate 1240 unități de score sunt efectiv
procesate; lipsurile nu sunt comprimate și nu sunt imputate. Nicio celulă
numerică reală nu este citită.

Testul pozitiv execută semnătura Ed25519 reală pe un payload de test,
validează exact scope-ul, git HEAD/pristine tree și runtime-ul, rezervă
invocarea, verifică două ZIP-uri, parsează toate145 CSV-uri, execută derive
și evaluate V1, scrie 145 checkpoint-uri și raportul final cu toate18
comparațiile. Hash-urile cache-urilor și raportul scris sunt verificate.
Scoring-ul repetat numai pe cache-urile FABRICATE trebuie să coincidă byte-exact
după eliminarea metadatelor operaționale variabile. SHA256 al output-ului
științific determinist este păstrat în rezultatul integrat.

Nu există switch sintetic în CLI-ul de producție. Testul folosește un repo
Git izolat, propriul manifest de bytes fabricate, propria cheie temporară
și propriile căi. În acel proces de test sunt furnizate numai observații
de infrastructură sintetice pentru metadata GitHub și host-ul durabil.
Semnătura, validatorii, hash-urile, git, limitele Linux, reader-ul,
parser-ul, modelul, checkpoint-urile și output-ul nu sunt înlocuite cu mocks.
Acest test nu dovedește existența unui host durabil real și nu instalează
chei sau autorizații reale.

Testele negative verifică payload alterat fără resignare, HEAD live greșit,
hash-uri semnate greșite, căi absolute greșite, runtime greșit, dependență
omisă, override de hash moștenit, host greșit și filesystem volatil.
Un corpus cu 144 identități este refuzat; ZIP corupt și timestamp duplicat
sunt refuzate în reader/parser. O întrerupere efectivă după prima serie
păstrează exact un checkpoint și blochează a doua invocare înainte de replay.

No-lookahead este verificat pe refit-urile de la zilele56/63/70/77/84 în toate
cele șase combinații horizon/lag: 30 verificări de prefix. Perturbarea
etichetelor cu maturity>=refit nu schimbă coeficienții sau forecasts;
perturbarea unei etichete mature eligibile schimbă fit-ul, deci oracle-ul
nu este unul vacuu. Toate training rows respectă maturity<refit și
decision+245min<refit. Aceasta demonstrează ruta simulatorului, nu receipt-ul
istoric autentic, care rămâne UNKNOWN.

Prima încercare de integrare a eșuat deoarece builder-ul fixture-ului
repartiza greșit identitățile după mutarea digesturilor. ARCHIVE_SCOPE a
refuzat această inconsistență. Corecția a fixat roster-ul original înainte
de înlocuirea digesturilor fabricate; nu a schimbat reader-ul sau știința.
Log-ul și rezultatul încercării eșuate sunt păstrate separat.

## Corpus fizic și host real

outcome_blind_preflight.py verifică toate145 headers, membrii canonici și
digesturile opace. Arhivele originale existente au 36.621.686 și 254.078.601
bytes, cu SHA256 acceptate 09d999… și37a47c… . Acest control nu convertește
valori OHLCV și nu produce răspunsuri reale.

Host-ul Work actual are cgroup memory.max=8GiB, dar filesystem-ul observat
este overlay cu fsync=volatile. Calea viitoare
/srv/mxm-primary145/accepted-archives este absentă. Accesibilitatea actuală
din scratch nu certifică persistența sau accesibilitatea pe alt host.
Transferul ulterior poate folosi numai aceleași artefacte acceptate,
rematerializate ca bytes opaci și reverificate pe host-ul desemnat; nu
există broker fallback. Nu s-a făcut deployment persistent în această etapă.

Blocaje operaționale exacte: PERSISTENT_EXECUTION_HOST_NOT_BOUND și
FUTURE_ARCHIVE_MATERIALIZATION_NOT_VERIFIED. Separat, auditul independent,
cheia independentă și payload-ul semnat real lipsesc în mod intenționat.
Performanța fixture-ului și plafonul Linux verificat nu garantează durata
sau completarea pe corpusul real. Niciun real report, ARM, cheie sau
semnătură reală nu a fost creată.

## Gate pentru următorul auditor

STOP_FOR_INDEPENDENT_INTEGRATED_PREARM_AUDIT. Auditorul trebuie să verifice
HEAD-ul final, toate hash-urile, scope-ul moștenit, log-urile integrale și
providerii sintetici declarați. Înainte de ARM real trebuie desemnat și
verificat un host persistent, materializate arhivele exact acceptate în
căile înghețate și verificate outcome-blind, apoi verificat scope-ul exact
pe acel host. Numai un mandat ulterior separat poate instala cheia și
semna payload-ul exact legat de live HEAD. V1 nu se redeschide ca rută
alternativă. Confirmarea disjunctă, plata selecției și protected forward
rămân sub autoritățile anterioare, fără modificări.
