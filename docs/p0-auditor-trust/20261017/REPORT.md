# P0 — arhitectura de încredere independentă a auditorului

Rezultat: **PUBLIC_TRUST_VERIFIER_READY_AWAITING_INDEPENDENT_ENROLLMENT_NO_GO**. Arhitectura minimă și verificatorul public sunt implementate și verificate prin12 teste noi. **Încrederea independentă reală nu este încă înrolată. MXM-SEM-G03.2 și toate cele28 BLOCKED rămân BLOCKED.** Frontiera rămasă cere o singură decizie OWNER de desemnare și înrolare, pe baza unui pachet public furnizat de custodele independent.

## Baza și limitele mandatului

OWNER a confirmat în conversația curentă recepția independentă SYNTHETIC_SUPERSESSION_PREPARATION_NO_GO la `e1d021a72ab3ada68b86851b74ebc4efc2cee8b3`, exclusiv în domeniul sintetic verificat. Aceasta este proveniență conversațională OWNER, nu o nouă semnătură criptografică independentă. Au fost recuperate MXM_CONTINUITY.md, cerințele AUDITOR_TRUST_ROOT din dosarul failclosed, rezultatul supersesiunii și registrul canonic. Nu s-au repetat O04.2, cele37 teste de supersesiune, vechea suită29, proba422 sau auditurile recepționate.

Repository existent: `mariancradulescu/mxm-quant-greenfield`; ramură existentă `mxm-remediation-p0-p4-20261015-v1`. Sursa testată: **`8326f992141f519316e06a583a482a284be17905`**. Publicarea documentară este ulterioară și nu modifică sursa executată.

## Soluția principală recomandată

**Custode auditor independent, cheie Ed25519 locală criptată, pin de înrolare acceptat de OWNER pe canal independent, registru public de lifecycle și receipturi semnate.** [Arhitectura completă](RECOMMENDED_ARCHITECTURE.md) definește custodia, verificarea, rotația, revocarea și limitele de distribuție.

Cheia este controlată numai de auditor/custode, pe un dispozitiv existent administrat independent, cu parolă și backup criptat offline sub aceeași custodie. Directorul, issuerul, GitHub Actions, App staging și secretele lor nu au acces la ea. Nu este necesar un nou serviciu, repository, cont cu drepturi de scriere sau privilegiu administrativ. Nu se pretinde că un astfel de custode/dispozitiv a fost identificat ori verificat aici. ChatGPT nu este singur o identitate criptografică independentă.

GitHub și Actions existente sunt suficiente pentru sursele/dovezile publice, distribuția documentelor semnate și verificarea publică read-only. Nu pot furniza singure custodia independentă a unei persoane neînrolate. A pune un secret nou pe același runner sau a redenumi un principal al executantului ar încălca obiectivul și nu s-a făcut.

OWNER intervine o singură dată la înrolarea completă: acceptă identitatea/custodia verificate, fingerprint-ul public și hashul genesis/dovezii posesiei, păstrând pinul într-un reper durabil aflat în afara controlului executantului. Auditorul semnează apoi propriile recepții; rotația normală cere semnătura veche și nouă, fără aprobări OWNER repetate. Un incident de pierdere/compromitere produce STOP și ar necesita o decizie de incident dacă apare; nu există recuperare autonomă sau o astfel de autorizare cerută acum.

## Implementări efective permise

Cod nou în [research_core_v4/p0_auditor_trust_20261017](../../../research_core_v4/p0_auditor_trust_20261017/public_verifier.py), fără importarea ori modificarea consumatorilor istorici sau a issuerului:

|Componentă|Comportament implementat|
|---|---|
|EnrollmentPin + genesis|Hash genesis și SPKI externe, subject/custody fixate, scope PREPARATION_RECEPTION_ONLY, dovadă Ed25519 de posesie. O cheie autodeclarată/self-signed nu substituie pinul.|
|Verificare publică Ed25519|SPKI DER cu algoritm fix, SHA256, semnătură64bytes, prefix de domeniu și JSON canonic ASCII/integer-only cu respingerea duplicatelor/câmpurilor necunoscute. Niciun API de semnare sau loader privat în verificator.|
|Rotație|Sequence exact+1, hash precedent, identitate/custodie constante, semnături veche+nouă; refuz de cheie/keyID retras ori reutilizat.|
|Revocare|Eveniment semnat închide identitatea; refuz de receipt și rotație după revocare, fără fallback.|
|Expirare|Valabilitate finită cheie, receipt maximum24h, fără depășirea valabilității cheii și fără receipt anterior head-ului/cheii curente.|
|TrustedHead independent|Reper extern cu sequence/hash și fereastră de prospețime maximum300secunde; rollback/fork/head vechi refuzat. Verificatorul nu obține singur acest reper și nu acceptă un dict prezentat drept stare deja verificată.|
|Receipt public|Verifică din nou întregul lanț, identitatea/keyID/head, provocarea exactă, scope/verdict, source/evidence/policy/root/operation și semnătura. Întoarce numai signature-valid, execution_allowed=false, receipt_consumed=false.|
|[real.disabled.json](../../../research_core_v4/p0_auditor_trust_20261017/real.disabled.json)|Identitate/pin/credential binding null, nicio înrolare/aprobare reală, toate drepturile false. verify_real_receipt refuză necondiționat; constructorul cere explicit SYNTHETIC_ONLY și identități sintetice.|

Nu s-au generat, instalat, importat sau folosit chei private reale de auditor. Numai testele au generat trei chei efemere sintetice, în directoare temporare private, curățate după suită. Dovezile păstrează material public DER și semnături sintetice, fără chei private reale/sintetice sau fișiere PEM private.

## Verificare nouă și dovezi

