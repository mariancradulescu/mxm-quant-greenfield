# MXM — delegare operațională și dovezi native B–C, 19 octombrie 2026

Directorul a instalat și executat succesorii delegați. Dependența lor de review-ul tehnic personal al OWNER a fost eliminată prin instalare administrativă nativă, surse separat sigilate și rută exclusivă către cheia App existentă. Gate-ul personal al vechii surse B nu a fost reinterpretat sau falsificat. OWNER păstrează controlul final și revocarea.

**Verdict limitat:** lanțul operațional al sarcinilor înregistrate are dovezi LIVE pentru autentificare App, drepturile tokenului, excluderea writerului non-App, CAS Git, restaurare rece, reînnoire, handoff, recuperare și oprire. Coada înregistrată s-a încheiat sigur. **Nu se certifică autonomie completă B–E, descoperire științifică nelimitată, profitabilitate sau un cBot validat.** Rezultatele economice sunt criptate; dovezile disponibile nu justifică promovarea unui cBot.

## IMPLEMENTAT

- BC V2: sursa `fe4f0047a6a55866d4f7dcfdcce0f973c21c2f00`, ramura `mxm-o04-successor-code-bc-v2`, sigiliul activ25372645, fără bypass. Patru sarcini: două restaurări OWNER1807, identificare parțială și admitere economică.
- Campanie C V3: sursa `ca99a5ad609a301fef8bd3efe0e902fe3fbe905b`, ramura `mxm-o04-successor-code-c-v3`, sigiliul activ25372928, fără bypass. Migrare exclusiv din predecesorul complet și exact, apoi sensibilitate la ieșiri lipsă, cost incremental și admiterea dovezilor.
- Mediul existent `mxm-p0-successor-issuer-v1` admite acum **o singură ramură, C V3, și zero taguri**. Directorul nu a vizualizat, extras, înlocuit sau multiplicat cheia App existentă; utilizarea machine-side rămâne în runtime-ul sigilat. Mediul are administrator-bypass dezactivat; vechiul gate personal rămâne separat.
- `BC_NATIVE_DELEGATION` este configurație administrativă nativă: sursă/politică/sigiliu/revizii ACL exacte și, pentru V3, checkpointul predecesor. App-ul cu `contents:write` nu are drept de administrare asupra acestei configurații.
- Un token App nou per execuție, limitat la repository1374181010 și numai `contents:write` plus metadata. App5343530, installation172030470 și amprenta cheii existente sunt verificate înaintea utilizării.
- Lease-uri deterministe de60secunde; o sarcină per run, cu identitate nouă și lease ulterior. Autoritatea delegată nu reciclează manifestul expirat al sursei B vechi.
- Git receive-pack cu `--force-with-lease` și părinte exact. `state.json` și `checkpoint.mxmenc` sunt în același arbore atomic. Cheia publică OWNER existentă criptează rezultatele; istoricul păstrează toate checkpointurile.
- Dispatcherul fără chei este instalat pe `main`: cron `7,22,37,52 * * * *`, `workflow_run` la încheierea runtime-ului și dispatch administrativ pentru probe. Nu are rută de bootstrap sau migrare, cheie App sau cheie OWNER.
- Control suplimentar al recuperării: un checkpoint finalizat precede revocarea tokenului, deci dispatcherul cere și succesul jobului issuer nativ anterior, din sursa/workflow-ul/attempt-ul exact. Un issuer eșuat, anulat sau ambiguu oprește reluarea. Schimbarea checkpointului între admitere și dispatch oprește cererea. Handoff-ul direct existent depinde deja de succesul issuerului și de outputul emis după revocare.
- O analiză separată de granularitate a dovezilor rulează cu `contents:read`, fără App și fără writer privilegiat. Rezultatul său criptat este arhivat aici, independent de retenția Actions.

## TESTAT SINTETIC / LOCAL

| Suită | CI nativ | Dovezi |
|---|---|---|
| 18 controale BC V2 |39200443125, job117892121009, SUCCESS|Lease/identitate, intent/replay, expirare, revocare, crash pending, ACL și revizii, criptogramă/stare atomică într-un Git bare local, lipsuri economice|
| 14 controale C V3 |39201735712, job117895943674, SUCCESS|Predecesor exact/revocat, migrare Git cu părinte real și ciphertext vechi păstrat, cold read, stale lease, praguri de missingness, costuri incrementale, izolare fără cheia App|
| 11 controale recuperare |39203347461, job117900805037, SUCCESS|Issuer eșuat după commit, identitate străină/retry, job încă activ, migrare fără primul receipt, wrapperul efectiv cu HTTP controlat, schimbare de checkpoint înainte de POST|

