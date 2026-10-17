# MXM — etapa A, raport pentru recepție independentă

**Verdict propus: A_NATIVE_INTEGRATION_VERIFIED_INSTALLATION_INCOMPLETE_NO_GO.** Codul și integrarea Git nativă sunt implementate. Două environment-uri fără credentiale sunt instalate. **Înghețarea sursei noi nu este instalată:** GitHub a cerut reconfirmare administrativă la salvarea noii reguli, apoi a afișat „Verification request timed out / We could not verify your identity”. O singură încercare, fără reluare, escaladare sau ocolire. Nu se declară etapa A integral finalizată și nici B gata de aprobare.

Mandat: mesajul OWNER „AUTORIZARE A”, după confirmarea recepției G03.2-R2 la `f1bc26280fab95b8fd083b032cb272c543aaa93b`. Proveniență conversațională OWNER; nu se fabrică un nou proces-verbal independent. Auditorului i se solicită recepția exclusiv a domeniului demonstrat de acest dosar, cu rezerva de instalare explicită.

## Implementare executabilă

Sursa finală: `5f8c9432cfa5f0c29711bd721c33a6536942b13a`, pe remediere și pe noua ramură `mxm-o04-successor-code-a-v1`. Aceasta are încă numai protecția append-only moștenită, **nu** interdicția creation/update pregătită. Nicio cheie nu este admisă pe această sursă.

| Componentă nouă | Comportament efectiv | Limită A |
|---|---|---|
| `gate.py` + workflow critic | Manifest exact, SHA sursă/politică, OWNER1807, operație și fereastră; verificatorul GET-only G03.2-R2 validează reviewerul OWNER și comentariul exact cu digestul manifestului | Run actor/commit author nu aprobă; niciun review OWNER efectuat de Director |
| `issuer.py` | Grant nativ înaintea citirii cheii; verificare public key pin, App/installation/repo/permisiuni; mint/use/revoke în același proces, fără export token; verificare ACL exactă cu principalul App înainte de Git write | Nicio cheie citită/importată/generată, niciun token App emis în A; ruta reală nu a fost executată |
| `publisher.py` | `git push --force-with-lease=<ref>:<expected>` cu părinte exact, autoritate unică, jurnal de intenții în același commit Git, generație1808 după rădăcina1807, epoch fixat, hash/integritate, policy finită și refuz la expirare | Launcherul A admite exclusiv prefixul sintetic propriu; regula25268790 blochează autoritatea activă |
| `pipeline.py` | Selector unic pentru restore/worker/handoff/economic; verifică OID, părinte Git, jurnal, digest, principal/epoch/policy; reutilizează `PreparedInput`, flags/parser și adaptorul de arhivă acceptate | Restore/handoff pregătesc input verificat; worker este transformare sintetică deterministă; economic refuză research. Nicio restaurare a DB ori execuție economică reală |
| Workflow de integrare | GITHUB_TOKEN contents-write doar în proba sintetică, checkout fără credentiale persistente; fără App, environment, OIDC sau secret real | Nu reprezintă principal App real ori writer operațional |

SQLite nu este autoritatea și nu înlocuiește CAS Git. Fiecare acceptare include intenția și generația în același obiect publicat atomic. Pierderea ACK conduce la o singură reconciliere read-only, inclusiv cu un client rece fără jurnal local; nu există resubmission automat. Conflictul/transportul nedeterminat opresc execuția. Nu există fallback Releases/side-ref sau import/execuție de module istorice cu mutații.

## Rezultat machine-side nou

[Run39004026709](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/39004026709), job117312689341, tentativa1: **SUCCESS,42 cazuri,9 pozitive și33 refuzuri**. [Rezumat](integration-summary.json), [cazuri complete](integration-cases.json), [log](integration-native-integration-job.log).

Pozitive: excluderea canarului sintetic al variabilei de cheie din mediul subprocessului Git; genesis sintetic izolat; checkpoint CAS; patru intrări ale succesorului; reconciliere rece după ACK pierdut; ultima generație finită. Negative: ținte active/staging din modul sintetic, lipsă grant OWNER nativ, grant sintetic folosit pentru mint App, principal/sursă/policy expirată, generație sărită/nepotrivită, flags neboolean, propunere/date alterate, competiție pe OID, replay, Releases/side-ref, OID conflictual, ACK digest fals/dublă acceptare, epuizare, revocare, rollback de jurnal și epoch/principal conflictuale — atât la consumator, cât și la publisher.