[Run38967638370](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/38967638370), job **117197963654**, attempt **1**, **SUCCESS**, la SHA-ul sursei de mai sus. [Rezultat](summary.json), [teste](tests.txt), [cazuri verificabile](cases.json), [5GET de păstrare](preservation.json), [proveniență GitHub](GITHUB_OBSERVATIONS.json).

Cele12 teste noi verifică strict protocolul nou: înrolare și posesie, respingerea self-enrollment, schimbarea identității/custodiei, rotație validă și semnătură veche/nouă lipsă ori invalidă, replay/fork al lanțului, revocare fără fallback, expirări, prospețimea reperului independent, bindingul receiptului/provocării, profilul wire și absența înrolării reale. **32 controale negative** au produs exact codurile așteptate. Cazurile pozitive includ înrolare publică sintetică și rotație urmată de receipt cu cheia nouă.

Testele nu accesează rețeaua; socket.socket este refuzat în procesul lor. Workflow-ul nou are numai Contents-read, checkout fără credențiale persistate, fără environment, App/OWNER key, OIDC sau token de scriere. Etapa separată de păstrare face5 GET native, zero scrieri. Nu este un nou audit general.

Lista celor10 rulesets și timestampurile updated_at sunt identice înainte/după; definiția completă25268790 este identică, activă și cu bypass_actors=[]. Acesta este domeniul citirilor de păstrare, nu o nouă reauditare exhaustivă a tuturor ACL. OWNER1807 rămâne `a830c132521bd4348454653f713e04f6107484fe`, staging `c6644174244cd92b8e41b17f241b8f5e545fddd9`, active-v1 este404. Nu au fost operate reguli, chei, permisiuni, environment-uri, referințe OWNER/staging sau workflow-uri istorice.

## Ce nu poate fi certificat sau activat aici

O semnătură verificabilă dovedește posesia unei chei și bindingul documentului, nu identitatea umană ori custodia fizică. independent_from este o declarație fixată în pinul acceptat extern, nu o măsurătoare magică a dispozitivului. Nu există în dosarul recuperat o identitate de auditor real nominalizată și verificată, cheia sa publică acceptată și mecanismul său independent de stare curentă. Nu se fabrică aceste date.

Git-ul controlat de executant poate ascunde un head/revocare sau poate prezenta cod de verificare modificat. De aceea TrustedHead/ceasul/provocarea și codul acceptat trebuie să provină din frontiere protejate, independente. Furnizarea/persistența reală a reperului, autentificarea canalului și custodia trebuie confirmate la înrolare; testele doar impun interfața și refuzul lipsei/stării vechi. Nu se declară o sursă independentă instalată, rezistență certificată la rollback malițios al discului sau protecție împotriva unei chei efectiv compromise și a unei revocări ascunse.

Receiptul din acest protocol autorizează numai recepția de pregătire; BOOTSTRAP/UPDATE/execuție sunt refuzate. Verificarea publică este read-only și poate fi repetată ca verificare de document; nu consumă nonce-uri și nu pretinde exactly-once operațional. Legarea la un store durabil/fenced pentru orice autoritate reală rămâne în domeniul etapelor anterioare BLOCKED și ar necesita autorizare separată. Nicio migrare operațională a celor26 frontiere ori144 workflow-uri nu este făcută.

## Unica decizie OWNER necesară acum

**MXM-OWNER-AUDITOR-ENROLLMENT-001 — desemnarea și înrolarea unui singur auditor/custode independent, cu identitate, custodie, SPKI SHA256 și genesis SHA256 verificate pe canal independent, exclusiv pentru receipturi de pregătire.**

[Actul exact pregătit](OWNER_SINGLE_DECISION_REQUIRED.json) este TEMPLATE_ONLY, NOT_APPROVED_NOT_ENROLLED. Custodele ales trebuie să furnizeze pachetul public și dovada posesiei; OWNER îl verifică și acceptă pinul complet. Nu se cere aprobarea unor câmpuri null. Aceasta este următoarea acțiune indispensabilă; Directorul se oprește înainte de înrolarea reală și nu creează identitatea sau semnează în numele ei.

Actul nu acordă privilegii GitHub, nu cere servicii noi și nu autorizează bootstrap, writer, issuer, bypass, migrare, cercetare ori restart. După o înrolare reală validă va fi necesară recepția independentă a legărilor reale înaintea oricărei concluzii de închidere a dependenței. În etapa curentă registrul rămâne **163 PASS / 28 BLOCKED**, cu semantica istorică păstrată; progresul verificatorului este consemnat separat în [REGISTRY_DISPOSITION.json](REGISTRY_DISPOSITION.json).

## Arhivare și recepție

Artifact **12076100839**, ZIP **5868bytes**, SHA256 **`bae146fc7ed725a9cb2005e89752f758f79cd27de30b27f51230e6b725cc5318`**, CRC verificat. [Bytes ZIP base64](ARTIFACT_RUN38967638370.zip.b64) și cele4 fișiere extrase sunt versionate, separat de expirarea Actions din14.01.2027. Nu sunt publicate date confidențiale sau credențiale reale.

[Index](EVIDENCE_INDEX.json), [SHA256SUMS](SHA256SUMS.txt), [receipt de citire GitHub ulterioară](GITHUB_READBACK_RECEIPT.json). Raportul și continuitatea se citesc la commitul publicării; sursa executată rămâne8326f992141f519316e06a583a482a284be17905. Receiptul de readback este ulterior și nu pretinde auto-hash.

Se solicită recepția independentă a arhitecturii, codului public, celor12 teste noi și frontierelor declarate. **Fără bootstrap real, autoritate activă, checkpoint nou, writer, restart, colectare, cercetare alpha, backtesting economic, broker I/O, cBot, Cloud sau tranzacționare.**