Acestea sunt controale ale infrastructurii și analizei noi, nu rerulări ale experimentului economic acceptat. Simularea revocării sau expirării nu este prezentată drept revocare administrativă LIVE. Testul cu o pauză de zile/un an nu este un an de funcționare observată.

## VERIFICAT LIVE

| Run / job issuer | Sarcină | Lease | Rezultat |
|---|---|---:|---|
|39200719304 /117892941379|Bootstrap unic reușit + prima restaurare OWNER1807|0|SUCCESS; stale CAS respins; checkpoint rece verificat; token revocat204|
|39200840636 /117893296850|A doua restaurare OWNER1807, pornită de Actions|2|SUCCESS; token nou și revocat204|
|39201004913 /117893783876|Identificare parțială a sumarului autentic|4|Issuer SUCCESS și token revocat204; run ulterior CANCELLED în proba de handoff|
|39201180575 /117894292035|Admitere economică BC V2|6|SUCCESS; oprire sigură fără calificare cBot|
|39202097721 /117897050766|Migrare V2→V3 + missingness frontier|0|SUCCESS; arhiva predecesorului verificată rece; zero bootstrap nou|
|39202289857 /117897637701|Sensibilitate la costuri, după recuperare separată|3|SUCCESS; token nou/revocat204; checkpoint rece verificat|
|39202471435 /117898179766|Admiterea dovezilor C V3, pornită de Actions|5|SUCCESS; token revocat204; stare terminală sigură|

App-ul a autentificat identitatea și instalarea reale, a solicitat și verificat tokenul restrâns și a confirmat revocarea204 în fiecare dintre aceste șapte execuții. Restaurările B au citit efectiv release412686323/asset642889915 și jurnalul OWNER1807 cu hashul acceptat; nu s-a pornit campania istorică.

**Excludere de writer:** run39202905071, job117899482891, SUCCESS. Tokenul obișnuit al workflow-ului avea `contents:write`, fără cheia App. O tentativă de append liniar, cu arbore identic și părinte exact, a fost respinsă nativ cu **GH013**. Head-ul autorității și OWNER1807 au rămas neschimbate. `NATIVE_WRITER_EXCLUSION_RECEIPT.json` păstrează identitatea candidatei respinse.

**Migrare fără bootstrap:** commitul `4a21c352eb2d4b5896830c16511dbf9df7e3c29f` are exact părintele `aecad00a5aa2785a6860748842803de9d2ed1c35`, ultimul checkpoint V2. Arhiva criptată V3 conține și jurnalul public/privat V2 verificat. Migrarea respinge alt head, predecesor incomplet/revocat/pending sau o reluare după mutarea head-ului.

**Recuperare efectivă:** în run39202097721 s-a omis intenționat numai handoff-ul imediat, după checkpoint și revocare. Dispatcherul separat39202272410/job117897588531 a emis `ORDINARY_CONTINUATION_DISPATCHED`, `bootstrap_dispatches:0`; Actions a pornit39202289857 din checkpointul Git existent. Lansarea probei de recuperare a fost administrativă; nu este prezentată drept cron observat.

**Oprire efectivă și trezire automată:** cererea negativă39203173927/job117900287999 a fost refuzată cu `BC_REGISTERED_RESEARCH_COMPLETE_INSUFFICIENT_EVIDENCE`, fără claim nou sau reexecutare științifică. Evenimentul nativ **workflow_run** a pornit automat39203216358/job117900411294; acesta a verificat succesul ultimului issuer acceptat și a păstrat starea terminală cu `bootstrap_dispatches:0`. Verificarea administrativă39203045092/job117899904771 confirmă același control.

**Read-only independent:**39201735704/job117895943491, SUCCESS. Token `contents:read`, `app_key_used:false`, `checkpoint_writer_used:false`, `accepted_experiment_replays:0`. Ciphertext SHA256 `48e915d1706d6a08f445feb6c77defd46d998eb1ead39169f178da2d0bc08bc7`; arhiva ZIP este păstrată aici.

## Istoric, corecții și limite ale probelor

Runul vechi39147483523 este **completed/cancelled**, attempt1, `approvals=[]`. A fost închis înainte de un nou bootstrap de autoritate. Gardianul administrativ de expirare devenit inutil a fost dezactivat manual de Director; UI confirmă «This workflow was disabled manually.». Codul și receiptul istoric sunt păstrate. Manifestul vechi nu se reînnoiește și nu este reutilizat de succesorii delegați. Vechea sursă B `95fc312a84f803276a408ca4f821a09b007e56b0` și sigiliul25313453 sunt păstrate.

