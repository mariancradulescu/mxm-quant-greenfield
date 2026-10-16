# MXM Director — O04.2 — raport final unic

16 octombrie 2026. Repository existent: `mariancradulescu/mxm-quant-greenfield`. Raport al executantului pentru recepția auditorului independent. Înlocuiește concluziile intermediare privind cheia și preflight-ul lipsă; istoricul și eșecurile fail-closed sunt păstrate în pachet.

## Rezultat propus recepției

Exclusivitatea acceptorului este demonstrată pentru **staging sintetic**: App dedicată a creat/avansat autoritatea prin CAS; GitHub a refuzat actualizarea aceleiași referințe cu token Actions generic și integrarea Codex. Cheia nouă a fost validată, cheia veche revocată, aceeași instalare reactivată conform confirmării proprietarului.

```text
WRITER_STATE=STAGED_READY_STOP_ONLY
PRINCIPAL_ISOLATION=VERIFIED_STAGING
OWNER_ACCEPTS_NEW_CHECKPOINTS=false
CAMPAIGN_RESTART_ALLOWED=false
PRODUCTION_GO=false
```

Concluzii tehnice propuse de executant, supuse recepției independente. Nu reprezintă certificare de platformă, autorizare de producție sau reluare a campaniei. A fost acceptată **o singură versiune sintetică**, niciun checkpoint OWNER.

Autoritate staging: **refs/heads/mxm-o04-stage-authority-v1**, OID final **c6644174244cd92b8e41b17f241b8f5e545fddd9**. STOP OWNER rămâne **a830c132521bd4348454653f713e04f6107484fe**.

## Aplicație, custodie și rotație

App privată **MXM O04 Staging Acceptor 20261016**, slug `mxm-o04-staging-acceptor-20261016`, App ID **5343530**, installation **172030470**, exclusiv repository ID **1374181010**. Permisiuni efective **Contents:write**, **Metadata:read**; fără Administration, Actions:write, Workflows:write sau alte repository-uri. Integrarea Codex nu este acceptorul.

Proprietarul a generat și depus cheia nouă prin GitHub UI în **O04_ACCEPTOR_APP_PRIVATE_KEY**, exclusiv environment **mxm-o04-staging-issuer**. Nu a fost mutată într-un secret comun. Executantul nu a citit/descărcat/exportat cheia. Nu au fost introduse servicii externe sau costuri noi.

Cu instalarea suspendată, preflight-ul a autentificat **GET /app → HTTP 200**, App ID **5343530**, nume și slug exacte. Amprenta publică derivată în runner a fost comparată independent cu UI:

- Nouă, key ID **4891846**: **SHA256:if9s0/vBUMyiKrKc5p6RJoXtcI2sL6HGIWRjNhpRKpk=**.
- Veche, key ID **4891138**: **SHA256:SwoXRrvOz1/KtsJiDjEvHD9R7dSP431kk5KyuMEOaYU=**.

După validare și confirmarea explicită a proprietarului a fost șters exclusiv key ID 4891138. Readback GitHub UI: **Key pairs 1 / Client secrets 0**, numai amprenta nouă. Numai apoi a fost reactivată instalarea **172030470**, cu aceleași permisiuni și repository. Nu s-a generat altă cheie App.

Preflight-ul păstrează cheia în memorie/stdin OpenSSL, fără fișier privat. Issuer v3 folosește un fișier temporar 0600 în runner-ul dedicat, eliminat la ieșirea contextului temporar. Tokenul de instalare nu a fost exportat către alte joburi, clienți, output-uri sau artefacte. A fost revocat la sfârșit; reutilizarea sa a primit HTTP 401. Secretele brokerului au rămas neutilizate și nemodificate.

## Arhitectura de autorizare și fencing

Ruleset **25231211** activ vizează exact `refs/heads/mxm-o04-stage-authority-v1`. Restricționează creation/update; unicul bypass este **Integration 5343530 / always**. Niciun bypass pentru Actions, Codex, utilizator sau administrator generic.

