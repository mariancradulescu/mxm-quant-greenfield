# G03.2-R2 — simplificare OWNER și delegare limitată, fără restart

**Rezultat: OWNER_BOUNDARY_DELTA_IMPLEMENTED_NO_GO.** Dependența de custode/cheie criptografică de auditor este retrasă prin decizia OWNER. Codul izolat înlocuitor verifică aprobarea nativă OWNER a manifestului critic și permite pregătirea checkpointurilor obișnuite în aceeași delegare finită, fără semnături de auditor ori review pe checkpoint. Instalarea și activarea reală rămân neautorizate. **163 PASS / 28 BLOCKED păstrate; G03.2 nu este convertit automat în PASS.**

## Modificarea formală a cerinței

Sursa este mesajul OWNER „SIMPLIFICARE P0 ȘI ELIMINAREA DEPENDENȚELOR CRIPTOGRAFICE NENECESARE”,17.10.2026 Europe/Bucharest, din conversația curentă. El autorizează adaptarea izolată a guvernanței, nu bootstrapul/GO. [G03_2_REQUIREMENT_CHANGE.json](G03_2_REQUIREMENT_CHANGE.json) consemnează versiunea R2, riscul schimbat, controalele păstrate și criteriile de recepție.

MXM-OWNER-AUDITOR-ENROLLMENT-001 nu mai este solicitat sau necesar. Documentele și codul etapei anterioare de trust root rămân arhivă, fără a fi șterse ori rescrise drept recepții istorice. Mecanismul nou nu le importă și nu cere TrustedHead auditor, custode, cheie privată suplimentară, signer sau serviciu nou.

Auditorul din conversația separată recepționează read-only etapele critice. OWNER autorizează tranzițiile critice. Directorul execută/verifică automat în limitele politicii acceptate și nu se auto-aprobă. Independența auditorului devine procedurală și documentară în modelul ales, nu identitate criptografică a unui writer.

## Modificările efective

Sursă executată **`8ea7253533abeaac4f38609191459d904b330c23`**, pornind de la LIVE **`d9a6c5ac2ccfb7b121a3730a4ee407d96f98bded`**. Nu se declară o recepție independentă nouă a acelui HEAD doar pentru că a fost baza LIVE.

[governance.py](../../../research_core_v4/p0_owner_governance_20261017/governance.py) adaugă numai stratul de autorizare:

- GitHubReadOnly face două GET native run/approvals, fără API approve, POST sau mutație. verify_owner_review nu acceptă dict-uri „approved_by_owner”, un fixture în modul nativ, actorul runului sau commit author ca aprobare;
- aprobarea trebuie să fie un review nativ approved al contului OWNER322088485, legat de environment exact, run attempt1, SHA/path și hashul manifestului critic scris explicit în comentariu. Istoricul conflictual nu este ordonat prin timestampuri inventate; API-ul folosit nu garantează aici un approvalID/timestamp;
- manifestul fixează source/policy/evidence de recepție/operație/root și valabilitate. Bindingul runtime trebuie să fie cel din configurația acceptată, nu date de client. Referința documentară a auditorului nu devine semnătură criptografică ori aprobare OWNER;
- BoundedCheckpointPreparation verifică aprobarea inițială o singură dată; două generații succesive folosesc aceeași politică finită/principal/source/epoch, fără alte review-uri sau chei. Orice extindere, expirare, revocare sau drift oprește delegarea;
- integritatea, Evidence/PreparedInput, root OWNER1807 și SyntheticLedger sunt reutilizate **neschimbate** din supersesiunea recepționată. Unicitatea per generație folosește constrângerea atomică existentă, fără alt store. Sursa GitFenceLab/CAS și recuperarea recepționată nu sunt modificate ori retestate. SQLite nu este prezentat drept fencing GitHub;
- real_checkpoint refuză necondiționat. Un input pregătit nu publică, nu restaurează operațional și nu execută broker/research.

