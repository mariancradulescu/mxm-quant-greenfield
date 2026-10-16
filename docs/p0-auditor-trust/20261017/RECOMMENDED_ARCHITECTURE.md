# Soluția recomandată: custode auditor independent, semnare locală, verificare publică

Aceasta este o arhitectură unică propusă, cu componente publice implementate și testate sintetic. Nu este o înrolare reală. Identitatea/custodia unui auditor nu rezultă dintr-o conversație ChatGPT, un username GitHub, o etichetă AUDITOR ori o cheie autodeclarată în repository.

## Custodie și identitate

Un auditor nominalizat și verificat de OWNER controlează exclusiv cheia sa Ed25519 pe un dispozitiv existent administrat independent de Director, issuer, Actions și App staging. Cheia privată este păstrată local într-un container PKCS#8 criptat cu o parolă deținută numai de custode, pe disc criptat, cu acces local restrâns și backup criptat offline sub aceeași custodie independentă. Parola și backupul nu sunt transferate executantului. Nu se presupune că un asemenea dispozitiv/custode există deja sau că securitatea lui a fost verificată aici. Dacă nu există, înrolarea se oprește.

Nu se instalează servicii, conturi, HSM-uri sau privilegii GitHub noi. Auditorul poate citi repository-ul public și dovezile publice fără Contents-write ori Administration. Materialul confidențial eventual necesar se primește numai prin mecanismul criptat/controlat deja aprobat, nu prin lărgirea accesului executantului. Niciun secret de auditor nu intră în GitHub Secrets/Environments, runner, App, Codex sau chat. Cheia OWNER existentă și cheia App staging nu sunt reutilizate ca auditor.

Formatul Ed25519 și verificarea semnăturii sunt documentate de RFC8032. OpenSSL existent în runner suportă Ed25519 și criptarea fișierului privat; implementarea publică folosește pkeyutl verify, SPKI DER Ed25519 și un profil JSON ASCII/canonical explicit. Nu este o implementare criptografică proprie și nu pretinde conformitate generală RFC8785.

Referințe primare consultate pentru aceste mecanisme: https://www.rfc-editor.org/rfc/rfc8032.html ; https://docs.openssl.org/3.0/man1/openssl-genpkey/ ; https://docs.openssl.org/3.3/man1/openssl-pkeyutl/ . Ele documentează mecanismele criptografice; independența custodelui este o condiție organizațională și de custodie care trebuie verificată separat.

## O singură înrolare OWNER

Actul **MXM-OWNER-AUDITOR-ENROLLMENT-001** fixează, într-o singură decizie de înrolare completă, persoana/organizația auditorului, custodele independent, verificarea pe un canal independent, amprenta SHA256 a cheii publice SPKI, hashul manifestului genesis și dovada posesiei pentru o provocare OWNER, precum și mecanismul independent de furnizare a stării curente/high-water. Toate acestea sunt date publice ori referințe nesensibile; nu se cere cheia privată.

Custodele ales trebuie să furnizeze el însuși pachetul public și dovada semnată după ce este contactat de OWNER. Directorul nu alege identitatea, nu generează cheia ei, nu completează amprente necunoscute și nu semnează în locul ei. Pachetul exact este [OWNER_SINGLE_DECISION_REQUIRED.json](OWNER_SINGLE_DECISION_REQUIRED.json); câmpurile null sunt lipsuri reale, nu valori implicit aprobate. Nominalizarea fără verificarea cheii/custodiei nu finalizează înrolarea. OWNER poate pregăti această singură decizie după obținerea pachetului public, fără a aproba un fingerprint inventat sau incomplet.

OWNER păstrează pinul acceptat într-un reper durabil controlat de el, în afara conținutului mutabil al executantului. Publicarea ulterioară în Git este o copie verificabilă și un canal de distribuție, nu sursa autonomă de încredere inițială. Un commit al Directorului sau un run Actions SUCCESS nu substituie această acceptare. Nici cheia OWNER accesibilă unui runner nu trebuie folosită singură pentru a pretinde o decizie umană independentă.

Nu este necesară o nouă decizie OWNER pentru fiecare recepție normală sau rotație normală în identitatea înrolată. Auditorul semnează fiecare verdict pe care îl asumă; această intervenție a auditorului este necesară independenței, nu este automatizată în numele său. Pierderea/compromiterea identității cere STOP și o decizie de incident/reînrolare OWNER dacă incidentul apare; nu există recuperare autonomă dintr-o cheie pierdută. Aceasta nu este o a doua autorizare cerută în etapa curentă.