Ruleset independent **25222248**, neschimbat, fără bypass, protejează `mxm-o04-*` împotriva ștergerii, non-fast-forward și istoriei neliniare. Bypass-ul App din regula creation/update nu anulează această protecție: force rollback și delete cu tokenul App au fost respinse efectiv cu **GH013**. **25222426** păstrează freeze-ul fără bypass pentru `mxm-o04-accepted-*`.

Cheia este disponibilă numai jobului reutilizabil unic al issuer-ului înghețat **639ebc99ab2237f1b68cc152537fe919900f338a**. Environment final: exact **mxm-o04-issuer-code-v3**, zero tags, fără bypass administrativ. Ruleset **25232285** blochează creation/update ale sursei, fără bypass. Joburile generice nu referențiază environment-ul sau cheia.

Înainte de emitere: verificare criptografică RS256 a OIDC, issuer/JWKS fix, audience, repository/owner/actor ID, SHA/ref, workflow și reusable workflow ref/SHA, environment, push, runner hosted, run/attempt; comparație cu metadatele GitHub și freeze-ul. Jobul este legat de fișierul reutilizabil înghețat cu un singur job `acceptor`. Nu este autorizare printr-un câmp JSON transmis de writer. **OIDC autentifică workload-ul; nu este token App.**

Tokenul App temporar a fost limitat la unicul repository și drepturile minime, verificat prin lista repository-urilor instalării și păstrat numai în proces. Issuer-ul validează epoch, lease, versiune, source, digesturi, manifest și semnături înainte de publicare. Genericii nu pot ocoli procesul prin scrierea directă a referinței: refuzurile native sunt demonstrate mai jos.

Transportul CAS Git receive-pack pe **expected_old_oid**, force-with-lease și istorie fast-forward este reutilizat neschimbat. Releases PATCH nu este autoritate. ROOT STOP este fix. Probele CAS 2/10 writeri acceptate anterior nu au fost repetate; noua probă verifică integrarea App cu acel transport.

## HEAD, ancestry, cod și modificări

HEAD remediation rămâne **6cdf76f5e7bf9c672c24a05c3054f2aa4e137a10**. Issuer v3 este nemodificat. Commiturile și datele originale rămân conservate; arborii minimali de probe nu trebuie integrați integral peste ramurile istorice.

| Componentă | Commit | Părinte / freeze |
|---|---|---|
| Issuer v3 reutilizat | 639ebc99ab2237f1b68cc152537fe919900f338a | b78f8a55… / 25232285 |
| Preflight v1 | 5aa017b9aff96dbb2d47fe5a575bbe4935f0b3b0 | issuer v3 / 25236611 |
| Preflight v2 validat | ad3fa34c306c6d8f3c521e8839e052f4439185c5 | preflight v1 / 25236786 |
| Cititor dry-run cu pinning | 0cf53e3992ab688d502dc0f146a6143075ee8b55 | preflight v2 / fără environment, contents:read |

Preflight adaugă `o042/preflight.py` și workflow-uri izolate, reutilizând verificatorul OIDC. V1 s-a oprit la omiterea bypass_actors din API-ul read-only; v2 acceptă această omisiune, fără a acorda Administration, iar lista goală este verificată separat administrativ. V2 a avut un refuz CODE_FREEZE în timpul salvării asincrone a variabilei; după readback-ul valorii efective a trecut attempt 3. Eșecurile sunt păstrate, nu mascate ca PASS.

Ordinea allowlist-ului: **issuer v3 → preflight v1 → preflight v2 → issuer v3**. Fiecare preflight avea freeze activ fără bypass înainte de acces. Mereu o ramură exactă, zero tags, fără wildcard. Nu s-a rescris secretul. La final preflight-urile nu mai au acces la environment. Variabile finale: **O04_CODE_FREEZE_RULE_ID=25232285**, **O04_CUSTODY_ACCEPTANCE_RUN=38885755596:2**.

Cititorul nou `o042/reader_gate.py` se consumă la **SHA-ul verificat 0cf53e…**. Selectează referința constantă, fixează amprenta cheii noi, verifică semnătura App, parent-OID, digestul întregii stări, ROOT STOP, sursa issuer, starea STOP-only și digesturile probelor acceptate. Rulează read-only, fără environment/cheie/token App. Taskul nu activează un consumator OWNER.

