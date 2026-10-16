# P0 — protecție fail-closed a viitoarei autorități, fără bootstrap

Verdict al executantului: **FUTURE_AUTHORITY_DENY_INSTALLED_NO_GO**. Protecția exactă este instalată și citită nativ; unica tentativă sintetică a fost respinsă. Atribuirea explicită a422 unei anumite reguli și respingerea nativă a unui update rămân limite de probă. **Runul nu este SUCCESS. Toate28 contractele rămân BLOCKED.** Se solicită recepție independentă exclusiv pentru acest domeniu.

## Mandat și proveniență

OWNER a confirmat recepția administrativă la `6c743b918bccc66809cf81e2a0d2d8c874fd348a` și a autorizat în conversația curentă regula exactă creation/update fără bypass, pregătirea separată a issuerului inactiv, probe sintetice izolate, inventarul consumatorilor și cerințele auditorului. Aceasta este proveniență conversațională declarată de executant, fără semnătură independentă nouă. Recepțiile anterioare O04.2 și P0 nu sunt redeschise.

Ramură de implementare/documentare: `mxm-remediation-p0-p4-20261015-v1`. Sursa executată: `7af72e8ec1bb761b322e18c44ee9a24c01d256ab`. Celelalte ramuri înghețate nu au fost modificate. Documentația și dezactivarea probei sunt publicate ulterior; acel commit ulterior nu este prezentat ca întregul cod executat de run.

## Reguli native instalate

| Ruleset | Țintă exactă | Enforcement / bypass | Reguli |
|---|---|---|---|
|25268790|`refs/heads/mxm-o04-active-v1`|active / `[]`; connector `current_user_can_bypass=never`|creation, update, deletion, non_fast_forward|
|25268949|`refs/heads/mxm-o04-synthetic-deny-20261016-v1`|active / `[]`; connector `current_user_can_bypass=never`|creation, update, deletion, non_fast_forward|

Creation/update au fost adăugate explicit. Restricțiile deletion/force-push implicite ale noilor reguli au fost păstrate. Nu există exclude ori wildcard în noile ținte. Regula append-only25222248 pentru `mxm-o04-*` continuă să impună deletion/non_fast_forward/required_linear_history. Toate cele opt definiții anterioare sunt identice integral cu exportul din etapa administrativă, inclusiv bypass-ul exclusiv staging al App5343530. Nu s-au modificat cele opt reguli, secretele, environment-ul staging, cheile, permisiunile App sau checkpointurile.

Crearea regulilor a folosit UI administrativ legitim, cu reconfirmare securizată GitHub Mobile. Salvarea a fost confirmată prin mesajul nativ „Ruleset created”, apoi prin GET al fiecărei definiții complete. [Înaintea probei](NATIVE_RULESETS_BEFORE_PROBE.json) și [după probă](NATIVE_RULESETS_AFTER_PROBE.json) sunt identice pe toate10 definițiile. Acestea sunt dovezi la momentul citirii; un administrator capabil să editeze regulile repository-ului nu este eliminat ca trust boundary.

## Verificare machine-side, fără reluarea auditurilor

[Run38954973739](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/38954973739), job117155431186, attempt1: **failure**. [Receipt nativ integral](NATIVE_RECEIPT_RUN38954973739.json), [cele8 teste noi](TESTS_RUN38954973739.txt), [rezumat verificat](VERIFICATION_SUMMARY.json).

