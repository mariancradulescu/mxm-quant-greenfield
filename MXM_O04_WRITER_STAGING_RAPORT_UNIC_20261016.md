# MXM O04 — raport unic de implementare și recepție staging, 16.10.2026

**Verdict: NO_GO — PRINCIPAL_ISOLATION_NO_GO.**

`WRITER_STATE=BLOCKED_STOP_ONLY`; `OWNER_ACCEPTS_NEW_CHECKPOINTS=false`;
`CAMPAIGN_RESTART_ALLOWED=false`; `PRODUCTION_GO=false`.

Nucleul sintetic a fost implementat și executat machine-side în GitHub Actions.
Nu este un acceptor exclusiv disponibil pentru activare și nu atinge
`STAGED_READY_STOP_ONLY`. Runul verde înseamnă că probele au produs rezultatele
prevăzute, inclusiv contraexemplul de securitate; nu înseamnă recepție pozitivă.
Nicio platformă sau performanță economică nu este declarată certificată.
Recepția finală aparține auditorului independent.

## 1. Mandat, bază și rezultat verificabil

Mandat: `MXM_DIRECTOR_MANDAT_UNIC_O04_WRITER_STAGING_20261016.md`, aprobat
explicit de proprietar în conversație. SHA256 al fișierului primit:
`66f9d135a2d618afaf53e26628d3d06ebb1c1b740db20cdf98b70c75b142ca6b`.
Eticheta de propunere din document nu înlocuiește aprobarea explicită ulterioară.

Repository unic: `mariancradulescu/mxm-quant-greenfield`.
HEAD-urile LIVE au fost citite înainte de primul commit, nu presupuse:

| Ref | OID de bază și stare finală relevantă |
| --- | --- |
| canonical | `9c5f9f1b7f2d73f98bb188a2651fd9a3c00df6b9`, neschimbat |
| autonomous | `3cb073e54fe3189063c2737c6337d3404b713710`, neschimbat |
| remediation, bază | `9b6e257280d35eba08209f3ca2a3bf9bad4a602e` |
| remediation, implementare testată | `7143c0158f113160da5dac1e327b5b3cd3e07cdb` |
| STOP | `a830c132521bd4348454653f713e04f6107484fe`, neschimbat |