Pachetul conține sursa exactă v3, preflight v1/v2 și reader, diff-uri, metadate și receipt-uri. Niciun arbore nou nu conține workflow-uri istorice sau execută cercetare.

## Runs și rezultate

| Probă | Run / attempt / job | Rezultat |
|---|---|---|
| Preflight cheie + App | 38896722378 / 3 / 116960291698 | SUCCESS; HTTP 200 și amprentă exactă |
| Environment, ref neautorizat | 38897044344 / 1 / 116959884046 | GitHub refuză deployment înainte de steps |
| App/CAS și fencing | 38885755596 / 3 / 116964070224 | SUCCESS |
| GITHUB_TOKEN contents:write | 38885755596 / 3 / 116964999529 | SUCCESS al probei de refuz; HTTP 422 |
| GITHUB_TOKEN read-only | 38885755596 / 3 / 116965088397 | SUCCESS al probei de refuz; HTTP 403 |
| Cititor/spoof/tamper | 38898857911 / 1 / 116965852327 | SUCCESS; zero scrieri |

App a creat genesis **c5e239ae76ee1e00fcc704f403c85400730f365f**. Acceptarea sintetică după pierderea ACK a fost găsită prin readback la **93211063e157ecf04723b53ae24ba8a3d8947f1b**, fără acceptare dublă. Final: **c6644174244cd92b8e41b17f241b8f5e545fddd9**, version 1, epoch 3, lease 0, fără owner/session/pending.

| Contract negativ | Rezultat efectiv și frontieră |
|---|---|
| Generic contents:write | PATCH al unui child valid → **HTTP 422**, OID înainte/după c6644174… |
| Integrarea Codex | Child valid **3ecc07eaa7f1608fd851258de8ebc9476016400b**, updateRefs respins **UNPROCESSABLE / protected ref**, OID neschimbat. HTTP transport neexpus de connector, nu inventat |
| Read-only | PATCH cu child valid → **HTTP 403**, OID neschimbat |
| Alt principal / cheie / anonim | GET /app: identitate App greșită, RSA sintetică neînregistrată și cerere anonimă → fiecare **HTTP 401** |
| Workload/ref neautorizat | Refuz GitHub Environment înainte de execuție; SHA/job legate de OIDC și cod înghețat. Claims greșite sunt teste suplimentare ale verificatorului, nu refuzuri native inventate |
| Expirare/revocare | JWT App efectiv expirat → **HTTP 401**; token de instalare revocat și reutilizat → **HTTP 401**. Nu se pretinde așteptarea expirării naturale a tokenului de o oră |
| Writer întârziat / sesiune / epoch | Lease semnat valid expirat: deadline **1792152572**, verificare la **1792152574**, **LEASE_EXPIRED**. După noul epoch, cererea veche refuzată, OID neschimbat |
| Replay/OID vechi/duplicat/versiune | **ACCEPT_STATE**, **PENDING_STATE**, **OPERATION_REPLAY**, **VERSION** în issuer protejat; OID înainte/după în receipt, fără acceptare suplimentară |
| Rollback/force/delete | Încercări reale cu token App → GitHub **GH013**; OID final neschimbat |
| Side-branch spoofing | **mxm-o04-stage-spoof-20261016-v1** pointează la același commit semnat; gate-ul cititorului refuză **REFERENCE_NOT_AUTHORIZED**; autoritatea fixă neschimbată |
| Digest/manifest/semnătură/source | Cereri alterate refuzate în issuer-ul înghețat, singurul deținător de credential: **CONTENT_DIGEST**, **SIGNATURE**, **SOURCE_SHA**, **FENCED_WRITER**. Cititorul refuză separat tamper de digest/semnătură/identitate |
| ACK incert | **SYNTHETIC_ACCEPTED_READBACK_NO_REPLAY**, o singură versiune sintetică acceptată |

Refuzurile de integritate/protocol sunt în **frontiera de încredere a issuer-ului**, nu într-un client cu drepturi directe asupra autorității. Refuzurile actualizării referinței, force și delete sunt **native GitHub server-side**. Cititorul este dry-run, nu substituie regulile. Nu se pretinde că GitHub validează nativ payload-ul checkpointului.

