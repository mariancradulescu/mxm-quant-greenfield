# P0 — pregătirea tranziției viitoare, fără GO

## Autoritate și scope

OWNER a autorizat în conversația din 16.10.2026 etapa „AUTORIZARE LIMITATĂ P0 PENTRU PREGĂTIREA CONTINUĂRII SIGURE”, după confirmarea recepției O04.2 staging și a arhivării la `8a71881c6ef8154be4d24aab7dad3b1dd212392f`. Aceasta este proveniență conversațională consemnată de Director, nu o semnătură criptografică OWNER fabricată.

Sunt autorizate implementări izolate, teste sintetice și citiri în repository-ul existent, machine-side prin Actions. Nu sunt autorizate checkpointuri reale, activarea unui writer, cercetare sau mutații ale ramurilor/regulilor înghețate. Cele 28 BLOCKED se păstrează.

## Ce este implementat

`TRANSITION_SPEC.json` fixează ROOT OWNER 1807, OID-ul staging, HEAD-ul de bază, sursele acceptate, hashul registrului, politica/inventarele păstrate și dependențele rămase. `transition.py` implementează numai un model de bootstrap în repository Git local marcat sintetic; reutilizează transportul `GitFenceLab` neschimbat. Nu are token, client GitHub writer, parametru pentru backend real sau funcție de activare. `production_checkpoint` refuză necondiționat.

Modelul: `SYNTHETIC_STOP → PREPARED_SYNTHETIC → SIMULATED_BOOTSTRAP_NO_GO`. Toate flagurile operaționale rămân strict `false`; ROOT și generația OWNER rămân referințe nemodificate. Semnăturile sunt Ed25519 sintetice, create temporar în runner, nu chei OWNER, App sau auditor independent. Aprobare cu rol și cheie distinctă pentru OWNER_SYNTHETIC/AUDITOR_SYNTHETIC; schema sintetică nu poate autoriza o operațiune reală. Trust roots provin din harness, nu din payload. Timpul este injectat în test; nu este pretins ceas de producție.

Semnăturile leagă rolul, digestul întregului plan, SOURCE_SHA, digestul politicii, ROOT STOP, OID staging, referința fixă, epoch/version, operation_id, scope și intervalul de valabilitate. Lipsă/duplicare rol, cheie greșită, schimbare semantică chiar resemnată, expirare și GO falsificat produc refuz înainte de publicare. Un ACK pierdut după commit se rezolvă prin OID/operation/digest fără al doilea bootstrap.

Rutarea modelată refuză explicit toate cele 144 căi istorice din inventarul fix. Cele 75 candidate suplimentare păstrate nu primesc autoritate; nici absența unui write static, nici acest model nu revocă drepturi GitHub native. Aceste teste verifică rutarea NOUĂ, nu relansează workflow-uri istorice și nu recertifică izolarea staging O04.2.

`live_probe.py` folosește numai o listă finită de endpointuri GET. POST/PUT/PATCH/DELETE, GET cu body, endpointuri nepermise și redirecturi autentificate sunt refuzate înainte de IO. Verifică metadata ROOT/release și configurația vizibilă a regulilor, înainte/după; observă absența autorității reale. Nu descarcă jurnalul OWNER, nu citește secrete, environment ori credential App, nu solicită OIDC, nu importă brokerul.

## Contractul viitoarei implementări reale — NU executat aici

