# MXM — registru consolidat de remediere integrată P0

Data: 19 octombrie 2026. Repository unic: `mariancradulescu/mxm-quant-greenfield`.

**Verdict: BLOCKED. END_TO_END_OPERATIONAL_ACCEPTED nu este declarat. Cercetarea economică rămâne oprită.** Reparațiile și probele de mai jos sunt efective; protecția ramurilor de orchestrare rămâne o dependență reală a recepției integrale. Acest registru înlocuiește raportarea fragmentată a remedierii P0; nu redeschide studiile istorice.

Sursa auditată: `1be8c56f1c132e16a5be292bf69c5747933d77e7`. Implementare integrată R1: `541bfe0e7d1eea060aa38d9e1e46a6639b7db13b`. Corecția generală R2: `eab050084982916ad0c67798b38b947bac66b2b2`, module SHA256 `c85a62a4f13f6787f11de7a2f35ad4d812569beaee8fbb7e34c8e5efe6e76f05`. Observator sigilat v3: `49ee16f38183b885699d2f3d7977ea8cbdb4ee0e`. Admiterea R2 înghețată: `6815d715d783f66a8b7968438f15e379775f5c50`.

Registrul JSON alăturat, `P0_INTEGRATED_ACCEPTANCE.json`, conține cauza, fișierele, commitul, probele pozitive/negative, joburile și limitele pentru fiecare defect. Identificatorii P0 de mai jos sunt aceleași în ambele reprezentări.

| Defect | Reparație și impact | Stare |
|---|---|---|
| P0-01: Checkpoint16 source excluded from migration | Exact b430/source/cipher/public/private provenance; immutable original, forward typed successor | CLOSED |
| P0-02: TypedTrialBook read as used/limits | Schema-aware accounting from baseline/events/view; legacy counter retained as snapshot | CLOSED |
| P0-03: Typed programme claim reads new_V2_identities | identity_budget validates v1/v2 field names, integral finite caps, rejects ambiguity | CLOSED |
| P0-04: Publisher public contract remains legacy V2 | Public typed accounting and separate reservation/outcome/observation/wire units; original report preserved | CLOSED |
| P0-05: Executed source disagrees with protected SOURCE_BRANCH | New versioned protected refs, exact checked-outSHA=declaredSHA=protectedHEAD, admission module and workflow hashes | CLOSED |
| P0-06: Invalid manifest could publish durable intent before complete validation | Full restore, DAG/operator/policy/candidate validation before encrypted preflight certificate and keyless claim; fence before worker | CLOSED |
| P0-07: No durable encrypted legacy-to-typed migration | Forward-only successor path, typed book persisted inside encrypted checkpoints, independent cold process | CLOSED |
| P0-08: Lost push ACK and writer concurrency | Single leased atomic push; ACK reconciliation checks exact remote commit and every byte, never second push | CLOSED |
| P0-09: SUCCESS could hide skipped required jobs or nondurable worker output | Native toJSON(needs) for same-run edges; exact terminal jobs and remote receipt/cipher for observer | CLOSED |
| P0-10: Recovery displaced a pending native continuation | Shared group retains max queue, cancel-in-progress false; finite idempotent issuance | CLOSED |
| P0-11: Native data/corpus and shared catalogue missing in general typed driver | Bind preserved corpus and prior quote receipts, lazy authenticated GET collector under programme budget; preserve shared cache and remaining resource count | CLOSED |
| P0-12: Cosmetic rationale allowed another causal identity | Prospective version2 index excluding rationale from complete33 verified frozen specs; preserve original baseline/hash/history | CLOSED |
| P0-13: New programme after closed typed checkpoint could lose recovery routing or finite origin | Per-admission origin and nonexposure recovery_continuation marker; preserve predecessor cipher, clear marker on publication | CLOSED |
| P0-14: Default and execution branch/workflow control plane unprotected | Read-only verified; exact proposed ruleset prepared, not applied; added economic gate requiring real protection and accepted source | BLOCKED |
| P0-15: Cron interval interpreted as autonomous liveness guarantee | Native durable handoff plus workflow_run and schedule observer; explicitly best-effort no15m SLA | SCIENTIFIC_UNKNOWN |

## Lanțul demonstrat efectiv

R1 a folosit laboratorul, criptarea și custodia existente. A decriptat checkpointul original 16, a verificat proveniența reală `b430a303...`, a derivat exact registrul tipizat acceptat, a validat integral programul înainte de intenție și a publicat un succesor separat. `program-state.json` original și arhivele lui nu au fost înlocuite.