Receipt-urile includ run/attempt/job, categorie principal, OID înainte/după și răspuns/decizie. Proba Codex este o operațiune API externă Actions, fără job fictiv. Nu au fost repetate CAS 2/10, inventarul celor 144 de workflow-uri sau auditul P0–P4.

## Artefacte și SHA256

| Artifact ID | Conținut | SHA256 ZIP verificat |
|---|---|---|
| 12044023758 | preflight | ea63e412b16302010caa5733a1739c44fd3514db331b3941a6d2a4dd28376fd9 |
| 12044464358 | App/custodie/revocare token | 2b68bf7f7dd107ac8a35e54db4bba56ef7f2fd2db4197ff554d54f5b6b6c06f5 |
| 12044522870 | generic writer | 53773894eb1f52fc5db09c0bd8b6e853c7db00058f44822593b2bfcf09ba88f9 |
| 12044334955 | read-only | 40d9d3b168ed00810694a84dbbbcea2f65d82f378181042ee841d915955499f4 |
| 12045091916 | reader/spoof | 97a24c0b14673c44b4698beb1e1c50bfbe150571c4702ecaf8b42e261b842520 |

Toate arhivele au fost descărcate și comparate cu digesturile GitHub; JSON-urile inspectate. SHA256SUMS din livrabil acoperă raportul, codul și dovezile. Niciun PEM privat, JWT/token brut sau valoare a secretului nu este publicat.

## Conservare și limite

STOP rămâne **a830c132521bd4348454653f713e04f6107484fe**. Rulesets **25222248** / **25222426** sunt identice integral cu baseline-ul. Release OWNER **412686323** are corp identic, SHA256 **01a6d82498c033131302b272ee4ba2f83c4e445f40585f76dfee1a91466679b9**. Sunt păstrate generația **1807**, jurnalul criptat **642889915**, canonical SHA256 **ea93f6c38768824521d4ad3e316c0cd507c837e5c089c5e3b6f63d20d79e7470**. Jurnalul nu a fost descărcat/decriptat din nou.

Politica **7689** este activă, cu lista exactă de **145** ținte neschimbată (144 istorice + fixture denial), restricțiile actors/events fără valori permise. Comparație read-only a configurației, fără reinventarierea ori relansarea writerilor. Verificare finală Actions: **zero runuri in_progress, zero queued**.

Starea sintetică păstrează câmpul conservator moștenit **principal_isolation: UNVERIFIED** al fixture-ului original; nu a fost rescris pentru a produce PASS. Modul final este STAGED_READY_STOP_ONLY. Concluzia exclusivității staging se bazează pe ACL, custodie și probele native documentate. Câmpul moștenit nu este certificat sau gate de producție. Funcția OWNER accept_checkpoint și cititorul OWNER rămân fail-closed; cititorul nou acceptă numai dry-run sintetic cu pinning.

Contents:write al App nu este branch-scoped. Autoritatea este limitată prin ruleset exact, issuer imutabil care nu exportă tokenul și cititor cu referință fixă. Administrarea rădăcină a GitHub și custodia dispozitivului proprietarului nu sunt înlocuite de aceste probe. Protecțiile nu au fost slăbite pentru PASS. Cititorul viitor trebuie fixat la SHA-ul verificat, nu la un ref mutabil ales de solicitant.

Instalarea dedicată rămâne activă în configurația staging autorizată; tokenul de instalare de test este revocat. Nicio autoritate **mxm-o04-active-*** creată, niciun checkpoint OWNER nou acceptat. Datele, secretele cTrader, OAuth/scope-urile și arhitectura Pepperstone LIVE nu au fost modificate/utilizate. Fără cercetare, colectare, backtesting economic, broker I/O, ordine, cBot, Cloud sau protected forward. Nu s-a creat repository nou.

Intervenția permisă este încheiată. **Recepția finală aparține auditorului independent.** Producția, checkpointurile OWNER reale și reluarea campaniei rămân interzise fără autorizare separată.