[Commit implementare](https://github.com/mariancradulescu/mxm-quant-greenfield/commit/7143c0158f113160da5dac1e327b5b3cd3e07cdb).
Diff-ul complet este `implementation.diff` în pachet: 11 fișiere, 2666 inserări.
Publicarea acestui raport este un commit separat, numai documentație; OID-ul
publicării și readback-ul final sunt în `report-publication.json`. Acesta nu
este prezentat ca sursă suplimentar testată.

S-au adăugat un pachet separat `research_core_v4/writer_staging_o04_20261016/`,
un workflow staging și un comentariu în proba safe de deny existentă.
GitFenceLab și transportul CAS existent sunt reutilizate fără modificare.
Workflow-urile istorice, codul campaniei și codul P0–P4 nu au fost modificate.
Matricea 163 PASS / 28 BLOCKED nu a fost reauditată sau recalificată.

## 2. Matrice de recepție A–F

| Contract | Recepție tehnică efectuată | Statut |
| --- | --- | --- |
| A | Export nativ 7689, ambele rulesets, comparație exactă 144 + fixture, deny safe nou cu zero joburi | Acoperire policy verificată; acceptarea independentă rămâne auditorului |
| B | API public de acceptare închis; schemă, prototip sintetic, inventar granturi UI și două contraexemple reale de write | **NO_GO**, principal exclusiv absent |
| C | CAS real, un părinte, PENDING cu dovezi content-addressed, recuperare în proces nou | Parțial; serverul nu impune semantica acceptorului |
| D | Patru adaptoare opt-in dry-run, regresie ReadOnlyAPI, OWNER refuzat, UNKNOWN conservat | Pregătire parțială; grantul real nu poate fi validat |
| E | 2/10 writeri reali, CAS stale, force/delete, read-only, write fără rol, probe de integritate și restart | Parțial; refuzul write fără rol a **eșuat** în server |
| F | Cod, diff, raport, loguri, artefacte verificate SHA256, readback, limite și cauză exactă | Livrat cu verdict NO_GO și STOP |

Nu se declară recepția completă a întregului O04 pe baza unui subset de teste.

## 3. Contract A — policy 7689 path-by-path

Exporturi native obținute din sesiunea GitHub autentificată, fără modificarea
setărilor. ID 7689, target `actions`, enforcement `active`, bypass `[]`.
Singura condiție este `workflow_path`; nu există condiție de ramură/ref.
Domeniul este repository-ul, pentru căile țintite pe toate ref-urile, nu numai
ramura de remediere. `exclude=[]`, `allowed_actors=[]`, `allowed_events=[]`.
UI afișează ambele restricții bifate și listele goale. UI menționează excepțiile
native GitHub pentru unele servicii; acestea nu sunt reclasificate ca granturi
ale unui acceptor și nu constituie dovadă de izolare a oricărui token extern.

Inventarul fix a fost reconstituit din dovada păstrată `o04-target-proof.json`.
Fișierul rezultat are 144 linii și hashul byte-for-byte exact solicitat:
`b751e2b87cf04cbedb9d82c4f4724b60b823a6d7ed2bf94278b7b48b68416606`.
Este versionat sub numele cerut în noul pachet. Nu am schimbat setul pentru a
potrivi politica.

Normalizare: UTF-8 ASCII, case-sensitive, separator POSIX, LF și LF final.
Se refuză whitespace marginal, backslash, traversal, wildcard și cale
necanonică; nu se face case folding sau URL decoding. Comparație de mulțimi
exacte și verificare separată a duplicatelor.

Rezultat: **144/144 incluse; zero lipsuri; zero duplicate; zero ținte neașteptate**
față de setul `istorice144 ∪ safe-denial-fixture`. Exportul are 145 ținte.
Ținta suplimentară este exclusiv:
`.github/workflows/mxm-o04-policy-denial-probe-20261016.yml`.
Proba permisă cu write `.github/workflows/mxm-o04-fencing-evidence-20261016.yml`
este distinctă și nu este în deny. Noul workflow staging este separat și nu
reactivează vreo cale istorică.

Dovezi public-safe versionate: `policy-certificate.json`, `policy-path-matrix.json`
și inventarul fix. Exporturile brute rămân în secțiunea privată a pachetului
protejat livrat proprietarului, nu în repository-ul public. Certificatul public
conține hashurile lor. Exportul nu oferă identitatea/timpul configurării politicii;
timpul observației este în certificat, nu este inventat ca timp de configurare.

Proba safe nouă: [run 38876164752](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/38876164752),
`startup_failure`, **zero joburi**. Anotația UI confirmă refuzul actorului și al
evenimentului push pentru exact safe-denial-fixture. Nu a fost rerulat niciun
workflow istoric. Această probă nu este prezentată ca 144 execuții negative;
acoperirea celor 144 este demonstrată prin export și comparație path-by-path.
Captura semnificativă și textul UI sunt incluse în pachet.

Ruleset 25222248: activ, `mxm-o04-*`, deletion/non-fast-forward/linear-history,
bypass `[]`. Ruleset 25222426: activ, `mxm-o04-accepted-*`, creation/update/
deletion/non-fast-forward/linear-history, bypass `[]`. Exporturile și răspunsurile
API înainte/după sunt identice. Nu am slăbit protecții pentru a obține PASS.

## 4. Contract B — autoritate și blocajul demonstrat

UI: zero colaboratori, zero deploy keys. O singură aplicație instalată:
ChatGPT Codex Connector, instalarea 158943705. Permisiuni vizibile: read checks,
commit statuses și metadata; read/write actions, code, issues, pull requests și
workflows. Aceasta este o integrare generală existentă, nu o identitate dedicată
acceptorului. Niciun token sau secret al instalării nu a fost extras în Actions.

Actions are implicit contents/packages read, fără drept de creare/aprobare PR.
Joburile noastre declară privilegiile necesare fiecărei probe. Cele cinci secrete
existente sunt păstrate; UI arată aceleași nume și date de actualizare din 6/3
Octombrie. Niciun job nou nu face referire la ele. Nu am cerut chei sau scope-uri.

Selectorul de bypass permite roluri, aplicații, utilizatori/deploy keys; nu oferă
în acest repository un grant pentru un anumit workflow/job/SHA Actions. A permite
integrarea GitHub Actions în ansamblu nu separă jobul acceptor de alt job cu write.
Un `if`, `concurrency`, un commit author ori câmpul JSON `writer_principal` nu
pot înlocui această limită de autorizare.

**Contraexemplu server-side 1, job 116892074736:** un token efemer al altui job,
`contents:write`, fără rol de acceptor, a trimis un forward PATCH sintetic.
Răspuns **HTTP 200**, ref mutat efectiv:
`1e357882461cea1f884c9389d632922b5e70cc8e` →
`b3831d31f05a60413a2ae086c4e6dc2f9a125cd6`.
Payloadul este explicit QUARANTINED/SYNTHETIC_ONLY, nu checkpoint OWNER.
PATCH este folosit numai pentru contraexemplul de autorizare, niciodată numit CAS.

**Contraexemplu server-side 2, canal de autentificare diferit:** integrarea GitHub
existentă a putut avansa același ref sintetic la
`1ed2fab87c28362b37acb011290d13cb485e345a`, cu același tree QUARANTINED și un
singur părinte. Preflight-ul a verificat că tree-ul conține numai `state.json`,
fără workflows; niciun push de campanie nu poate rezulta din acel tree.
Readback-ul confirmă avansarea. Acest test nu folosește credențialele jobului.

Inventarul de bypass refolosește dovada statică anterioară, fără audit general
nou: `bypass-candidate-review.json` tratează toate cele **75 de căi workflow
istorice din afara setului 144 și a probelor O04**. Mandatul nu atașează lista
canonică a cohortei de 27 candidate; nu pretind identificarea exactă a acelei
cohorte. Am analizat supersetul de workflow-uri disponibil și granturile pentru
bypass-ul acceptorului, nu siguranța lor științifică. Nici absența unui flag write
static, nici tokenul implicit read nu demonstrează izolarea globală. Chiar un
singur credential valid cu write face ca aceeași lipsă ACL să fie relevantă.
Granturile PAT/SSH personale nelistate nu sunt declarate inexistente; în modelul
cerut ele trebuie oricum refuzate la ref-ul acceptorului prin control server-side.

**Dependența tehnică determinantă:** o identitate GitHub dedicată acceptorului,
selectabilă într-o regulă restrict-create/update pentru namespace-ul staging/
active, și emiterea de credențiale efemere exclusiv după verificarea identității
workload-ului aprobat (repository ID, workflow SHA/ref/job, actor, run/attempt,
gate staging). Credentialul nu poate fi disponibil altor workflow-uri/ramuri.
O aplicație GitHub dedicată cu emitent autentificat este o posibilă realizare;
această capabilitate nu există în granturile verificate. Un deny-all ar bloca și
acceptorul; un allow pentru integrarea generală nu este exclusivitate. Admin UI
este accesibil, deci cauza nu este cTrader și nici o simplă repetare a acelui 403.
Nu am creat aplicații, chei ori infrastructură nouă și nu solicit operații manuale.
Administratorul care poate schimba regulile rămâne limita declarată de guvernanță.

## 5. Contract C — arhitectură, schemă și durabilitate

`protocol.py` reutilizează `_publish` din GitFenceLab. Un singur ref sintetic
pentru fiecare run și un singur părinte per commit. Git receive-pack compară exact
`expected_old_oid` prin `--force-with-lease=REF:EXPECTED`. Non-FF/delete sunt
interzise de server. Existența unui release, asset sau side branch nu acceptă nimic.

State machine fixture: UNCLAIMED → CLAIMED → PENDING → ACCEPTED; o recuperare
prin claim în proces nou avansează epoca durabilă. Intrările invalide sunt
REJECTED fără publicare; starea neautorizată este QUARANTINED. `schema_version`,
root STOP, părinte/expectedOID, epoch/version, operation_id, principal/session,
lease/time, generation, source_SHA, manifest/ciphertext digest și emitent sunt
legate într-un record semnat Ed25519. Cheia fixture este generată efemer în
spațiul temporar, niciodată din cheile OWNER. Este o semnătură sintetică, **nu**
atestare de identitate GitHub sau grant exclusiv.

PENDING persistă bytes ai dovezilor indexați SHA256 în commit înainte de
ACCEPTED. Înregistrarea acceptată păstrează OID-ul PENDING și istoricul. Datele
sunt exclusiv sintetice; generațiile fixture 0/1 nu reprezintă generații OWNER.
Root-ul propus păstrează prin referință STOP, generația1807 și toate digesturile
cerute. Nicio ref `mxm-o04-active-*` nu a fost creată sau activată.

Observația de timp vine din headerul Date al API GitHub prin HTTPS. Aceasta nu
înseamnă că receive-pack validează expirarea lease-ului. Serverul verifică CAS și
regulile Git; semnătura, monotonia și grantul semantic necesită acceptorul de
încredere absent. API-ul public `accept_checkpoint` refuză necondiționat cu
`PRINCIPAL_ISOLATION_NO_GO`, inclusiv la încercarea de a furniza PRODUCTION_GO.

Retenție: dovezile sintetice content-addressed rămân în commiturile protejate de
no-delete/no-rollback, pe durata existenței repository-ului, sub guvernanța
administratorului. Un writer cu forward write poate încă altera starea curentă;
acesta este exact NO_GO. Artefactele/logurile Actions au retenție90 zile și nu
sunt prezentate ca depozit OWNER imuabil. Pachetul exportat conține loguri,
artefacte verificate și hashuri pentru recuperare independentă. Cheia privată
fixture a fost distrusă odată cu directorul temporar. Întreruperea și ACK incert
se rezolvă citind exact ref-ul, operation_id și digestul, fără retry orb.

Procedura de bootstrap pentru viitoarea active-v1 este documentată în DESIGN.md:
recepție independentă, identitate exclusivă + emitent, mandat separat de producție,
regulă active specifică, root legat de STOP, verificări negative și gate explicit.
Este numai documentație, nu activare sau declarare de autoritate OWNER.

## 6. Contract D — integrare opt-in dry-run

| Entrypoint original vizat | Adaptor staging executat | Rezultat |
| --- | --- | --- |
| owner.py:main | readers.dry_run(owner_checkpoint_readback) | OWNER NOT_AUTHORIZED; fixture valid cu grant UNVERIFIED |
| owner.py:child | readers.dry_run(cold_owner_readback) | idem |
| full_native_frontier runner_v1.py:restore | readers.dry_run(frontier_restore) | idem |
| FrontierStore.restore | readers.dry_run(frontier_asset_restore) | idem |

Căile complete sunt versionate în ENTRYPOINTS și în receipt-ul Actions. Adaptoarele
sunt trasee noi opt-in; nu au fost conectate la campania istorică și nu importă
modulele broker ale acesteia. Verifică ref-ul ales față de gate, rădăcina, schema,
source_SHA, epoch/version/generation, digesturile și semnătura fixture. Raportează
explicit lipsa grantului verificat; nu acceptă în producție un certificat sintetic.
Release-ul vechi, side ref, active-v1, UNKNOWN și un checkpoint nou sunt
NOT_AUTHORIZED pentru OWNER. Rezultatul științific rămâne UNKNOWN. Patru teste
read-only includ regresia ReadOnlyAPI: POST/PATCH/PUT/DELETE sunt refuzate fără
apelul transportului. Grantul real și integrarea de producție rămân BLOCKED.

## 7. Contract E — matricea probelor și limite

[Run 38876163425](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/38876163425),
HEAD7143c015, attempt1, completed/success; patru joburi:

| Job ID | Rol și rezultat |
| --- | --- |
| 116891624605 | read_only_regression, 4 teste, SUCCESS, contents read |
| 116891700215 | synthetic_protocol, probe Git reale, SUCCESS |
| 116892003390 | readonly_probe, HTTP403, ref neschimbat, SUCCESS |
| 116892074736 | write_without_acceptor_role, HTTP200, contraexemplu NO_GO observat, SUCCESS |

| Probă cerută | Observație verificabilă | Recepție |
| --- | --- | --- |
| 2 writeri | 1 câștigător, 1 refuz; OID final egal cu învingătorul | PASS strict CAS transport |
| 10 writeri | 1 câștigător, 9 refuzuri; readback server | PASS strict CAS transport |
| stale expectedOID | push real cu lease vechi refuzat, ref neschimbat | PASS CAS |
| două epoci / proces nou | PID nou, epoch2 persistat | PASS fixture durabil |
| replay / dublură | refuz precheck, OID server înainte=după | PASS client + observație, nu ACL semantic |
| semnătură/manifest/ciphertext/source/version/generation/epoch/principal schimbate | refuz și OID server înainte=după | PASS validator fixture; server semantic BLOCKED |
| expired | câmp lease invalid refuzat; expirare reală modelată în test local | Server trusted-lease BLOCKED |
| întrerupere înainte de commit | proces separat exit71; ref neschimbat | PASS fault injection la frontieră |
| ACK pierdut după commit | proces separat exit72; alt proces citește operation+digest și găsește ACCEPTED | PASS recuperare fixture |
| eșec fizic de rețea înainte/după commit | Nu a fost produsă o pană de rețea GitHub; testele sunt process cuts | NEDEMONSTRAT, nu echivalat cu network fault real |
| force / rollback | GH013 no-force; readback neschimbat | PASS server |
| delete | GH013 cannot delete; readback neschimbat | PASS server |
| overwrite checkpoint acceptat | replay/versiune refuzate în client; forward state rămâne permis unui write generic | NO_GO pentru garanția globală |
| side branch / autoritate veche | side carrier fără autoritate; cititor OWNER refuză release/active/side/new | PASS dry-run, grant real absent |
| read-only token | HTTP403, exact același OID server | PASS server |
| write fără rol | HTTP200 și OID schimbat | **FAIL control / NO_GO** |
| alt canal de autentificare | forward update permis de integrarea existentă | **FAIL control / NO_GO** |
| policy7689 cale istorică | safe denial fixture existent, actor+event refuzate, zero joburi | PASS safe probe + acoperire nativă |
| politică dispărută/alterată | Nu a fost slăbită live; fixture automat dedicat acestei condiții nu este inclus | NEDEMONSTRAT |
| grant/atestare GitHub exclusivă | Numai cheie Ed25519 sintetică; nicio identitate reală acceptor | BLOCKED de aceeași limită de autoritate |

Run/job/ref/SHA/actor/attempt sunt gardate în workflow și prin citirea metadatelor
runului real. Trigger numai push pe ramura de remediere și căile noi, actor ID
322088485, SHA=event.after, attempt1; fără workflow_dispatch. Aceste garduri nu
sunt prezentate ca protecție a ref-ului față de alți writeri.

Ref sintetic: `refs/heads/mxm-o04-stage-38876163425`.
CAS/fixture final înainte de proba write: `1e357882461cea1f884c9389d632922b5e70cc8e`.
După proba write: `b3831d31f05a60413a2ae086c4e6dc2f9a125cd6`.
După proba de autentificare alternativă: `1ed2fab87c28362b37acb011290d13cb485e345a`.
Carrier side rămâne `b3831d31f05a60413a2ae086c4e6dc2f9a125cd6`.
Starea finală sintetică este QUARANTINED, nu o autoritate OWNER.
Toate aceste tree-uri conțin numai state.json și nu pot executa campania.

## 8. Invariante și preflight înainte de modificări

`precommit-trigger-proof.json` inventariază trigger-ele efective la baza LIVE.
Numai noul workflow staging și proba safe de deny corespund fișierelor schimbate.
Celelalte două workflow-uri cu push au filtre de căi distincte; cele istorice
rămân neactivate. Proba alternativă a verificat tree-ul state-only înainte de
actualizarea ref-ului. Publicarea raportului are doar cale rădăcină, fără match
în filtrele push. Nu am declanșat manual workflow-uri și nu am schimbat setări UI.

Readback înainte/după: release412686323, body SHA256
`01a6d82498c033131302b272ee4ba2f83c4e445f40585f76dfee1a91466679b9`, identic.
Generație1807, STOP_FAIL_CLOSED; jurnal642889915 în release413440554,
canonical SHA256 `ea93f6c38768824521d4ad3e316c0cd507c837e5c089c5e3b6f63d20d79e7470`.
Registrul STOP rămâne la OIDa830, STOP_ONLY_FROZEN, writes=false, restart=false.
Nu a fost descărcat/decriptat sau modificat asset OWNER. API-ul și procedura nu
conțin operații de scriere asupra release-ului/assetului OWNER.

Toate cele397 tag OID sunt păstrate. La observația finală sunt83 ramuri,
cu două ref-uri staging sintetice noi. Nu există ref active nou. Cele cinci
secrete și arhitectura cTrader Open API/OAuth au rămas intacte; zero broker I/O,
zero colectare/cercetare/backtesting/ordine/cBot/Cloud/protected-forward.
Nicio campanie de la1807 nu a fost reluată. La citirea finală nu există Actions
in_progress; runurile acestei intervenții sunt exclusiv cele două O04 de mai sus.

## 9. Dovezi, SHA256 și stocare

Artefactele ZIP au fost descărcate și comparate byte-for-byte cu digestul GitHub:

| Artifact ID | Conținut | SHA256 ZIP |
| --- | --- | --- |
| 12035880580 | mxm-o04-stage-readonly | `sha256:ed3eef8a11e7bdae554c217276131c84e80a5658d2ceb663e1c2db2890be654a` |
| 12035601590 | mxm-o04-stage-write-bypass | `sha256:921b054081a7014f9c5751e69aa66482c0989564571bd33eaebd868c38c9e0fa` |
| 12034984008 | mxm-o04-stage-protocol | `sha256:13b58c07b2f0b9b4e93b8d2c2c8a9286c025b3e1b647712a60313f458383ea54` |

Hashuri ale dovezilor principale, căi relative în pachet:

| Dovadă | SHA256 |
| --- | --- |
| `private/policy-7689.json` | `e502281a95f54929cb1bf87d05ad37f9a580b062f1e0c69d298d23cb15424676` |
| `private/ruleset-25222248.json` | `23564b243b32c45f35eec98771a6ac2c01340ef57c5ac2ca89684495ad019017` |
| `private/ruleset-25222426.json` | `b7c8f6d6e4c53f87b4b3924eb44229d69dd81b1f6da71c116413f2bdf2063408` |
| `actions/o04-stage-protocol.json` | `d8a37a72da4fe8531e3760a87598cbf23c204b1e08dda4ce725f5316314a0126` |
| `actions/o04-stage-readonly.json` | `3257b4bb9ebe15d403dc2c99f476d6c9af2baf695850f99deabc987f7d4983ca` |
| `actions/o04-stage-write-bypass.json` | `465efd538c426c68bfc92c85e3403e4adcd6237db958704929c6bd018977f51b` |
| `alternate-auth-write-receipt.json` | `55d067b07865eadf4054fee3242a99cc74fbe8b3fc36e7469f68bda024e7be74` |
| `precommit-trigger-proof.json` | `5f32ccd4486d8eb6bc81cf191c14faeabdfeb337f9e8b8d9816cc2dce0f75b13` |
| `invariant-comparison.json` | `6a1fbb6fc525c7149680e6c2f01d2e7bf1e76cf161cf2c77bdaa887395461175` |

`SHA256SUMS.txt` din pachet acoperă fiecare fișier, inclusiv raportul, logurile,
exporturile native și captura UI. Brutele administrative sunt în `evidence/private/`
în exemplarul protejat livrat proprietarului; repository-ul conține numai
certificatul redacted și date public-safe. Niciun secret sau payload decriptat
nu este inclus. Nu s-a creat link public de partajare pentru dovezile private.

## 10. Oprire executivă

Intervenția se oprește la acest raport. API-ul de acceptare rămâne închis,
registrul OWNER rămâne STOP și nu există PRODUCTION_GO. Rezultatele sintetice
nu compensează lipsa exclusivității și nu autorizează activarea. Dependența
precisă este identitatea acceptorului cu credențial efemer legat de workload și
ACL server-side care refuză orice alt write. După rezolvarea ei trebuie repetate
recepțiile negative rămase și realizată recepția independentă; acest raport nu
le declară îndeplinite și nu cere proprietarului operațiuni GitHub manuale.
