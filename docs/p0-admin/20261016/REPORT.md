# MXM Director — verificare administrativă P0 limitată, 16.10.2026

**Rezultat: dovezi administrative obținute; NO GO operațional.** OWNER a confirmat recepția independentă a pregătirii P0 la `3bd053a3b23bc94ab90d5ee66e1f466483fb42cb` și a autorizat numai citirea administrativă și publicarea raportului. Recepția acestui raport rămâne auditorului. Nu au fost relansate O04.2, cele 29 teste P0 ori auditurile anterioare.

## Dovezi și metodă

Inspecție în GitHub Work, cu contul legitim existent. GitHub a cerut reconfirmare sudo pentru pagina de acces; aceasta a fost finalizată prin fluxul securizat GitHub Mobile. Nu au fost acordate permisiuni, create credențiale ori modificate setări. Autentificarea nu este confundată cu un grant nou.

[Observații UI public-safe](UI_OBSERVATIONS_PUBLIC.json), cu URL-uri și timpi UTC; [cele opt rulesets native](NATIVE_RULESETS.json); [matricea referințelor](REFERENCE_SCOPE.json); [delta P0](P0_EVIDENCE_DELTA.json); [SHA256SUMS](SHA256SUMS.txt). Observațiile UI sunt consemnări ale executantului din DOM/AX, nu exporturi JSON native ori semnături independente. Nu se publică capturi, IP-uri, locații, emailuri, valori secrete, tokenuri sau PEM.

## Configurație efectivă observată

| Suprafață | Observație administrativă |
|---|---|
| Actions 7689 | **Active**;145 ținte =144 istorice + fixture de deny; restrict actors/events bifate, liste permise goale |
| Amprentă ținte | UTF-8, ordinea UI, LF și LF final: `fa3edaf81aefaaafcc108119cfb7729918020e17bc55010a95c6aabc95c90d35`; coincide cu inventarul fix păstrat plus fixture |
| Excepții native | UI precizează Dependabot, code scanning, Codespaces prebuilds și Pages exceptate; nu se declară deny universal al tuturor serviciilor |
| Actions generale | Allow all actions/reusable workflows; SHA pinning global nebifat; default GITHUB_TOKEN contents/packages read; creare/aprobare PR de Actions nebifată |
| Forkuri / retenție / runners | Aprobare pentru first-time contributors; retenție90 zile; niciun self-hosted runner configurat |
| Colaboratori / deploy keys | **0 / 0**, confirmate în paginile administrative |
| App staging | Instalare172030470; metadata read, contents write; numai repository1374181010; buton Suspend vizibil, coerent cu instalare activă |
| Integrare Codex | Instalare158943705; read checks/statuses/metadata; write actions/contents/issues/PR/workflows pentru proiect. Nu este acceptorul dedicat |
| Environment staging | Exact `mxm-o04-issuer-code-v3`,1 branch/0 tags; fără bypass administrativ; required reviewers și wait timer nebifate |
| Custodie environment | Doar metadate: secret App + canary;2 variabile de configurare. Nicio valoare secretă citită. Code-freeze rule25232285 și custody run38885755596:2 |
| Protecții clasice | **Nu sunt configurate**, conform UI;403-ul anterior nu mai este tratat ca incertitudine asupra existenței lor |
| Rulesets | Opt active, toate pentru branch refs O04; fără required status checks/PR/signed-commit rule în setul observat |

Setările generale Actions de mai sus sunt fapte, nu o cerere de hardening global sau o dovadă că orice workflow are efectiv write. Permisiunile pot fi declarate per workflow; politica 7689 privește numai țintele sale. Nicio setare nu a fost schimbată.

## Frontierele reale ale protecției

| Referință | Reguli aplicabile | Concluzie limitată |
|---|---|---|
| OWNER accepted1807 |25222426 +25222248 | Creation/update/delete blocate, fără bypass; append-only/linear |
| Stage authority |25231211 +25222248 | Creation/update numai App 5343530; append-only/linear separat |
| Issuer v3 |25232285 +25222248 | Source freeze fără bypass; append-only/linear |
| Issuer v1/v2, preflight v1/v2 | Freeze exact +25222248 | Surse înghețate, fără bypass |
| Canonical / autonomous / remediation | Niciunul dintre cele opt; protected=false în metadata | Nu sunt protejate global de regulile O04; nu se deduce exclusivitate pentru writerii istorici |
| Viitorul `mxm-o04-active-v1` | Numai25222248; GET404 | Nu există; lipsește regula exclusivă de creation/update. Append-only singur nu este autorizație exclusivă |

Aceasta este derivare din condițiile native și UI, **nu test de scriere**. Nu s-a creat referința activă și nu s-a trimis nicio probă de write. Interfața confirmă bypass gol pentru freeze OWNER și numai App staging pentru autoritatea staging; cele opt JSON-uri native au rămas integral identice între citirile înainte/după.

