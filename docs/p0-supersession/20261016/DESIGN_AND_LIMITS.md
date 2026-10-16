# Selector comun și adaptoare izolate — fără execuție

Mod: **SYNTHETIC_SUPERSESSION_PREPARATION_NO_GO**. Implementarea nouă este în `research_core_v4/p0_supersession_20261016/`; niciun modul istoric nu o importă în această etapă. Nu există migrare operațională, writer, issuer, bootstrap sau conectare la broker.

## Frontiere efective

`read_owner_archive(raw)` fixează digestul rădăcinii OWNER1807 din `OWNER_ROOT`; un manifest sau un argument al apelantului nu îl poate înlocui. `read_archive(raw, ArchivePin)` verifică integritatea bytes față de un pin furnizat pe o cale de încredere și întoarce `ArchiveRead`, fără drept de execuție. Un pin furnizat de o sursă neautentificată nu este o certificare a provenienței. Citirea pozitivă testată folosește numai arhive sintetice; jurnalul OWNER real nu este descărcat/decriptat aici.

`AuthoritySelector` refuză implicit backendul real. Poate fi construit numai cu `mode=SYNTHETIC_ONLY`, Policy, două TrustRoot sintetice distincte și SyntheticLedger marcat. Payloadul acceptabil este strict JSON canonic, cu schema sintetică, marker și toate flagurile execution/research/restart/broker_io false. `real_consumer_input` refuză necondiționat; schimbarea unei configurații nu creează backend real.

Selecția cere exact active-v1, OID/generație/digest/părinte/issuer/epoch/policy/source fixate, o singură revendicare de autoritate coerentă și transport CONFIRMED_READ. Release, legacy manifest, side-ref și OWNER_ARCHIVE sunt refuzate ca surse de autoritate operațională. Orice revendicare secundară de autoritate este conflict; locatorii arhivelor nu devin revendicări implicite și nu există fallback. Blocul `checkpoint` este date opace care nu sunt evaluate economic; structura de envelopă și generația sunt verificate înaintea oricărui consum.

`ReceiptVerifier` verifică Ed25519 prin OpenSSL, numai cu chei publice furnizate separat de payload. Verifică tipul SPKI Ed25519 și distincția cheilor prin DER, nu prin formatarea PEM. Fiecare receipt fixează principal/keyID/rol, statement canonic complet, consumer și intent, nonce și interval de valabilitate de cel mult300secunde sintetice. Rădăcinile revocate/expirate, principalul ori autoritatea revocată, snapshotul de politică expirat, rolurile duplicate și cheile identice sunt refuzate. Nu există generare de chei sau semnare în modulul verifier; numai testele generează chei efemere sintetice, șterse după suită. Nu se creează un auditor real.

`ConsumerAdapters.restore/worker/handoff/economic` cheamă același selector și întorc numai `PreparedInput` cu execution_allowed=false și external_calls_allowed=false. Nu acceptă callbacks, nu restaurează baze istorice, nu fac dispatch, nu calculează PnL și nu importă motoare istorice. Aceasta este o frontieră de pregătire reutilizabilă, nu o implementare a activităților economice sau a restartului. Un ArchiveRead nu poate fi promovat prin niciun adaptor.

## Replay, concurență și ACK

SQLite local marcat SYNTHETIC_ONLY folosește BEGIN IMMEDIATE, synchronous=FULL și constrângeri unice pe intent și nonce/rol. Un candidat succesor trebuie să fie exact generația precedentă+1 și să fixeze OID-ul părinte. Refolosirea aceluiași checkpoint de către un alt consumer este permisă numai cu aceeași identitate/digest/epoch și cu receipturi noi, scoped pentru alt consumer/intent; nu se promovează încă o dată checkpointul. Conflictul la aceeași generație, rollback-ul, gap-ul și nonce-ul reutilizat sunt refuzate înaintea commitului.

Commitul jurnalului este înainte de returnarea unui PreparedInput. Pierderea ACK după commit produce STOP și niciun rezultat de consum. `reconcile` citește mode=ro și poate confirma doar ALREADY_RECORDED_NO_REEXECUTION; nu restituie payload sau autorizație și nu permite retry. Două conexiuni concurente la același fișier pot consuma intenția o singură dată. Lipsa jurnalului nu îl recreează automat la consum.

Acesta este un jurnal local pentru probe sintetice, nu autoritate GitHub atomică și nu exact-once execuțional. Nu poate certifica protecția împotriva restaurării malițioase a unui snapshot vechi al discului, ștergerii/reinițializării în afara procesului sau coordonării între copii independente ale fișierului. Viitoarea implementare reală necesită store durabil comun, checkpoint/epoch și fencing extern autentic, cu antirollback și recepție separată. Apelantul de încredere trebuie să obțină politica, revocările, ceasul și mărturia transportului prin mecanisme autentificate; stringul CONFIRMED_READ dintr-un payload de utilizator nu este o dovadă nativă. Aceste legări reale sunt absente și backendul real rămâne închis.

## Compatibilitate și migrare

`compatibility.py` citește cele10 surse la commiturile fixate, verifică SHA256 și Git blobOID, apoi folosește numai ast.parse. Cele29 funcții/versiuni sunt verificate prin identitate, intervale de linii, semnătură și expresiile de rută din inventarul recepționat. Testele verifică forma envelopelor sintetice și frontierele de autoritate, fără echivalență comportamentală afirmată pentru codul istoric neexecutat. Matricea declară NOT_MIGRATED_NOT_EXECUTED pentru fiecare intrare.

Constructorii istorici de store pot publica release-uri; nu trebuie apelați ca cititori read-only într-o migrare viitoare. Funcțiile OWNER1807 rămân cititori de arhivă fixați, fără redirecționarea lor către active-v1. Branch-urile canonical/autonomous înghețate rămân intacte; eventuala înlocuire ar necesita surse succesoare autorizate, nu editarea checkpointului ori a surselor înghețate.

O04.2, vechile29 teste P0, probele422 și auditurile recepționate nu sunt executate de noul workflow. GitHub Actions are numai Contents-read; nu are environment, cheie App/OWNER, OIDC sau permisiune de scriere. Citirile native curente verifică păstrarea invariabililor și sursele de compatibilitate, nu reiau auditul istoric exhaustiv.