1. Manifest unic versionat pentru bootstrap, cu ROOT STOP/gen1807/jurnal existent, sursa issuer și reader fixate prin SHA, environment/workload/audience exacte, snapshots și hashuri native ale politicilor, referință activă unică, epoch, expirare și operation_id. O aprobare nu se transferă automat la un alt commit sau ref.
2. Recepție auditor cu rădăcină de încredere administrată independent și aprobare OWNER distinctă pentru scope-ul real. Fișierele semnate de executant sau cheia OWNER din Actions nu substituie auditorul. Nicio cheie nouă pentru auditor nu a fost creată aici.
3. Regula NOUĂ creation/update exact pentru `refs/heads/mxm-o04-active-v1`, bypass numai pentru App dedicată; păstrarea tuturor regulilor existente append-only și freeze. Sursele issuer-ului real și environment allowlist trebuie fixate separat. Același App poate fi evaluat fără extindere de permissions, însă issuer-ul staging înghețat și audience-ul său nu se reutilizează automat pentru producție.
4. Bootstrap real prin receive-pack cu expected-old-OID zero pentru referința absentă, genesis cu un singur părinte ROOT STOP și pointer la jurnalul existent. Nu se rescrie STOP și nu se dublează checkpointul OWNER ca rezultat nou. Mai târziu, fiecare acceptare necesită CAS pe expected-old-OID exact și validare epoch/lease/version/proveniență și dovezi criptate persistate înainte de commit; Releases PATCH nu este autoritate.
5. Consumatori fixați la noua autoritate numai după supersesiune explicit aprobată și recepționată. Toate rutele istorice neautorizate rămân deny; niciun fallback la release/side branch, payload PRODUCTION_GO ori identitate din JSON nu acordă write.
6. ACK incert: citire exactă a referinței, OID, operation_id și digest; fără retry orb. La expirare ori incident: oprire fail-closed și revocare de epoch prin procedură autorizată, fără force rollback, delete sau alterarea checkpointurilor acceptate.

Aceasta este o specificație pentru lucrul viitor, nu cod real instalat. Modelul actual NU creează referința activă și nu poate transforma un rezultat sintetic în GO.

## Dependențe P0 și aprobări indispensabile

`TRANSITION_SPEC.json` conține cele nouă contracte P0 și dependențele D1–D6. O04.1/N10 beneficiază de dovezile staging acceptate, dar fără extindere automată la toate namespace-urile istorice. N25.3 necesită supersesiune/migrare ori disable autorizat pentru rutele suplimentare afectate. G03.2 necesită principalul/rădăcina auditorului independent, nu o semnătură generată de Director.

Înainte de orice writer real rămân: aprobarea OWNER separată a operațiunii reale exact fixate; aprobarea configurației native a noii autorități și workload-ului; recepția/trust root auditor independent; dovezi native ale politicilor/ACL afectate; autorizarea oricărei migrări istorice suplimentare. Citirea administrativă poate utiliza sesiunea legitimă existentă sau acces read separat aprobat; nu este necesar și nu se propune Administration pentru App staging.

N25.4/N32.4/N34.4 cer dovezi istorice autentice. Aceste lipsuri nu se depășesc printr-o aprobare nouă sau test sintetic și nu sunt declarate închise. Impactul lor asupra unui scope viitor este al recepției independente, nu al unei excepții unilaterale a Directorului.

## Threat model și limite

Acoperit de noile teste: payload cu GO falsificat, roluri confundate, signer duplicat/greșit, altă sursă/ref/policy/ROOT, expirare, replay, ACK incert, transport cu mutații și rute istorice către model. Neacoperit ca garanție nativă: identitate auditor instalată, ACL pe viitorul ref absent, emiterea tokenului real și toate namespace-urile istorice. Testele locale nu constituie refuzuri native GitHub ale unui writer real.

Citirile native coroborează numai configurația vizibilă. Omiterea bypass_actors, un 403 ori lipsa audit logului se raportează explicit UNKNOWN/visibility limit; probele vechi acceptate rămân cu proveniența lor. Administratorul capabil să schimbe reguli și custodia cheilor rămân limite de guvernanță.

Workflow-ul nou are numai contents:read/actions:read, fără environment/secrets/OIDC. Trigger push exclusiv pe fișierele noi ale modulului și workflow; nu atinge filtrele existente. Numai actor OWNER, branch exact, attempt1 și SHA al pushului. Nu există dispatch. Artefactele includ teste, citiri, surse și SHA256; rezultatele finale public-safe vor fi versionate în Git, separat de retenția Actions.