Compare-ul nativ confirmă exact5 fișiere noi în modulul izolat și workflow-ul său; nicio sursă istorică, implementare recepționată sau workflow istoric nu a fost modificat. [GITHUB_OBSERVATIONS.json](GITHUB_OBSERVATIONS.json) fixează delta/proveniența.

## Verificare strict a diferenței

[Run38971751030](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/38971751030), job **117211522185**, attempt **1**, **SUCCESS**: **6 teste noi PASS /23 controale negative**, zero chei generate. [Rezumat](summary.json), [teste](tests.txt), [cazuri](delta-cases.json).

Testele sunt necesare numai pentru schimbarea de frontieră: autoatestare/actor fără review refuzate; OWNER/comment/environment/source/manifest exact; două checkpointuri obișnuite cu o singură aprobare inițială; limite/revocare/expirare; integrarea cu integritatea/fencing/replay existente și refuzul writerului real. Nicio suită închisă O04.2/29P0/37supersesiune/12trust ori audit anterior nu a fost repetată. Nu au fost generate fixture-uri cu chei noi.

[Observația nativă a runului](native-observation.json): două GET autentificate au recuperat actorul OWNER și history=[]; rezultatul este **owner_critical_authorization_observed=false**. Un run SUCCESS al contului OWNER nu devine autorizare. Testele pozitive folosesc un transport explicit sintetic care este refuzat în modul nativ; nu sunt prezentate drept aprobări OWNER reale.

Workflow-ul are Contents-read și Actions-read, fără environment, OIDC, key/secret App sau token de scriere. Procesul celor6 teste refuză socket.socket; transportul nativ rulează separat numai pentru citire. Zero cereri machine-side de scriere a autorității/aprobărilor.

## Ce mai lipsește concret

[Calea minimă unică](MINIMAL_ACTIVATION_PATH.md) enumeră numai:

1. **Instalarea tehnică autorizată** a gate-ului OWNER critic, issuerului succesor înghețat/custodiei existente și publisherului Git atomic pentru exact active-v1, cu un singur principal admis. În prezent25268790 este corect blocată fără bypass; active-v1 nu există. Acordarea bypass-ului sau admiterea unui issuer nou la credential rămân interzise acum.
2. **Armarea atomică a politicii/grantului/epoch în autoritatea unică**, apoi integrarea unui singur pipeline succesor pentru restore/worker/handoff/economic. Review-ul nativ observat singur nu este grant deja instalat. Nu trebuie migrate operațional toate cele26 versiuni istorice: ele rămân arhivă/inactive; noul pipeline nu poate selecta rutele lor implicit.
3. **Recepția read-only a diferenței reale instalate și autorizarea OWNER de activare**, cu bootstrap exact și delegare finită. Cercetarea trebuie autorizată explicit în scope-ul final, cu date/bugete/termen și limite științifice; nu rezultă implicit din checkpointuri sau din această simplificare.

Acestea sunt lipsuri tehnice/de autorizare efective, nu nevoia unui nou custode. N10.1 are deja dovezi administrative recepționate; vechiul403 din registrul original nu justifică un nou audit general sau privilegiu Administration pentru App.

## Separarea celor28 BLOCKED

[BLOCKER_DISPOSITION.json](BLOCKER_DISPOSITION.json) păstrează fiecare test_id, dependența și statusul istoric, cu delta curentă:

|Categorie curentă|Număr|Efect|
|---|---:|---|
|Cerință G03.2 revizuită de OWNER|1|Custodele extern nu mai este condiție; înlocuitorul așteaptă recepție/instalare nativă.|
|Dovadă administrativă deja furnizată|1|Nu se repetă citirea/auditul general; se adjudecă domeniul dovezilor existente.|
|Instalare tehnică ori scope operațional neautorizat|6|Pachet tehnic exact și apoi activare; fără reactivarea writerilor istorici.|
|Dovezi istorice autentice nerecuperate|19|Nu sunt o cheie/permisiune lipsă; nu se fabrică și nu se repetă căutări fără sursă nouă.|
|Limită metodologică/date afectate|1|Nu se deduce impact economic și nu se relaxează automat cerința științifică.|