- Opt teste issuer inactiv PASS: configurație, refuz token/bootstrap/checkpoint, flaguri de activare, legări de credențiale/principali, drift de referință/root/politică și câmpuri suplimentare. Nu au fost executate29 teste P0 vechi sau O04.2.
-32 GET native și un singurPOST `git/refs`, exclusiv pentru numele sintetic protejat. GITHUB_TOKEN al jobului avea Contents-write și Metadata-read, fără App key, environment, OIDC, OWNER key sau token App emis. Aceasta este permisiunea existentă a jobului de probă izolată; nu s-a schimbat default-ul repository-ului ori vreo permisiune administrativă.
- Candidatul `a13d7b0d9005ec175e3c2851ee06c956e58a9e63`, tree `fc368e41f527fca6b2752e293287863601084833`, este un obiect Git fără ref, cu un singur fișier `SYNTHETIC_ONLY.json`, fără workflow/date de piață/checkpoint. Crearea obiectelor nu a creat autoritate sau ramură.
- POST a primit **HTTP422**, corp nativ `{"message":"Reference update failed","documentation_url":"https://docs.github.com/rest/git/refs#create-a-reference","status":"422"}`. Referința sintetică a fost404 înainte/după. Refuzul este observat; cauza specifică ruleset nu este declarată de acel mesaj. Condiția strictă a probei a cerut text care să numească restricția și a eșuat cu `RULE_REJECTION_NOT_PROVEN`. Nu se schimbă verdictul runului și nu se repetă scrierea.
- Endpointul rule-suites a returnat403 `Resource not accessible by integration`; UI de detaliu a expus configurația și numai Export/Delete în opțiuni, fără o atribuire rule-suite recuperată. Nu s-a escaladat accesul și nu se pretinde că acest403 împiedică toate citirile administrative. Soluția minimă pentru atribuire suplimentară este un export read-only al evenimentului rule-suite, dacă administratorul legitim îl poate obține printr-un canal existent; lipsa lui nu justifică altă probă ori bypass.
- Nu s-a încercat niciodată creare/update pe active-v1. Nu s-a testat nativ update pe o referință existentă: ambele ținte sunt inexistente și nu s-a introdus o excepție de bootstrap. Regula update este verificată în definiția nativă; execuția ei nu este certificată aici. O eventuală probă suplimentară ar necesita un plan sintetic separat, recepționat înaintea oricărei scrieri și fără relaxarea vreunei protecții.

După unica tentativă, workflow-ul nou este dezactivat prin `if: ${{ false }}` la job. Nu se păstrează un executor de scriere activ sau retry automat. Codul issuer/config/teste rămâne identic cu versiunea testată; numai workflow-ul probei este dezactivat ulterior. Nu se modifică workflow-uri istorice.

## OWNER și domenii interzise

OWNER1807: `mxm-o04-accepted-owner-1807-v1` = `a830c132521bd4348454653f713e04f6107484fe`, înainte/după. Staging authority = `c6644174244cd92b8e41b17f241b8f5e545fddd9`, înainte/după. Body release412686323 SHA256 = `01a6d82498c033131302b272ee4ba2f83c4e445f40585f76dfee1a91466679b9`, identic. active-v1 este404 înainte/după. Jurnalul criptat OWNER nu a fost descărcat sau decriptat. Zero bootstrap real, checkpoint nou, broker I/O, ordine, cercetare, colectare, backtesting economic ori restart de campanie.

## Issuer inactiv și supersesiune

[Design și porți](../../../research_core_v4/p0_failclosed_20261016/DESIGN.md), [cod](../../../research_core_v4/p0_failclosed_20261016/issuer.py), [config DISABLED](../../../research_core_v4/p0_failclosed_20261016/issuer.disabled.json). Token, bootstrap și accept_checkpoint sunt refuzate necondiționat. Nu există încă backend GitHub atomic real sau verifier real de recepție auditor; sunt cerințe explicite pentru o implementare autorizată ulterior. Sursa este versionată, nu o nouă ramură înghețată de issuer și nu o implementare reală recepționată.

[Inventar exact](HISTORICAL_CONSUMERS.json):10 versiuni de sursă fixate prin commit, blobOID, SHA256, funcție și intervale de linii;29 rânduri funcție/versiune. Inventarul urmărește punctual entrypoint-urile deja cunoscute și dependențele directe, fără a pretinde un nou audit exhaustiv al tuturor consumatorilor istorici.

