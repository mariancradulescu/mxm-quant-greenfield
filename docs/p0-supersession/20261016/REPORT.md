# P0 — supersesiune izolată și separarea autorității pentru consumatori

Stare propusă recepției independente: **SYNTHETIC_SUPERSESSION_PREPARATION_NO_GO**. Există implementare nouă funcțională, verificată exclusiv sintetic. **37 teste noi PASS**,94 observații negative cu codul de refuz așteptat și patru intrări pozitive scoped pentru restore/worker/handoff/economic. **Zero migrări operaționale; toate28 contractele rămân BLOCKED.**

## Mandat, surse și proveniență

OWNER a confirmat în conversația curentă recepția independentă FUTURE_AUTHORITY_DENY_INSTALLED_NO_GO la `9678e920627f3f8684be3a4ba98d61b847d28c81`, exclusiv în limitele verificate, apoi a autorizat această pregătire izolată. Confirmarea este consemnată ca proveniență conversațională OWNER; nu este prezentată drept o nouă semnătură criptografică a auditorului recuperată din GitHub.

Repository unic: `mariancradulescu/mxm-quant-greenfield`. Ramură existentă de lucru/documentare: `mxm-remediation-p0-p4-20261015-v1`. Sursă executată: **`e2f9409d222c55a21f7306dfefcabc02e97ff08e`**. Publicarea raportului este ulterioară, fără modificarea codului testat. [Inventarul recepționat](../../p0-failclosed/20261016/HISTORICAL_CONSUMERS.json) are10 versiuni/29 funcții-versiuni; SHA256 `35edb86e2653e3cb56fb65163a2446e8eaff68bac4b0a3f017e14c4dafe6d27e`.

## Implementare efectivă

|Componentă nouă|Comportament implementat și verificat|
|---|---|
|[authority.py](../../../research_core_v4/p0_supersession_20261016/authority.py): AuthoritySelector/Policy/Evidence|Selecție explicită a exact active-v1 cu OID, generație, digest, părinte, issuer, epoch, sursă și politică fixate; refuz release/manifest/side-ref, conflict, revocare, expirare și transport incert; backendul real închis implicit.|
|ReceiptVerifier|Ed25519, două chei/principali sintetici distincți, verificarea tipului SPKI și a distincției DER, binding complet pe consumer/intent/root/policy/source, intervale finite și nonce. Cheile publice efemere din dovezile de test nu sunt identități OWNER/auditor reale; nicio cheie privată nu este păstrată în rezultate.|
|SyntheticLedger|SQLite marcat, tranzacție BEGIN IMMEDIATE și unicitate intent/nonce, monotonicitate și conflict de generație. Reopen și concurență pe același fișier; ACK pierdut după commit produce STOP, reconciliere read-only fără reexecuție.|
|[adapters.py](../../../research_core_v4/p0_supersession_20261016/adapters.py)|Patru entrypoint-uri care folosesc același selector și întorc numai PreparedInput sintetic, execution_allowed=false și external_calls_allowed=false. Fără callbacks istorice, restaurare de baze, dispatch, broker sau calcul economic.|
|read_archive/read_owner_archive|Bytes cu integritate fixată, ArchiveRead fără drept de execuție. OWNER1807 are digestul rădăcinii fixat în cod; nu poate fi înlocuit printr-un manifest. Testele pozitive citesc numai fixture-uri de arhivă, fără jurnalul OWNER real.|
|[compatibility.py](../../../research_core_v4/p0_supersession_20261016/compatibility.py)|10 GET de surse la commituri fixate, SHA256+blobOID, ast.parse pentru identitate/semnături/linii/rute ale celor29 funcții. Niciun import sau apel al codului istoric.|

[Designul și limitele complete](DESIGN_AND_LIMITS.md). Payloadurile sintetice nu sunt checkpointuri reale acceptate. Protecția și schema sunt reutilizabile pentru pregătire; legarea operațională la transport, trust root și execuție nu este instalată.

## Dovezi machine-side

[Run38961978161](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/38961978161), job **117179030059**, attempt **1**, event push: **SUCCESS**, la sursa fixată de mai sus. [Metadate native și controale de păstrare](GITHUB_OBSERVATIONS.json), [rezumat verificare](VERIFICATION_SUMMARY.json), [teste](tests.txt), [cazuri pozitive/negative](case-evidence.json), [compatibilitate AST](compatibility.json), [15GET native](live-readonly.json).

Workflow-ul nou `.github/workflows/mxm-p0-supersession-20261016.yml` are numai Contents-read; checkout fără credențiale persistate, acțiuni fixate prin SHA, fără environment, secrete App/OWNER, OIDC, Contents-write sau alt token de scriere. GH_TOKEN read-only este injectat numai în cele două etape GET. Procesul testelor are socket.socket blocat. Generarea/semnarea de fixture-uri folosește două chei Ed25519 efemere exclusiv sintetice în directoare temporare private, curățate după suită. Nu a fost creat/controlat niciun principal auditor real.