Refuzul rollback-ului **numai pe ținta sintetică nouă** a returnat nativ `GH013`; nu este proba422 veche. Competiția CAS a parcurs comanda Git push cu lease și readback; nu pretindem că mesajul stale a fost emis de un anumit ruleset sau că am capturat o cursă la nivel de pachet receive-pack. Atomicitatea folosește protocolul Git și părintele exact.

Referința finală a probei este `refs/heads/mxm-o04-successor-a-synthetic-39004026709-1` → `793049aeb5ee45ee47571a393b99dca3efa26d66`. Tail-ul conține intenționat stări invalide pentru controale negative și **nu este autoritate consumabilă**. Ultimul checkpoint sintetic valid și OID-urile intermediare sunt în cazuri. Nu se migrează această referință către autoritatea activă.

Artefact12089794794,3619bytes, SHA-256 **`73b1cf6fe06930ebde7e3b3785ed3c3d24b71ce046439db68c5761472bf2cfb0`**. ZIP verificat CRC și digest, păstrat integral în Git ca Base64, plus fișiere extrase. Nu depindem de retenția Actions.

Două revizii intermediare ale aceleiași integrări noi: run39003758610 la287eb6b (34cazuri), run39003978636 lafc3edfd (41cazuri), ambele SUCCESS. Revizuirea a adăugat validarea stării persistate/genesis exact1807, flags stricte și excluderea variabilei viitoarei chei din subprocess. Ultimul run este dovada sursei livrate. Nu s-au reluat O04.2, suitele recepționate de29/37/6 teste, vechea probă422 sau auditurile închise.

## Gate și configurație nativă

Environment critic **24553414129 / mxm-p0-owner-critical-v1**: required reviewer exclusiv OWNER322088485, bypass administrativ false, branch exact `mxm-o04-successor-code-a-v1`, zero tags, zero secrets/vars. Prevent-self-review false permite aceluiași OWNER să inițieze un run și să îl aprobe separat; inițierea singură nu acordă aprobare.

Environment issuer **24553648726 / mxm-p0-successor-issuer-v1**: aceeași ramură exactă, zero tags, bypass administrativ false, zero secrets/vars. Fără reviewer pe checkpoint: jobul depinde de gate-ul critic inițial. Acum nu deține niciun credential.

[Run critic39004110399](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/39004110399): manifest job117312929786 SUCCESS, gate job117312959007 **WAITING fără runner și fără pași**, review history `[]`, reviewer nativ OWNER exact. Manifest SHA-256 `867139d1459aea4a4f25006a6ebe81ed013b64492e79d2ceb8292666ff3065d9`. După capturarea dovezii, runul a fost **CANCELLED**, fără aprobare, iar issuerul nu a executat pași. Și proba preliminară39003841405 a fost închisă CANCELLED. Aceste runuri nu sunt raportate SUCCESS. Artefactul final al manifestului12089473996 are SHA-256 `7b80fbfc6f04a8c4058a62a5c14df57151a9d81580a66583efed6c765e556665`, păstrat integral.

**Limită de identitate:** API pending_deployments raportează `current_user_can_approve=true` pentru sesiunea OWNER folosită administrativ. Gate-ul separă identități GitHub și aprobarea explicită, dar nu poate separa criptografic două persoane care folosesc aceeași sesiune OWNER. Directorul nu a apelat endpointul de aprobare și nu a aprobat în UI. Înaintea B, sesiunea administrativă OWNER accesibilă Directorului trebuie retrasă din execuție; OWNER aprobă direct din propria sesiune, iar Directorul/motorul rămân pe principalul App fără Deployments-write/Administration. Nicio cheie auditor sau identitate ChatGPT substituită.

**Limită de instalare:** [regula exactă pregătită](SOURCE_AND_SYNTHETIC_SEAL_PENDING.json) nu are ID și nu este instalată. Lista nativă arată numai cele10 reguli vechi; niciuna nu este modificată. Este indispensabilă finalizarea salvării prin reconfirmarea nativă GitHub a OWNER, în cadrul autorizării A deja date. Nu este nevoie de mandat nou, slăbirea protecțiilor ori privilegiu App suplimentar.

## Izolarea App și frontiera B

