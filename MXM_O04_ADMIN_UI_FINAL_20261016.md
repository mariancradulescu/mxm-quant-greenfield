# MXM O04.1 — izolare globală verificată în starea STOP

**Verdict al executantului: VERIFIED_GLOBAL_STOP.** Writerii istorici identificați sunt izolați prin politică GitHub la nivel de repository, iar registrul care fixează checkpointul 1807 este înghețat fără bypass. Mecanismul CAS/fencing a fost verificat pe referințe sintetice reale din același repository. **Nu este activat un writer de campanie sau un flux de acceptare de checkpointuri noi.** Recepția independentă a O04.1 și certificarea platformei nu sunt declarate prin acest raport.

16 octombrie 2026. Repository existent: `mariancradulescu/mxm-quant-greenfield`. Acest raport înlocuiește concluzia administrativă anterioară, bazată numai pe integrarea care răspundea 403. Nu reauditează cele 191 de contracte și nu schimbă unilateral matricea 163 PASS / 28 BLOCKED.

## 1. Acces legitim și conservarea conexiunii cTrader

Browserul Work a fost autentificat prin fluxul securizat GitHub și verificările de dispozitiv aprobate de proprietar. Nu au fost extinse permisiunile integrării și nu au fost extrase credențiale din browser. Limitarea 403 a integrării există în continuare; administrarea s-a efectuat legitim prin UI.

UI a confirmat: zero chei deploy; zero colaboratori; o singură aplicație instalată, ChatGPT Codex Connector. Permisiunea implicită Actions era deja de citire, iar aprobarea PR-urilor de către Actions era dezactivată. Nu existau protecții clasice de branch sau ruleset-uri. Allow-all pentru dependențele Actions și retenția nu au fost modificate.

Cele cinci secrete existente sunt păstrate: `CTRADER_ACCESS_TOKEN`, `CTRADER_CLIENT_ID`, `CTRADER_CLIENT_SECRET`, `CTRADER_REFRESH_TOKEN`, `MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM`. Au fost citite numai numele și datele de actualizare din listă, fără editare, ștergere sau acces la valori. Proiectul folosește cTrader Open API, OAuth și scope-urile existente, asociate contului Pepperstone LIVE nealimentat. Nu s-a realizat autentificare directă la Pepperstone, reconectare la broker sau schimbare de scope.

## 2. Controale globale aplicate și verificate