Regulile de branch nu sunt prezentate drept protecții ale body-urilor Releases. O politică de execuție pe145 căi nu revocă tokenurile externe și nu transformă toate rutele istorice în cititori. App are Contents:write la nivel de repository, nu un scope nativ de branch. Izolarea acceptată staging rămâne compoziția ACL + issuer înghețat + credential neexportat + cititor fixat, conform recepției existente; probele ei nu au fost repetate.

## Ce incertitudine a fost eliminată și ce rămâne

Lipsa accesului administrativ nu mai este o explicație generală pentru blocaj. Configurația scoped a fost citită legitim fără escaladarea privilegiilor. Componenta de vizibilitate N10.1 are acum dovezi. Directorul nu o transformă unilateral în recepția întregului contract; [toate cele 28 BLOCKED rămân neschimbate](P0_EVIDENCE_DELTA.json).

Rămân concrete: autoritatea reală absentă și încă neizolată pentru creation/update; issuer/gate/consumatori reali neinstalați; trust root/principal auditor independent neinstalat în mecanismul real; rutele istorice mutable fără supersesiune recepționată. Permisiunile personale ale OWNER rămân limita de guvernanță; zero colaboratori și zero deploy keys nu sunt un inventar al tuturor credentialelor personale sau o dovadă a inexistenței lor.

Jurnalul personal de securitate este accesibil și arată evenimente repository/ruleset/environment. Căutarea limitată pentru release a afișat în continuare evenimente de environment/ruleset; nu a furnizat martorul exact al mutațiilor istorice de body cerut de N25.4. Nu se pretinde că filtrul produce un inventar exhaustiv, că martorul nu există ori că vreun actor este vinovat. S-au păstrat doar tipuri de evenimente și limita probei, fără metadate private de rețea.

N32.4/N34.4 cer martori istorici de date/cache, nu setări GitHub. Citirea administrativă sau un drept nou nu îi fabrică. Remediul minim pentru aceste lipsuri este originalul autentificat dacă există, ori o decizie scoped a recepției independente asupra limitării; nu o certificare inventată de Director.

## Numai deciziile suplimentare indispensabile

1. **Recepția independentă a acestui dosar administrativ**, cu adjudecarea exactă a componentelor N10 pentru care dovezile sunt acum disponibile. Nu este necesară o nouă permisiune administrativă pentru a repeta aceleași citiri.
2. Dacă OWNER alege continuarea pregătirii: **aprobare punctuală pentru implementarea/configurarea frontierei reale**, cu regula NOUĂ creation/update exclusiv App pe referința viitoare, sursa issuer real înghețată, workload/environment exact și trust root/receipt auditor administrat independent. Se pot păstra permisiunile App existente; nu se solicită Administration pentru App, collaborator write nou sau relaxarea regulilor înghețate. Probele native de write pe o frontieră viitoare ar necesita scope separat explicit; nu sunt autorizate/executate aici.
3. **Decizia de supersesiune pentru consumatorii/rutele istorice afectate**: autoritate unică fixată, release/side refs fără autoritate operațională și migrarea ori blocarea punctuală necesară. Dacă se cere în schimb imutabilitate globală pentru toate ramurile/release-urile istorice, aceasta nu este furnizată de configurația actuală și cere un scope distinct explicit. Nu se reactivează writerii istorici.
4. **Bootstrapul real și orice GO operațional rămân o aprobare OWNER ulterioară separată**, după implementarea și recepția frontierelor de mai sus. Acest raport nu cere pornirea campaniei.

Nu se propun audituri generale noi, schimbări globale de Actions, chei de broker, scope-uri de piață ori infrastructură nouă.

## Conservare și publicare

Bază: `3bd053a3b23bc94ab90d5ee66e1f466483fb42cb`. Singura mutație autorizată a acestei etape este publicarea documentelor și actualizarea continuității pe ramura de remediere existentă. Niciun workflow/cod/configurare nu se schimbă.

OWNER STOP rămâne `a830c132521bd4348454653f713e04f6107484fe`; staging `c6644174244cd92b8e41b17f241b8f5e545fddd9`. Release412686323 are body identic înainte/după; jurnalul642889915 nu a fost descărcat/decriptat. Starea observată înaintea publicării: queued=0 / in_progress=0. Recepția P0 precedentă este confirmată de OWNER la 3bd; nu este inventat un proces-verbal semnat nou.

**163 PASS /28 BLOCKED**, fără reclasificări. `STAGED_READY_STOP_ONLY`; OWNER accepts=false, restart=false, production=false, research=false. Fără teste relansate, checkpointuri reale noi, broker I/O, colectare, backtesting economic, cBot, Cloud, ordine sau restart.