App5343530 / installation172030470 / repo1374181010 rămâne în custodia staging existentă. Sursa înghețată639ebc99 fixează staging și nu exportă tokenul, dar App Contents-write este repo-wide. **Bypass-ul nou pentru acest App ar acoperi toate tokenurile sale, inclusiv emise prin custodia veche.** Nu certificăm exclusivitate activă cât timp vechea rută de mint are aceeași cheie. Soluția minimă unică propusă B: retragerea accesului vechi de emitere, custodie exclusivă a aceleiași chei existente pe noul issuer înghețat, scurgerea TTL maxim3600s a tokenurilor vechi, apoi doar bypass-ul exact App pe25268790. Nu se modifică rădăcina ori istoricul staging; schimbarea custodiei staging cere excepția OWNER explicită B. Transferul secretului nu se poate demonstra prin JSON public autoatestat; va cere metadata/readback administrativ și recepție înainte de bypass. Dacă nu se poate demonstra exclusivitatea, **STOP înainte de bypass**.

Pinul public existent a fost recalculat din cheia publică a grantului staging acceptat, fără cheie privată: SPKI SHA256 `if9s0/vBUMyiKrKc5p6RJoXtcI2sL6HGIWRjNhpRKpk=`. Codul pregătit verifică și identitatea App/installation/repo după autentificare. Dacă API omite lista bypass pentru tokenul read-only, verificarea exactă se face cu App contents-write înainte de orice scriere; dacă tot nu poate fi probată, issuerul refuză. Această cale cu credential real nu este probată în A și nu este declarată activată.

Workflow-ul critic nu există pe default `main`; UI nu oferă Run workflow. Pachetul B include adăugarea **numai a fișierului critic nou, identic byte-cu-byte**, în `main`, apoi dispatch explicit pe ramura înghețată. Nu s-a schimbat `main` în A. Conform documentației GitHub, workflow_dispatch cere fișier pe default; nu presupunem dispatch/scheduler funcțional fără această instalare.

[B_PACKAGE.json](B_PACKAGE.json) este un singur traseu condiționat, **NOT_AUTHORIZATION_READY**, nu un grant. Fixează sursa, App/environment/ref, bootstrap ABSENT→genesis1807, epoch1, generații1808–1810 și24h, scope fără research. Nu inventează un ID de regulă, recepție A ori timestamp de închidere a custodiei. Datele acestea trebuie completate din probe înainte de manifestul exact B și aprobarea nativă OWNER. Formatul de checkpoint acceptat în A rămâne exclusiv sintetic; nu se declară parser/restaurare de checkpoint economic real ori cercetare autonomă instalate. Bootstrap-ul de control nu califică datele istorice.

## Păstrare și recepție

OWNER1807 `a830c132521bd4348454653f713e04f6107484fe` și staging `c6644174244cd92b8e41b17f241b8f5e545fddd9` sunt neschimbate; active-v1 rămâne404.25268790 activă, bypass[]; toate cele10 rulesets au enforcement/conditions/rules/bypass/updated_at identice snapshotului recepționat. Comparația Git față def1bc arată numai8 fișiere noi —6Python și2workflow-uri; zero modificări ale celor144 workflow-uri istorice ori ale surselor acceptate.

**Registru163PASS/28BLOCKED neschimbat**, blob733f3378a783bdb901b0aa115ddd8e6ddfdec5c5, SHA256 `17eebd55b50bd8f4b935e2eb2532ee34ee4fd7dd6f2f2de2c9f1ef54b89b84ad`. G03.2 nu devine automat PASS. Lipsurile istorice rămân UNKNOWN/carantină, nu sunt compensate de fixture-uri și nu admit date în research.

Fără bootstrap real, autoritate activă creată, token App real nou, bypass, checkpoint real nou, migrare operațională, restart, research/colectare/backtesting economic, broker I/O, cBot, Cloud ori tranzacționare. Următoarea operațiune exactă este finalizarea **sigiliului A** după reconfirmarea nativă administrativă, apoi readback și recepție independentă. B rămâne o decizie separată ulterioară asupra pachetului completat cu dovezi reale.

Corecție de publicare: commitul documentar intermediar e6df6b5c8e6d40873a29e8a241864bfdec048f9b a inclus un fișier cu cheia **publică** App deja prezentă în staging. Cerința OWNER interzice și fișierele PEM; fișierul a fost eliminat din livrarea curentă și înlocuit exclusiv cu fingerprint/digest. Nu conținea cheie privată ori token. Istoricul Git nu a fost rescris; această corecție nu ascunde publicarea intermediară.