| Control | Domeniu și stare efectivă |
|---|---|
| [Actions policy 7689](https://github.com/mariancradulescu/mxm-quant-greenfield/settings/actions/rules/7689) | **Active**. Exact 144 de căi istorice care au declarat `contents: write` sau `actions: write`, plus o probă sintetică inofensivă. Niciun actor și niciun eveniment permise pentru aceste căi. Regula nu este limitată la ramura succesoare. |
| [Ruleset 25222248](https://github.com/mariancradulescu/mxm-quant-greenfield/settings/rules/25222248) | **Active**, `refs/heads/mxm-o04-*`. Fără bypass; refuză ștergerea și non-fast-forward, impune istoric liniar. |
| [Ruleset 25222426](https://github.com/mariancradulescu/mxm-quant-greenfield/settings/rules/25222426) | **Active**, `refs/heads/mxm-o04-accepted-*`. Fără bypass; refuză crearea, actualizarea, ștergerea și non-fast-forward, impune istoric liniar. Interdicția de creare a fost activată după fixarea registrului și a fixture-ului de probă. |

Politica este o listă exactă de căi, fără glob care să blocheze toate verificările de citire. `mxm-o04-fencing-evidence-20261016.yml` rămâne în afara acestei liste și are garduri pentru repository, ramură, actor, prima încercare și namespace sintetic. Numai jobul probelor Git sintetice primește temporar `contents: write` prin tokenul nativ Actions; nu primește vreun secret cTrader/OWNER. Celelalte joburi au citire.

Exporturile JSON descărcate din GitHub sunt incluse în pachet. După salvare, starea Active, țintele și lipsa bypass-ului au fost reverificate. API-ul operatorului raportează și `current_user_can_bypass: never`. Politica împiedică intrările istorice identificate; protecția registrului acceptat se aplică tuturor principalilor de scriere, indiferent de calea workflow-ului, cât timp regulile rămân active. Administratorul care modifică intenționat regulile este autoritatea de configurare, nu un writer de checkpoint autorizat prin acest mandat.

## 3. Autoritatea fixată și semnificația stării STOP

Registrul nou este la branch `mxm-o04-accepted-owner-1807-v1`, commit **`a830c132521bd4348454653f713e04f6107484fe`**. Conține numai `state.json` și `README.md`; nu conține workflow-uri sau date private. El înregistrează prin referință checkpointul original, fără rescriere sau decriptare:

- generație `1807`, `STOP_FAIL_CLOSED`;
- release original `412686323`, activ jurnal `642889915`;
- SHA256 canonic jurnal `ea93f6c38768824521d4ad3e316c0cd507c837e5c089c5e3b6f63d20d79e7470`;
- SHA256 corp release `01a6d82498c033131302b272ee4ba2f83c4e445f40585f76dfee1a91466679b9`;
- `checkpoint_writes_allowed: false`, `campaign_restart_allowed: false`, `scientific_certification: false`.

Regula globală de update nu permite nici conexiunii operatorului să mute această familie de referințe. Crearea altor referințe în namespace-ul acceptat este acum refuzată. O referință creată în alt namespace nu devine această autoritate: proba curentă fixează explicit numele și OID-ul de mai sus.

`Releases PATCH` **nu a devenit CAS** și nu se revendică acest lucru. Registrul fixează identitățile/digesturile acceptate; verificarea adăugată în cod compară înainte și după probe OID-ul registrului, modul STOP, protecția de update, digestul corpului release și digestul jurnalului. O schimbare incompatibilă duce la refuz. Writerii istorici nu au fost migrați într-un flux de acceptare activ: sunt izolați. Datele istorice rămân la locul lor, iar campania rămâne oprită.

Aceasta este închiderea problemei prin **izolare globală și autoritate înghețată**, opțiune autorizată de proprietar. Nu este demonstrarea unui serviciu de producție care acceptă checkpointuri noi în timpul cercetării. Nu se poate deduce un GO pentru reluarea campaniei din rezultatul de siguranță STOP.

## 4. Fencing atomic real, cu reutilizarea codului verificat

Baza `4a9e46c956efba430ae03633f1ce771f1daf1266` a fost reutilizată. `live_proof.py` adaptează transportul la GitHub și moștenește neschimbate operațiile `claim`, `accept`, `resolve` și publicarea CAS din `GitFenceLab`. Transportul este restrâns la `refs/heads/mxm-o04-proof-<run_id>`, exclusiv date sintetice. Nu poate alege branchul OWNER sau un release ca țintă.

Fiecare tranziție construiește un commit copil al OID-ului așteptat și cere comparația explicită a vechiului OID în `git push --force-with-lease=REF:EXPECTED`. Serverul Git execută actualizarea condiționată. Regulile GitHub refuză rollback-ul chiar și când clientul cere force. Claimurile și preluările cresc epoca; acceptarea verifică OID, epocă, writer, lease și versiune. Digesturile acceptate sunt aditive, iar operațiile nu sunt reluate după un ACK incert fără readback exact. Referință tehnică primară: [documentația Git push](https://git-scm.com/docs/git-push).

Două sesiuni remote distincte au concurat pe același părinte. Acesta nu este un mock de API, un mutex SQLite local sau un concurrency group Actions. Valorile timpului/lease-ului din scenariile sintetice sunt controlate de test; respingerea CAS are loc pe serverul GitHub. Recuperarea verificată creează un client și un workspace Git noi după un ACK pierdut injectat; nu se revendică oprirea forțată a unui runner de producție.

## 5. Rezultatele negative și dovezile lor

| Probă | Rezultat |
|---|---|
| Doi writeri remote, aceeași versiune | Exact unul `ACCEPTED`, celălalt `REJECTED`. |
| Writer întârziat după epocă nouă | Refuz în mașina de stări și refuzul unui push remote cu OID vechi, chiar ocolind precheck-ul clientului. |
| Întrerupere/ACK pierdut după acceptare | Client nou citește acceptarea de pe server; replay respins. |
| Suprascriere checkpoint sintetic acceptat | Versiunea refuzată, digestul anterior păstrat. |
| Principal absent din grantul sintetic | Refuz înaintea acceptării. |
| Token Actions fără scriere | PATCH către referința sintetică: **HTTP 403**, OID neschimbat. |
| Rollback cu tokenul de scriere | Refuz de ruleset GitHub, verificat în răspunsul serverului. |
| Operator cu acces de scriere încearcă să actualizeze un registru sintetic înghețat | **Cannot update this protected ref**; înainte/după `9f11842b1d95fc63c61019993ca893819fe61852`. Reguli identice cu registrul OWNER. |
| Creare autoritate sintetică suplimentară după închiderea namespace-ului | HTTP **422 Reference update failed**; GET ulterior **404**. Ruleset-ul activ include explicit regula `creation`. |
| Proba sigură vizată de politica Actions | Startup failure înaintea alocării unui job. UI: actorul și evenimentul push nu sunt permise; API jobs este gol. |

Proba politicii nu conține checkout, secrete, rețea sau scriere: ar fi emis numai un mesaj fix dacă politica ar fi eșuat. Nu a fost rerulat un workflow istoric de campanie pentru a încerca protecțiile.

## 6. Commituri, Actions și artefacte

- `cbc20518ee5ad29aef1877254a1a50238fc4c571`: adaptorul GitHub sintetic și probele sigure.
- `8e6483765453efe0642f29de5632efab19c24d05`: tratarea corectă a câmpurilor administrative omise din răspunsul tokenului Actions. Prima rulare se oprise înainte de orice scriere, cu `KeyError: bypass_actors`; nu au fost acordate drepturi administrative tokenului pentru a elimina eroarea.
- HEAD de cod testat **`7b7ae28317dad0fcd1e33cf46e3b323d91e25d87`**: verificarea registrului STOP și separarea raportării drepturilor tokenului de verdictul UI.
- [Diff de cod față de baza verificată](https://github.com/mariancradulescu/mxm-quant-greenfield/compare/4a9e46c956efba430ae03633f1ce771f1daf1266...7b7ae28317dad0fcd1e33cf46e3b323d91e25d87).
- [Run final `38863652744`](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/38863652744): **completed / success**. Joburile `116851433517`, `116851568446`, `116851701209` sunt SUCCESS. Opt teste locale izolate plus probele GitHub și verificarea registrului STOP.
- [Refuzul politicii, run `38863049346`](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/38863049346): refuz actor/eveniment, zero joburi.

| Artefact final | SHA256 ZIP verificat după descărcare |
|---|---|
| `12030014034` — teste, inventar și vizibilitatea tokenului | `4716c69dc7df8fabb932d43b6d59b44e24c21fcd5cdf429e36a2d41a5b63b399` |
| `12029668077` — CAS remote și registrul STOP | `844316fb3ef0237865518433a0c8ad3b545993d43f008bed8cfc03ee419c1200` |
| `12029593231` — token fără grant | `47e67593e6cae38d43f6e650c9fb1e5a8aa3fb1ad48b6e4112c7ec3f69fd9bf0` |

Exporturile administrative, răspunsurile operatorului, jurnalele joburilor, receipt-urile, inventarul și verificările de conservare sunt în pachet. Inventarul din run final surprinde 79 de ramuri înainte de crearea celor două referințe sintetice ale acelei rulări; starea finală are 81. Cele 397 de taguri sunt neschimbate. Cele 144 de căi istorice sunt derivate din cele 290 de versiuni care declarau contents/actions write în inventarul de bază, nu dintr-o presupunere despre toate cele 714 versiuni.

## 7. Conservare și verdict de recepție

Corpul release-ului original este identic înainte/după. Nicio cheie OWNER nu a fost încărcată în probele noi, niciun activ OWNER nu a fost decriptat sau rescris. Au fost create numai referințe de siguranță și fixture-uri sintetice în repository-ul existent.

Din cele 75 de ramuri ale bazei, 74 au OID neschimbat. Singura modificată este ramura autorizată de remediere. `main` rămâne `982dbbedcf7ec26ccbea47bde33bc40e39ebc038`; canonical `9c5f9f1b7f2d73f98bb188a2651fd9a3c00df6b9`; autonomous `3cb073e54fe3189063c2737c6337d3404b713710`. Nu s-au declanșat joburi istorice, nu s-au efectuat colectări, cercetare alpha, backtesting economic, ordine, cBot, Cloud sau protected forward. Raportul celor 191 și codul remedierilor anterioare nu au fost modificate; testele nu reprezintă acceptare economică.

**O04.1 este prezentat auditorului ca izolare globală verificată pentru starea STOP**, cu autoritatea existentă fixată și imposibil de suprascris printr-un writer obișnuit, inclusiv prin conexiunea operatorului, cât timp controalele verificate sunt active. Nu revendicăm o funcție de acceptare de checkpointuri noi sau promovarea datelor necunoscute. Auditorul decide recepția și orice actualizare a matricei; platforma nu este declarată certificată.

Notă de trasabilitate: o politică inițială care ar fi vizat aproape toate workflow-urile a fost respinsă de revizuirea automată ca întrerupere prea largă. Nu a fost salvată și nu a fost ocolită respingerea. A fost înlocuită cu politica material mai restrânsă, verificabilă, pe cele 144 de căi de writer și o singură probă sigură. Nu rămâne o cerere de aprobare pentru acea configurație abandonată.