Cele37 teste sunt noi și țintite, nu vechile29 teste P0. Cele29 intrări de compatibilitate sunt rânduri funcție/versiune din inventar, nu un număr nou de teste ori o migrare a29 sisteme. S-au efectuat10 GET de surse și15 GET de păstrare; **zero cereri de scriere machine-side**. Niciun modul istoric capabil de mutație/broker I/O nu a fost importat sau executat.

|Control|Dovadă observată|
|---|---|
|Pozitive scoped|Toate cele patru adaptoare întorc numai input sintetic după receipturi distincte pentru consumer/intent;4 intenții și8 nonce-uri, un singur head sintetic.|
|Release, manifest vechi, side-ref, OWNER_ARCHIVE ca autoritate|Refuzuri HISTORICAL_SOURCE_CANNOT_AUTHORIZE și EXACT_REF_REQUIRED, fără fallback.|
|OID/generație/digest/checkpoint/principal/părinte/epoch greșite|Coduri specifice de refuz; flag de execuție ori câmpuri suplimentare în envelopă sunt refuzate.|
|OWNER/auditor absent, invalid, expirat, rol duplicat ori cheie identică|Refuzuri de receipt, semnătură, timp, identitate ori separare a cheilor; niciun consum al intenției după validare eșuată.|
|Receipt reutilizat și replay|INTENT_REPLAY după reopen; RECEIPT_REUSE pentru alt intent semnat cu nonce deja consumat.|
|Rollback, gap și conflict|ROLLBACK, GENERATION_GAP_OR_PARENT și CONFLICTING_SAME_GENERATION; un succesor sintetic valid este permis numai cu părinte exact și generație+1.|
|Revocare și politică expirată|Refuz pentru rădăcină revocată/expirată, issuer/autoritate revocată și snapshot de politică în afara ferestrei finite.|
|Arhivă promovată în consum operațional|Toate cele patru adaptoare refuză ArchiveRead; integritatea arhivei și pinul OWNER real nu pot fi înlocuite de fixture.|
|Transport incert|UNKNOWN_ACK/TIMEOUT/STALE_CACHE/MISSING produc STOP și zero intenții consumate.|
|ACK pierdut după commit|STOP; reconciliere numai read-only, fără payload/drept de retry; noul apel este refuzat ca replay.|
|Concurență|Două conexiuni pe același jurnal: exact un ACCEPTED_SYNTHETIC și un INTENT_REPLAY. Nicio execuție externă are loc.|
|Date ambigue/alterate|Digest nepotrivit, JSON duplicat ori necanonic refuzate.|

În [case-evidence.json](case-evidence.json) sunt100 evenimente:94 observații negative potrivite exact,4 pozitive cu declarații/semnături sintetice și material public de verificare, un rezultat ACK și unul de concurență. Rezultatele nu constituie semnături OWNER/auditor reale ori certificare a tuturor comportamentelor istorice.

## Matrice și migrări care necesită autorizare separată

[CONSUMER_MIGRATION_MATRIX.json](CONSUMER_MIGRATION_MATRIX.json) fixează fiecare intrare prin migration_id **MXM-SUP-C01…C29**, path, source_ref, blobOID, SHA256 la nivel de sursă, funcție, linii, semnătură AST, rută observată, frontieră nouă și acțiunea viitoare exactă. Fiecare rând declară operational_migration_performed=false și current_stage_changes_to_historical_source=false.

- **3 frontiere OWNER** rămân cititori ai arhivei1807; nu se propune redirecționarea sau migrarea lor operațională. Cititorul viitor active trebuie separat.
- **26 frontiere de integrare viitoare** necesită aprobare OWNER punctuală înaintea modificării sursei/callsite-ului/workflow-ului relevant. Sunt frontiere funcție/versiune, nu26 aplicații sau26 schimbări independente obligatorii. Planul per rând cere sursă succesoare fixată, consumer, transport/trust roots, delta de workflow/permisiuni dacă există, teste negative, plan STOP și recepție independentă.
- Constructorii Store/RotatingStore/BoundStore/StoreAdapter nu trebuie reutilizați ca shortcut read-only: au rute de creare/publicare sau selecție implicită a release-ului. Matricea cere înlocuirea lor cu un cititor pur înaintea oricărui restore viitor.
- Main/gate/dispatcher trebuie să verifice frontiera înaintea constructorului, restore-ului, workerului, handoff-ului ori oricărei căi broker/economice. Gate-urile STOP existente se păstrează. Dry_run staging nu reprezintă migrare și nu este promovat la active.
- Cele144 workflow-uri istorice rămân nemodificate, nereactivate și nemigrate. Sursele canonical/autonomous înghețate nu se modifică; planurile viitoare vizează succesori autorizați, cu supersesiune explicită.

