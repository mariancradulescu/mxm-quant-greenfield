# MXM — recuperare durabilă B și continuitatea datelor originale

19 octombrie 2026.

## Recuperare finalizată, fără repetarea analizei

Ciphertextul ORIGINAL al rezultatului cached-support B a fost recuperat din artefactul GitHub Actions 12197614203, verificat și adăugat în ref-ul de dovezi la **1f5cd4e6df827d61d3231edd48440c66aa14c0a5**, directorul diagnostics/frontier-support-pregate-B-cached/.

ZIP SHA256: e9049f9255d7c6d042e010c9340ce2cf502f7a4b7e3c20cbdf097272750685b4. Ciphertext SHA256: b087ebcae103ff4780b41da4cb6623593bd18b52de68dd9262a0c96236391ad4; 3.377 octeți. Chitanța originală concordă exact cu rezultatul public anterior. După scriere, partea criptată și chitanța au fost recitite din GitHub și comparate integral. Nu s-a folosit cheia privată și nu s-a recriptat sau recalculat nimic.

program-state.json este identic octet cu octet cu părintele ffaac1428220926509299d8cbca0f9d9fee35d3a. Checkpoint16, pending=null, safe_stop=true, sursele, toate arhivele anterioare, OWNER1807 și autoritatea activă sunt conservate. Adăugarea s-a făcut prin commit descendent și update de ref cu expected SHA, fără force sau slăbirea protecțiilor.

## Cauza și recuperarea transportului

Workerul original 118148506560, run39278529554/attempt1, este confirmat SUCCESS nativ, la trigger a3e609779c2f1dcc069e96b23797b27d63c1fe5a și sursa1340ab28cc645f3a05acd75838de1618b0d18067. Publisherul118148698981 a eșuat cu LAB_CACHED_NATIVE_SUCCESS când API-ul nu afișa încă succesul workerului; rezultatul și artefactul existau deja.

S-a cerut reîncercarea numai a jobului eșuat. Attempt2 a fost SKIPPED de protecția existentă a tentativelor. Nu există o nouă evaluare științifică: înregistrarea succesului moștenit are jurnalul și artefactul ORIGINAL, cu timestampurile15:31 și același artifactID. Nu declarăm întregul workflow SUCCESS și nu contabilizăm tentativa de transport drept confirmare sau încercare economică.

Arhivarea a fost recuperată prin conectorul GitHub, nu printr-un nou program: verificare explicită a jobului original din endpointul attempts/1/jobs, SHA sursă/trigger/artefact, verificare criptografică locală și append-only CAS în ref-ul protejat. Dovada metodei este transport-recovery.json lângă ciphertext. Nu au fost înlocuite cerințele de autoritate printr-un simplu mesaj din jurnal.

Corecția de referință a verificării publisherului este versionată la **59ca00ea56e43ce5086b58016c3abcd6317ab9a6**: dovada se leagă de tentativa 1, jobul original, run, trigger și succes, nu de lista implicită a ultimei tentative de transport. Cinci teste focalizate au trecut, inclusiv respingerea unui retry, a altei surse, a altui job/run și a dovezilor ambigue/lipsă. Această sursă nu a fost folosită pentru a relansa B și nu modifică sursa recepționată. Nu pretindem că schimbarea referinței elimină orice întârziere eventuală a API-ului.

## Rezultatele economice nu s-au schimbat

Rămân493 de momente bilaterale valide pentru opt identificatori, zero în perioada M5 20–26 august2026 în cache-ul examinat; condițiile din11octombrie nu certifică istoricul. B este închis finit pentru cele două execuții de calcul și cele opt arhive prevăzute. Reîncercarea și recuperarea transportului sunt documentate separat, fără resetare sau extindere a bugetului științific.

V2 rămâne21 de identități taxate la outcome,29 de observații, rezervarea C033 păstrată, contorul tehnic22. În această recuperare: zero noi identități/rezervări, outcomes, cereri broker, ordine sau decriptări. Niciun candidat sau cBot nu este calificat printr-o arhivare reușită.

## Localizarea altor date: constatare de proveniență

Am citit țintit șapte manifeste/surse publice din sursa conservată, fără deschiderea rândurilor de piață sau a rezultatelor economice. Nu este un nou experiment sau un inventar exhaustiv.

ARCHIVE_INPUT_MANIFEST_V1 identifică EURUSD.zip și SpotCrude.zip și membri BID/ASK pentru săptămânile16–23 și23–30august2026. Dar sursa recover_archives_v1.py le clasifică explicit în demo_tick_archives, accountMode=DEMO, reused_as_live_execution=false. Nu le-am promovat drept acoperire autentică a execuției sau costurilor contului nostru. Simplul nume de instrument și suprapunerea calendaristică nu repară proveniența.

Pachetul criptat asociat acelui manifest conține trei membri M5 acceptați și catalogul; nu conține automat octeții tick doar pentru că aceștia apar în index. Manifestul V4_EXACT_M5_INPUT_MANIFEST_V2 identifică18 serii M5, nu un substitut pentru BID/ASK. Aceste constatări evită o recuperare inutilă sau folosirea unei surse neeligibile.

Pagina publică a raportului native-frontier din14octombrie indică două execuții native acceptate,38540231625 și38543479609. Acesta este un locator istoric, nu colectare nouă și nu dovadă deja verificată de suprapunere cu cei29 de identificatori și fereastra B. Următoarea căutare țintită trebuie să folosească metadatele checkpointurilor lor, fără replay, fără PnL și fără înlocuirea eșantionului după rezultate.

Registrul de metadate și bloburile sursă se află în ORIGINAL_DATA_METADATA_FOLLOWUP.json. Nicio achiziție nouă nu este justificată doar de faptul că primul cache nu acoperă perioada. Mai întâi se rezolvă locațiile și acoperirea nativă păstrată; apoi numai lipsurile exacte, legitime, pot primi un buget prospectiv de colectare read-only.