|Consumator / sursă|Rută și supersesiune necesară|
|---|---|
|remediation `owner.py:main`, `child`, `read_asset`|release412686323 și manifest1807; păstrare ca cititor arhivă OWNER fixat. Un viitor cititor active trebuie separat, fără redirecționarea arhivei OWNER.|
|full_native `runner_v1.py:restore`, `FrontierStore.restore`, `main`|manifest din `store.release.body`, restore sharding/assets. Există versiuni distincte remediation și canonical înghețat; viitoarea selecție trebuie gate explicit activeOID/receipt înainte de restore.|
|critical repair `storage_v2.py:restore`, `RotatingStore.__init__`|`store.anchor.body.current_journal`, shards/snapshots/increments și release tag; trebuie supersedat fallback-ul implicit către release. Constructorul poate crea release; nu este un cititor pur.|
|final recovery `storage.py:Store.decoded/restore`, `restore_snapshot`, `StoreAdapter.__init__`|decriptare asset/hash nu conferă autoritate; `restore_snapshot` înlocuiește local anchorbody și deleagă restore. Necesită selecție autoritate verificată înaintea stării consumate; constructorul nu trebuie folosit ca read-only.|
|continuation1307 `BoundStore.__init__`, `main`; root-cause `evidence.py:main`|snapshot/release prin store/snap.restore; separare istoric de active și interdicție de fallback.|
|autonomous `runtime.py:worker`, `handoff`, `economic`, `main/gate`|worker/handoff refac din anchorbody și pot continua dispatch/broker; economic delegă cititorul OWNER doar în versiunea remediation. Versiunea autonomous înghețată este fixată separat; nu i se atribuie automat gate-ul remedierii. Toate rămân neexecutate, nemodificate și fără reactivare.|
|staging `readers.py:dry_run`|adapter opt-in pentru patru entrypoint-uri; nu este dovada migrării funcțiilor istorice reale.|

Cohorta144 de workflow-uri și inventarul75 de candidați se reutilizează din dosarul recepționat. Nu se inventează o cohortă exact27 și nu se afirmă că29 rânduri de funcții reprezintă29 sisteme distincte.

## Trust root și decizii indispensabile ulterior

[Cerințe auditor independent](AUDITOR_TRUST_ROOT_REQUIREMENTS.md). Nu s-a creat ori controlat principal/cheie/semnătură de auditor. Toate28 BLOCKED sunt păstrate, inclusiv MXM-SEM-G03.2 și dependențele exacte din registrul canonic nemodificat. Progresul noii protecții este raportat separat și nu închide unilateral un contract P0.

Pentru prezenta livrare se cere numai recepția independentă a domeniului și limitelor. Pentru o etapă reală ar rămâne indispensabile, separat: nominalizarea și acceptarea trust root-ului auditorului; aprobarea implementării atomice și supersesiunii consumatorilor cu dovezi/recepție; identificarea principalului issuer și autorizarea exactă a oricărei legări credential/environment ori bypass pe25268790; apoi o autorizație OWNER distinctă pentru bootstrap cu expected ABSENT, candidate exact și termen/scope. Rezolvarea dependențelor globale P0 și a contractelor relevante este precondiție, nu derogare. Niciuna dintre aceste autorizări nu este cerută ca GO acum și nici dedusă din mandatul curent.

## Arhivare și recepție

Artifact12069901999, ZIP2401bytes, SHA256 `c9c48e606e724b681da049deaefa2bb3c0e3de90b46091059c88ced2261c6540`, CRC verificat; bytes integrali păstrați ca [base64](ARTIFACT_RUN38954973739.zip.b64), receipt și teste extrase separat. Git versionat elimină dependența de expirarea90zile Actions pentru aceste dovezi. Candidatul sintetic fără ref a fost citit nativ de runner; obiectele Git fără ref pot fi ulterior colectate, deci nu se garantează recuperarea permanentă a obiectului candidat prin API. Receiptul și identificatorii lui rămân arhivate. [Index](EVIDENCE_INDEX.json), [SHA256SUMS](SHA256SUMS.txt), readback ulterior în `GITHUB_READBACK_RECEIPT.json`. Nicio dovadă nouă confidențială, cheie sau token publicat; capturile de autentificare nu sunt arhivate.

Auditorul este rugat să verifice definiția exactă fără bypass, păstrarea celor opt reguli și OWNER1807, configurația issuer inactivă, bytes/rezultatele runului inclusiv failure, limitele atribuirii422 și update-ului netestat, inventarul și păstrarea28 BLOCKED. Directorul nu emite recepția auditorului.