În codul nou, release body, manifest vechi, side-ref și fallback automat sunt eliminate ca surse de autoritate pentru toți cei patru consumatori. Aceste rute **nu sunt declarate eliminate global din codul istoric**, care nu a fost modificat sau executat. Compatibilitatea AST/envelopă nu dovedește echivalență comportamentală ori migrare operațională.

## Păstrarea autorității și a limitelor recepționate

Cele10 definiții native de rulesets sunt identice înainte/după, inclusiv25268790 active, exact active-v1, bypass_actors=[]. OWNER ref1807 rămâne `a830c132521bd4348454653f713e04f6107484fe`; staging rămâne `c6644174244cd92b8e41b17f241b8f5e545fddd9`; active-v1 este404. SHA256 body release412686323 rămâne `01a6d82498c033131302b272ee4ba2f83c4e445f40585f76dfee1a91466679b9`. Canonical și autonomous rămân la OID-urile recepționate.

Nu au fost operate setări, permisiuni, chei, environment-uri sau referințe OWNER/staging. Nicio referință activă creată, bypass acordat, issuer operațional instalat sau token de scriere emis de această implementare. Nu s-a repetat O04.2, vechea suită29, proba422 ori auditul exhaustiv.

**HTTP422 anterior rămâne neatribuit concludent și run38954973739 rămâne FAILURE.** Confirmarea OWNER a recepției acelei etape nu schimbă rezultatul tehnic sau limitele sale. Nu s-a încercat cosmetizarea lui.

Zero acceptări de checkpointuri reale, restart, cercetare alpha, colectare, backtesting economic, broker I/O, ordine, cBot, Cloud ori protected forward.

## Blocaje și condiții pentru etapa următoare

[Registrul28 BLOCKED păstrate](BLOCKED_CONTRACTS_PRESERVED.json) reproduce exact rândurile fără schimbare de status; hashul registrului canonic nemodificat este `17eebd55b50bd8f4b935e2eb2532ee34ee4fd7dd6f2f2de2c9f1ef54b89b84ad`. Progresul noii componente este separat de închiderea contractelor. Nicio recepție independentă nu este fabricată.

Pentru acest dosar se solicită recepția auditorului asupra codului nou și domeniului sintetic. Pentru orice etapă operațională ulterioară rămân indispensabile:

1. Nominalizarea și custodia reală independentă a principalului/trust root-ului auditorului, cu proveniență OWNER și mecanisme de revocare/rotație. Cheile efemere din teste nu satisfac MXM-SEM-G03.2.
2. Politică, ceas, revocări și mărturie de transport autentificate și proaspete; store durabil comun și fencing atomic nativ, antirollback și reconciliere recepționate. SQLite pe același fișier nu certifică GitHub atomicity sau rezistență la rollback malițios al discului. Un string CONFIRMED_READ furnizat de utilizator nu este probă de transport.
3. Aprobarea punctuală a frontierelor de integrare din matrice, înainte de migrarea reală; testele de integrare reale, dacă vor fi autorizate, trebuie să păstreze STOP și să aibă recepție distinctă. Nu există încă echivalență comportamentală certificată pentru modulele istorice neexecutate.
4. Rezolvarea și recepția dependențelor exacte P0 încă BLOCKED, inclusiv izolarea principalilor/autorizațiilor reziduale. Orice issuer real, legare credential/environment, bypass sau bootstrap necesită autorizare OWNER separată, exactă. Mandatul curent nu le acordă.

Nu se cere și nu se deduce GO pentru cercetare din recepția acestui dosar.

## Arhivare durabilă și verificare de recepție

Artifact **12072469188**, ZIP14199bytes, SHA256 **`a51580de93a5fac07ffc33eba35a90c5f1fb65cc7d2f27d3efb4730135c12568`**, CRC verificat. [Bytes ZIP base64](ARTIFACT_RUN38961978161.zip.b64) și toate cele5 fișiere extrase sunt versionate în Git, astfel că aceste rezultate nu depind de expirarea artefactului Actions la14.01.2027. Artefactul conține numai rezultate publicabile și identități de test explicit sintetice, fără chei private, credențiale reale, date confidențiale sau capturi sensibile.

[Index SHA256](EVIDENCE_INDEX.json), [SHA256SUMS](SHA256SUMS.txt), [receipt de citire ulterioară GitHub](GITHUB_READBACK_RECEIPT.json). Indexul fixează codul testat și documentele publicate; receiptul se adaugă într-un commit separat și nu pretinde auto-hash. Versiunea de raport nu schimbă sursa executată.

Auditorul este rugat să verifice run/source/attempt și bytes, cele37 teste și refuzurile, distincția arhivă/input sintetic/execuție, matricea10/29, limitele SQLite/transport/trust root, lipsa migrării istorice și păstrarea28 BLOCKED. Directorul solicită recepția și nu semnează în numele auditorului.