| Probă nativă | Workflow / job | Rezultat și dovadă |
|---|---|---|
| Crash nou, înainte de fence | [39318418345](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/39318418345), claim 118286132802, recovery 118286352421 | FAILURE intenționat; fence/worker SKIPPED; recuperare SUCCESS la `5f38e60f7a95c518eb57e96d3bf5ae0e2439db1b`; zero expunere și zero restituiri |
| Continuare machine-side R1 | [39318690151](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/39318690151), [39319204335](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/39319204335), [39319648613](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/39319648613) | Trei succesori workflow_dispatch emiși nativ din jurnalul durabil, fără porniri conversaționale |
| Publicare criptată și cold restart 19 | Run 39319648613, cold-readback 118291490736 | SUCCESS; recitire remote și decriptare independentă la `3c7cfff423dbbf8f1367c80aa261efdacff91486` |
| ACK incert, token, checkpoint incomplet, writer concurent | Run 39319648613, fault-probes 118291670602 | ACK pierdut injectat după push, reconciliat exact fără al doilea push; GET cu token fixture neautorizat respins 401; parte reală trunchiată respinsă; doi writeri reali, exact unul acceptat; dovadă `32f4ef9dbfd7dd694628319623f6c1105ca1e837` |
| Guard recuperare sigilat v3 | [39322270965](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/39322270965), 118299047143 | SUCCESS; 8 teste afectate; checkpoint închis observat fără dispatch nou |
| Preflight R2 autentic | [39322312307](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/39322312307), 118299244155 | SUCCESS; 37 teste afectate; decriptare reală 19; verificare a tuturor celor 33 de specificații păstrate și upgrade prospectiv al indexului cauzal |
| Crash R2 după predecessor închis | Run 39322312307, claim 118299562543, recovery 118299804590, handoff 118299973512 | FAILURE intenționat în claim; recuperare SUCCESS la `d72f7a37445c20e19bf0b8fece53b2a085db93ad`; continuare nativă emisă la `f420697b50f2134a9ee3760106c3f7a5fc7c27a1` către run 39322587530 |
| Rezultat final R2 | [39322587530](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/39322587530), publisher 118301019568, cold 118301402224 | SUCCESS; checkpoint20 la `9ae2d912638923297fec36504ef93bd0db383dfe`, readback/decriptare rece SUCCESS; markerul de recuperare consumat; pending=null, safe_stop=true |

Manifestul R1 permitea exact trei noduri tehnice artificiale, 0 identități economice, 0 outcomes, 0 cereri broker. R2 permite exact un nod tehnic nou și o singură probă de crash înainte de fence după predecessorul închis 19. Nu reexecută cele trei noduri R1. Fixturile unitare sunt artificiale și izolate; nu sunt observații de piață, identități economice canonice sau dovezi de profitabilitate.

Checkpoint20: ciphertext `0c94708365f296a91404d5bc770981fe0aab7432980e74cb867a64626bf66eca`, private SHA256 `01227d7a7715a89bc1bfcf6fac183fbaec3b941f8c61281fb3c0e4f01f232fa6`. Contabilitate persistentă: versiune index cauzal2, 4 evenimente administrative totale, zero evenimente economice noi.

Checkpoint 19: ciphertext `cb14705c8456668c273f3c19a55bde40839e5be13c92cb43ad36b5cd61dc71b5`, private SHA256 `47c34e6307d247e03c95f2727112bcbbaee7e40d6a07f104f20b16e622be8102`. Succesorul persistent păstrează baseline-ul legacy; rezervarea C033 nu a fost restituită. Șase controale negative suplimentare de proveniență au trecut local pe codul R2; sursa lor este păstrată în `verification/P0_TRANSITION_NEGATIVES.py`, fără pretenția că sunt joburi Actions.

## Siguranță și limite operaționale

Validarea completă și certificatul criptat preced intenția durabilă. Fence-ul durabil preced workerul. Un crash demonstrat înainte de fence poate elibera doar intenția tehnică, păstrând istoricul și rutarea către aceeași admitere. Un crash după fence sau o expunere ambiguă oprește reluarea automată. Eșecul autentificării nu autorizează folosirea altei identități sau a altui token.

Publisherul keyless face un singur push cu lease și verifică commitul și octeții remote dacă ACK-ul este incert. CAS exclude writerul concurent. Readback-ul verifică ordinea, mărimile, hashurile și autenticitatea criptografică. Jurnalul de emitere se salvează înainte de workflow_dispatch; ACK-ul POST incert nu produce retry orb. Dacă platforma nu furnizează dovada unei porniri, sistemul poate rămâne în HOLD, în loc să garanteze o continuare pe care nu o poate demonstra.

Un SUCCESS de workflow nu înlocuiește concluziile joburilor. Sunt distinse joburile obligatorii, SKIPPED legitime pe ramura negativă și SKIPPED terminale. Observatorul verifică identitatea exactă a predecessorului, starea terminală, rezultatele joburilor și publicarea remote, nu numai verdictul agregat. Runul observator 39318702258 rămâne CANCELLED în istoric. Coada observatorului a fost remediată cu `queue:max`, păstrând aceeași grupă de concurență și `cancel-in-progress:false`.

Cronul vechi declara 7,22,37,52. API-ul a expus pe 19 octombrie numai două execuții schedule, 39236262889 la 10:16:25Z și 39290742457 la 17:02:44Z. Cauza exactă a absențelor nu este demonstrată. Cronul nou declară 11,26,41,56; nu este o garanție de livrare la 15 minute. Handoff-ul nativ efectiv, workflow_run și observatorul programat sunt mecanisme complementare. Documentație primară: [schedule](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), [concurrency și queue](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).