N25.4 privește martorul mutației istorice de release, N32.4 universul branch/generation/per-key, N34.4 loguri cache/recompresie originale. Din starea finală ori o aprobare nouă nu se reconstruiesc autentic aceste dovezi. Nu se afirmă că originalele sunt definitiv distruse; ele lipsesc din dosarul recuperat. Absența lor blochează certificarea istorică sau folosirea domeniului afectat, nu este o operațiune tehnică suplimentară de instalat. Corpusul fără proveniență rămâne carantinat/UNKNOWN. Orice scope de cercetare trebuie să demonstreze admisibilitatea/excluderile sale, nu să convertească aceste19+1 cazuri în PASS sau să pretindă o derogare implicită.

Registrul original hash `17eebd55b50bd8f4b935e2eb2532ee34ee4fd7dd6f2f2de2c9f1ef54b89b84ad` rămâne nemodificat,163 PASS/28 BLOCKED. R2 schimbă formal cerința și riscul, fără a fabrica retroactiv semnături, teste sau recepții.

## Riscuri și criterii de acceptare

GitHub autentifică un cont, nu persoana fizică aflată în spatele unei sesiuni accesibile executantului. Nu se pretinde separare criptografică împotriva controlului total al contului/administrației OWNER. Directorul nu va folosi UI/API pentru a aproba în locul OWNER; codul nou nu poate trimite aprobări. O copie mutabilă de cod/config poate fals raporta verificări, deci sursa/custodia executabilului real trebuie fixate și protejate la instalare.

Gate-ul uman este numai pentru operațiuni critice și fără secret; issuerul automat folosește separat politica armată și credentialul existent protejat. A pune required review pe fiecare emitere de checkpoint ar încălca delegarea autonomă cerută și nu este soluția propusă. Criteriile exacte de acceptare sunt în modificarea formală: origine OWNER nativă, manifest/binding fixate, limite și revocare/refuz, native atomic fence și independent read-only reception. Proba locală nu închide acele condiții reale.

## Numai aprobările OWNER indispensabile

**A: un pachet tehnic exact**, după recepția adaptării, pentru configurare/issuer/fencing și integrarea succesorului, cu lista concretă a deltelor și fără pornirea cercetării. **B: activarea explicită după recepția instalării**, cu bootstrap/politică finită și research GO numai dacă este cerut și demonstrat în acel scope. Pot fi prezentate compact drept două acte la cele două frontiere; nu se cer aprobări pe checkpoint, custode, cheie auditor, serviciu nou sau26 aprobări separate pentru versiuni arhivate.

Nici A, nici B nu este acordat aici. Noile autorizări critice ar mai fi necesare numai la schimbarea limitelor/source/custody/permisiunilor, expirarea delegării ori recuperare incertă în afara politicii. Această etapă nu cere încă bootstrap, bypass sau cercetare.

## Conservare și arhivare

OWNER1807 și staging au rămas la OID-urile recepționate;25268790 este identică, activă fără bypass; active-v1 este404. Nicio regulă, cheie, environment sau referință înghețată nu a fost modificată. Niciun checkpoint real, bootstrap, migrare operațională, cercetare/colectare/backtesting economic/broker I/O/cBot/Cloud/tranzacționare ori restart.

Artifact **12077496915**, ZIP **2421bytes**, SHA256 **`cbd1c004775f8253da74ee4c72eebf40009c0c26f759fe8f4972389123a4dced`**, CRC verificat, [bytes durabili base64](ARTIFACT_RUN38971751030.zip.b64) și4 fișiere extrase. [Index/hashuri](EVIDENCE_INDEX.json), [SHA256SUMS](SHA256SUMS.txt), [citire ulterioară GitHub](GITHUB_READBACK_RECEIPT.json). Raportul este ulterior sursei testate; receiptul se publică separat și nu pretinde auto-hash.

Se solicită recepția read-only a adaptării G03.2-R2 și a limitelor sale. **Fără GO sau restart.**