## Aprobare și verificare curentă

1. Executantul pregătește un bundle public: sursă/workflow/config/evidence hashuri și identificatori fixați, scope și o provocare aleatoare de verificare. Nu acordă autoritate prin simpla pregătire.
2. Auditorul independent citește dovezile și manifestul pe dispozitivul său, verifică proveniența și registrul curent aflat sub propria custodie, decide și semnează local receiptul canonic. Receiptul fixează identitatea, keyID, registry sequence/head, provocarea, intervalul finit, verdictul, scope, source/evidence/policy/root/operation. Poate refuza; existența unei chei nu înseamnă recepție.
3. Bundle-ul semnat și registrul public se publică în documentația repository-ului existent. Directorul poate transporta documentul public fără să poată produce semnătura auditorului. Nici materialul privat, nici fișiere PEM private nu se publică.
4. Verificatorul public recalculează pinul și dovada posesiei, verifică întregul lanț de lifecycle și comparația cu starea independentă proaspătă; apoi verifică identitatea, cheia, scope/context, provocarea, expirarea și semnătura receiptului. Rezultatul este o verificare publică, nu o autorizație de execuție sau consum al nonce-ului.
5. Consumul nereutilizabil pentru o eventuală autoritate operațională aparține backendului durabil/fenced autorizat ulterior. Nu este creat în această etapă. Verificarea criptografică repetată read-only a aceluiași document nu echivalează cu dublă acceptare operațională.

## Rotație, revocare și prospețime

Registrul public este un lanț de evenimente cu sequence exact+1, hashul precedent și identitate/custodie fixe. Rotația normală necesită semnăturile cheii vechi și noii chei pe același eveniment; nu permite reutilizarea unei chei sau a unui keyID retras. Receipturile noi folosesc cheia curentă. O revocare semnată închide identitatea pentru recepție curentă: fără fallback la cheia veche și fără rotație după revocare. Documentele istorice rămân dovezi de arhivă, fără autoritate curentă.

Custodele menține o copie durabilă a stării curente și high-water sub propriul control independent, cu backup criptat. Git este oglinda publică. Verificatorul trebuie să primească un **TrustedHead extern**, proaspăt și provenit din procesul independent, și un ceas/provocare de încredere. Nu are voie să copieze head-ul declarat în bundle în acel parametru și să îl numească independent. Modelul impune o fereastră de prospețime de cel mult300secunde; cheile și receipturile au valabilitate finită, receiptul maximum24h și niciodată după expirarea cheii.

Semnătura singură nu dovedește că o revocare sau un fork recent nu a fost ascuns de distribuitor. Fără acces la reperul independent curent se produce STOP; nu se acceptă cache/release/side-ref ca substitut. Canalul și persistența reală ale acestui reper fac parte din dovada de custodie cerută la înrolare și nu sunt instalate ori certificate de aceste teste. Verificarea pe o copie de cod mutabilă de executant poate fi fals raportată; viitorul consumator trebuie să execute numai sursa publică acceptată/fixată printr-o frontieră de execuție protejată. Nici acest lucru nu este activat aici.

## Frontiera implementării actuale

Codul nou verifică efectiv public lifecycle/recepții, dar constructorul acceptă numai explicit SYNTHETIC_ONLY și identități/keyID sintetice. verify_real_receipt refuză necondiționat. Configurația real.disabled.json are identitate/pin/binding null și toate drepturile false. Schimbarea JSON-ului nu implementează backendul real. Nu există signer de producție, loader de chei private sau fetcher care să pretindă un TrustedHead independent.

Testele noi sunt12 teste înguste ale protocolului de înrolare/lifecycle, cu trei chei efemere sintetice, șterse după suită; nu reiau O04.2 sau cele37 teste de supersesiune. Cheile publice DER și semnăturile din cazuri sunt doar fixture-uri verificabile, nu identități auditor reale. Revocarea/rotația reală, custodia fizică și furnizarea stării independente nu sunt demonstrate prin simpla simulare.

Dependența organizațională **MXM-SEM-G03.2 rămâne BLOCKED** până la înrolarea reală verificată și recepția dependențelor exacte. Registrul163 PASS/28 BLOCKED nu se modifică. Niciun bootstrap, writer, bypass, checkpoint nou, migrare operațională sau GO de cercetare nu rezultă din această arhitectură ori din actul de înrolare propus.
