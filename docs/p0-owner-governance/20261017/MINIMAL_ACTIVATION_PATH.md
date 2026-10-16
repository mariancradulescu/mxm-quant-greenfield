# O singură cale minimă: OWNER critic → issuer unic protejat → checkpointuri delegate

Decizia OWNER actuală elimină custodele/cheia auditorului extern. Nu se cere înrolarea MXM-OWNER-AUDITOR-ENROLLMENT-001. Auditorul din conversația separată recepționează read-only etapele critice; nu semnează checkpointuri și nu deține autoritate de scriere. Directorul nu poate transforma propriul raport sau actorul unui run într-o aprobare OWNER.

## Ce este deja disponibil și nu se repetă

O04.2 staging are App/issuer/custody și probe CAS recepționate numai staging; OWNER1807 este fixat;25268790 blochează exact active-v1 fără bypass; autoritatea reală nu există. Modelul Git receive-pack CAS, anti-replay/readback și checkpoint recovery au dovezi acceptate. Selectorul/adaptoarele izolate și matricea10/29 sunt recepționate sintetic. Citirile administrative au furnizat deja vizibilitatea N10.1; vechiul403 nu mai justifică o nouă cerere generală de acces sau reaudit.

## Implementarea nouă minimă

G03.2-R2 cere un manifest critic cu hash exact, source SHA, policy SHA256, referința recepției read-only, operation ID, root OWNER1807 și fereastră finită. Un review nativ GitHub trebuie să fie approved de OWNER322088485, pentru exact environment/run/source/workflow și cu comentariul explicit `MXM_OWNER_CRITICAL_APPROVAL_V2 sha256=<manifest>`. Istoricul ambiguu, rerun, respingere ori comentariu generic sunt refuzate. Commit author/run actor/JSON approved_by_owner nu sunt aprobări.

Mecanismul citește numai GET /actions/runs/{id} și /approvals. Nu există approve/POST, cheie auditor sau signer. Bindingul run/environment/source/manifest trebuie să provină din configurația acceptată, nu dintr-un payload al clientului. Semantica API și review-urilor sunt documentate oficial la https://docs.github.com/en/rest/actions/workflow-runs#get-the-review-history-for-a-workflow-run și https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/review-deployments .

Odată aprobată politica, checkpointurile obișnuite folosesc exclusiv principalul/ref/source/epoch acceptate, generații finite, deadline și budget payload fixe. Nu necesită review uman sau semnătură auditor per checkpoint. Limitele reale de cereri/date/campanie vor fi fixate în politica de execuție acceptată; modelul actual autorizează numai pregătire sintetică CHECKPOINT_ONLY și nu acordă acces la piață sau cercetare.

Un review nativ verificat este o observație de autorizare, nu o autoritate deja activată. Grantul real trebuie instalat atomic în head-ul unic, cu manifest/policy hash și epoch; joburile ordinare trebuie să citească acel head și să refuze un grant absent, diferit ori nearmat. Un review al unui run eșuat/cancelled înaintea commitului grantului nu îl armează singur. Această instalare și legare reală nu există în modelul de pregătire și nu este declarată implementată.

Jurnalul deja recepționat este reutilizat, fără schimbare, pentru head/parent/epoch/intent și o cheie atomic unică per generație; nu este introdus alt store. O generație nu poate fi pregătită din nou sub alt intent. Fencingul atomic nativ Git nu este înlocuit de SQLite: integrarea publisherului real lipsește încă și rămâne închisă. Recuperarea după ACK incert rămâne readback exact și STOP, fără retry orb; o intervenție de reset/recovery în afara politicii cere OWNER critic.

## Două aprobări OWNER viitoare, fiecare la frontiera ei

**A — instalare tehnică exactă, fără pornirea cercetării.** După recepția acestei adaptări, OWNER poate autoriza un singur pachet tehnic concret, fixat prin SHA, care cuprinde:

- issuerul/publisherul succesor unic, cu Git ref update atomic expected-oldOID, sursă înghețată și admiterea exactă la credentialul App existent. Nicio cheie nouă ori permisiune Administration pentru App;
- autorizarea explicită a bypass-ului **numai App existent** pe25268790, păstrând append-only și toate freeze-urile existente. Fără creare active-v1 sau checkpoint OWNER nou în acest pas;
- un singur gate GitHub de review OWNER pentru operațiuni critice, fără secret și fără admin bypass. Este o funcție nativă GitHub, nu serviciu/rol/cheie nouă; este necesar pentru a avea dovadă de autorizare din afara fișierelor Directorului;
- accesul automat al issuerului la credential se face separat de gate-ul uman, astfel încât gate-ul nu rulează pe fiecare checkpoint. Orice schimbare necesară a admiterii noului issuer înghețat la environment-ul existent trebuie enumerată și aprobată explicit; environment-ul staging actual și sursele înghețate nu se ating în mandatul de față. Nu se presupune că secretul poate fi exportat sau copiat;
- o singură integrare în pipeline-ul succesor, cu patru frontiere restore/worker/handoff/economic. Nu este necesară editarea celor26 versiuni istorice: acestea rămân arhivă/inactive și nu mai pot fi selectate implicit de noul pipeline. Lista exactă de fișiere/callsite-uri care intră în succesor se prezintă în pachet înainte de autorizare;
- verificarea nativă numai a diferenței instalate, cu controale sigure explicit autorizate și readback, reutilizând O04.2 și probele acceptate. Nu se reia proba422, iar run38954973739 rămâne FAILURE și neatribuit concludent.

Gate-ul cere contul OWNER ca reviewer; opțiunea GitHub Prevent self-review nu poate fi impusă orbește dacă singurul OWNER inițiază și aprobă operația. Nu se introduce altă identitate doar pentru a ocoli această constrângere. Actorul inițiator nu este niciodată folosit ca aprobare. Directorul nu va utiliza UI/API pentru a aproba în locul OWNER. Configurația efectivă și politica de acces la cont trebuie recepționate în pachetul A.

**B — activare explicită, după recepția read-only a instalării.** OWNER decide separat dacă autorizează bootstrapul exact și delegarea checkpointurilor ordinare în politica finită acceptată. Dacă se dorește și cercetare autonomă, actul de activare trebuie să o autorizeze explicit, cu limitele științifice/date/cereri/termen și excluderile stabilite; nici bootstrapul singur, nici G03.2-R2 nu acordă implicit research GO. Aceste scope-uri critice pot fi prezentate în același pachet final OWNER complet, fără aprobări repetate pe checkpoint. La pregătirea acelui pachet nu se vor folosi drept PASS lipsurile istorice rămase UNKNOWN/BLOCKED.

Nu există A sau B aprobate acum. Niciun pas de configurare live, bypass, bootstrap, migrare operațională ori cercetare nu a fost executat de această etapă. Nu se cere o aprobare separată pentru custode, cheie auditor, servicii noi, repetarea auditului sau fiecare checkpoint.

## Limita de guvernanță acceptată, fără promisiuni false

GitHub autentifică un cont; nu poate identifica fizic operatorul unui cont accesibil atât OWNER, cât și Directorului. Codul nu acceptă autoatestări și nu poate aproba, dar aceasta nu este o separare criptografică împotriva unui executant care ar controla complet contul/administrația OWNER și ar încălca mandatul. Acest risc este declarat, nu folosit ca pretext pentru a reinstala custodele refuzat de OWNER. Review-ul uman, controlul sesiunii OWNER și sursa executabilă protejată rămân frontierele modelului ales.

## Ce nu trebuie confundat cu infrastructura lipsă

N25.4/N32.4/N34.4 și celelalte dovezi istorice nerecuperate nu pot fi fabricate prin aprobare nouă ori test sintetic. Nu sunt chei/permisiuni pe care să le mai instalăm. Ele blochează certificarea istorică sau utilizarea domeniului de date afectat, conform contractelor lor; nu se afirmă că originalele sunt definitiv distruse. Corpusurile fără proveniență rămân carantinate/UNKNOWN. Un eventual scope nou trebuie să demonstreze datele admisibile și excluderile, nu să convertească aceste BLOCKED în PASS. [Separarea exactă a celor28](BLOCKER_DISPOSITION.json) păstrează sursa, lipsa și condiția fiecărui contract.