BC V1, sursa9527c32a19416da289e4c05e2ed7a0d55f67a4b1, a eșuat în run39200166907 cu `BC_NATIVE_RULE_ACTORS`, înainte de crearea autorității. API-ul ascunde actorii de bypass tokenurilor fără acces de scriere la ruleset. V2 păstrează privilegiile App restrânse și leagă snapshotul administrativ complet de revizia nativă și câmpurile vizibile curente; o revizie schimbată oprește execuția. Nu se interpretează un câmp absent drept listă goală. V1 și sigiliul25372506 rămân în istoric.

Proba de anulare a handoff-ului V2 a prins o cursă: dispatch-ul fusese deja transmis înaintea anulării. Runul39201215182 a detectat workerul existent și a suprimat duplicarea. Aceasta probează suprimarea duplicatelor, nu recuperarea unui handoff pierdut; proba separată V3 de mai sus demonstrează acea recuperare.

Primele două înregistrări ale workflow-ului read-only,39201667111 și39201676292, au fost respinse la validarea YAML, fără joburi sau analiză executată. Sintaxa a fost reparată înaintea sigilării sursei C V3; runul unic de analiză ulterior39201735704 a reușit.

Tokenurile au fost revocate înainte de expirarea lor naturală; nu s-a așteptat literal o oră pentru expirarea unui token. Sunt observate tokenuri noi, revocări reale și lease-uri expirate/reînnoite între runneri reali. Cronul periodic este configurat; o execuție cu event `schedule` nu era încă observată la această verificare. Trezirea automată prin `workflow_run` este observată LIVE. Disponibilitatea și programarea serviciului GitHub rămân dependențe ale platformei.

## ÎNCĂ BLOCAT / NEFINALIZAT

Promovarea unui cBot este blocată de suportul empiric incomplet: ieșiri complete pentru populația declarată, comparatori cu eligibilitate comună, costuri istorice/executabilitate și risc susținute de date, plus confirmare independentă sau inferență care ține cont de selecția adaptivă. Analizele agregate de sensibilitate nu furnizează aceste dovezi și nu justifică inventarea ieșirilor sau costurilor reale.

Coada înregistrată s-a încheiat; nu rulează acum o căutare nelimitată de ipoteze. Universul autorizat de cercetare nu este declarat epuizat. Următoarea definiție științifică justificată rămâne în mandatul Directorului și poate utiliza succesiune versionată, protejată și ancorată în checkpoint; nu necesită transformarea OWNER în reviewer sau operator. O definiție nouă nu este echivalentă cu un nou bootstrap. B–E integral și cBot-ul validat offline rămân obiective deschise.

Revocarea administrativă reală a instalării/cheii/grantului și un crash de producție cu intent pending nu au fost injectate deliberat. Controalele lor sunt implementate și testate sintetic; nu se declară acele scenarii verificate LIVE. Un pending sau ACK ambiguu cere oprire și investigație, fără repetarea operației.

## Starea durabilă și controlul final

Head activ final: `07d1ddbe0b83753bbf189770af1911623fef8d6f`; sequence3 V3, pendingnull, `REGISTERED_RESEARCH_COMPLETE_INSUFFICIENT_EVIDENCE`. Ciphertext final SHA256 `9e00d40aa8ba5038c15518e97b227defb7bb67b9cba130d02a3feec2a2c028e8`.

OWNER1807 rămâne `a830c132521bd4348454653f713e04f6107484fe`, jurnal `ea93f6c38768824521d4ad3e316c0cd507c837e5c089c5e3b6f63d20d79e7470`. Regula25268790 admite numai Integration5343530/always pe exact `refs/heads/mxm-o04-active-v1`. Regula independentă25222248 rămâne activă, fără bypass și cu revizia16octombrie neschimbată. Protecția OWNER25222426 rămâne activă.

Checkpointurile criptate sunt în istoricul Git protejat și au copii criptate verificate în acest pachet; reluarea nu depinde de fișierele sesiunii ChatGPT sau de retenția artefactelor Actions. Directorul a exercitat administrarea și evaluarea tehnică delegate. OWNER păstrează dreptul final de supraveghere/revocare prin instalarea App, grant și ruta sursei. Zero ordine, tranzacții reale sau furnizori noi; zero review-uri personale fabricate; zero rescrieri ale surselor acceptate.