## Blocaj real al recepției

LIVE: `main.protected=false`, `mxm-remediation-p0-p4-20261015-v1.protected=false`. Sursa R2 și observatorul sunt sub regula append-only 25222248, fără bypass, iar admission impune egalitatea sursei executate cu HEAD-ul protejat. Această protecție nu acoperă automat orchestrarea din main/exec.

Conectorul raportează rol administrativ la citire, dar inventarul instrumentelor nu expune scriere administrativă pentru rulesets/protection. Endpointul de citire Actions permissions este refuzat de instrument cu 400 URL not allowed; nu revendic un 403 GitHub inexistent. Issuerul App existent cere și verifică numai contents:write/metadata; cheia lui nu a fost refolosită pentru un token mai larg. Mandatul OWNER există; lipsește capabilitatea apelabilă necesară aplicării legitime. Nu se cere OWNER să opereze GitHub.

`P0_CONTROL_PLANE_PROTECTION_PROPOSAL.json` conține cererea exactă pregătită și verificările de readback. Este **NEAPLICATĂ**, fără bypass, fără slăbirea protecțiilor existente și fără modificarea OWNER1807. Nu se publică o acceptare falsă pentru a trece de acest blocaj. Vechiul workflow economic păstrează `if: ${{ false }}`. În plus, driverul R2 refuză DEVELOPMENT fără o acceptare integrată a aceleiași surse și protecție LIVE pentru ambele ramuri.

## Contabilitate și cercetare

V2: limita lane-ului 84; 21 identități taxate la deschiderea outcome; 1 hold C033 fără PnL; 22 used legacy păstrat; 29 observații istorice; 62 capacitate negrevată; 0 restituiri/resetări. Nu există plafon universal 84 și nu se creează bugete prin redenumire. R2 exclude prospectiv justificarea narativă din amprenta identității cauzale, păstrând indexul/baseline-ul istoric și controlând coliziunile conservator. Evenimentele administrative ale migrării nu sunt rezultate economice.

[Reconcilierea științifică deja închisă](SCIENTIFIC_RECONCILIATION.md) rămâne autoritatea pentru cele 12 identități fără outcome, cei trei supraviețuitori de screening, specificațiile invalidate, C025 DATA_INSUFFICIENT și diagnosticul C033. Nimic nu a fost retestat economic. C033 rămâne NO_ELIGIBLE_EVENTS: suport 240/240, volum autentic variabil/nenul, niciun prag 2× atins la ceasurile înghețate; această regulă restrânsă nu închide familia sau universul.

Frontiera păstrată are 1.576 de identități istorice, 29 clase și nucleul expus 145. Censusul autentic anterior a găsit 5.329 identități curente, 1.707 arhivate; 1.576 potriviri istorice de nume, 1.575 enabled și una disabled. Cele 3.753 de identități din afara rosterului nu sunt automat listări noi sau oportunități. Aceste rezultate și metadatele a 29 de instrumente sunt deja durabile; nu s-a repetat colectarea pentru P0.

După închiderea tehnică este justificată mai întâi analiza nonoutcome stratificată a ticketului minim, costurilor/sesiunilor și fezabilității EUR200 din datele păstrate. Programul B anterior are bugetul său consumat și nu se relansează. Un program distinct trebuie să arate necesitatea informațională, reutilizarea corpusului, lipsurile exacte și buget finit prospectiv înainte de acces autentic read-only la broker. Deschiderea economică cere suport causal, costuri și marjă suficiente și identitate nemultiplicată cosmetic. Datele protejate rămân închise.

EUR200 continuu, costurile istorice, fill-urile, robustețea și HARD21 pe portofoliu sunt **SCIENTIFIC_UNKNOWN** până la dovezile lor specifice. Nu există strategie/cBot calificat, confirmare independentă, protected forward, ordin real sau deployment live.

## Închidere de etapă

Registru: **13 CLOSED / 1 BLOCKED / 1 SCIENTIFIC_UNKNOWN**. Dovada consolidată de readback este publicată append-only la `09703adad6433f395a0506fa640f59bf3dba80b5`, în `typed-successor/verification/`; cele trei fișiere au fost recitite exact prin conector. Checkpointul20 este `pending=null`, `safe_stop=true`. Checkpointul16 original păstrează exact SHA256 `1f8d3ed42a276ad6c28a29d9c19d406fe45971dcdf8a239c589b090feff70e83`.

Continuarea periodică ChatGPT existentă a fost pusă pe pauză deoarece lucrările executabile sunt închise, iar următorul pas P0 depinde de capabilitatea administrativă neexpusă. Observatorul GitHub-native rămâne instalat, fără autorizație de bootstrap economic. Nu s-a creat o automatizare nouă. Următoarea acțiune este aplicarea legitimă a protecției deja pregătite și readback LIVE, apoi verdict integrat; nu se transferă operațiuni GitHub către OWNER.
