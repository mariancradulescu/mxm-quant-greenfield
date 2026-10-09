# Recuperare științifică MXM — V1

Stare: **recuperare parțială, oprire pentru audit independent**. Aceste fișiere păstrează materialul efectiv recuperat; nu declară recuperarea tuturor conversațiilor, a tuturor surselor istorice sau a octeților arhivelor. Nu aleg un câștigător global și nu autorizează execuție reală.

Sursa canonică verificată inițial: `65887459e4c7c8b9551fb02c6c2c59c13fca8b33`, ramura `performance-research-v3-20260922`. Autoritățile originale sunt păstrate integral.

| Fișier | Conținut |
|---|---|
| PROJECT_SCIENTIFIC_CONTINUITY_LEDGER_V1.json | Cele 15 autorități obligatorii, 19 legături de hash verificate, obiectivul final și limita recuperării |
| FORMULA_TO_IMPLEMENTATION_TRACEABILITY_MATRIX_V1.json | 24 intrări tematice: specificații exacte, cod, ipoteze, estimanzi, rezultate și limite |
| HISTORICAL_RESULT_AND_SELECTION_LEDGER_V1.json | 51 noduri de închidere, rezultate adaptive, Stage6/7, certificatele 24/28 săptămâni și selecția |
| DATA_ARCHIVE_AND_RECOVERY_PROVENANCE_LEDGER_V1.json | PRIMARY145, 100 fragmente criptate, proveniență, diferența dintre metadate și recuperare exactă |
| PROJECT_WIDE_OPEN_QUESTION_AND_BLOCKER_MATRIX_V1.json | Familii deschise, blocaje, defectul fail-open și limitele promovării |
| RESEARCH_REENTRY_DECISION_AND_NEXT_EXPERIMENT_V1.json | Nicio rută empirică globală selectată; discriminatorul minim fără rezultate și proiectul existent păstrat pentru audit |
| SOURCE_BYTE_IDENTITY_INVENTORY_V1.json.gz | Index comprimat fără pierderi al celor 3403 fișiere originale: SHA256, commit și cale; indexarea nu echivalează cu analiza tuturor fișierelor |
| VERSIONED_DELIVERY_MANIFEST_WITH_SHA256_V1.json | Identitatea exactă a octeților livrați și delimitarea afirmațiilor |
| PUBLICATION_VERIFICATION_V1.json | Citirea independentă după publicare și filiația commitului care conține livrabilele |

Citările din JSON indică exact calea, SHA256, commitul sursă și ultima modificare. Hashurile din manifest se calculează peste octeții fișierelor, inclusiv terminatorul final; pentru inventar se verifică separat fișierul gzip și conținutul decomprimat. Manifestul nu își include propriul hash; acesta este legat în certificatul de publicare. Certificatul este un commit ulterior, cu commitul livrării ca părinte, evitând o referință circulară.

Rezultatele istorice nu au fost recalculate. Metadatele GitHub ale celor 100 fragmente coincid cu hashurile declarate, fără descărcare sau decriptare. Cele două ZIP-uri PRIMARY145 au fost localizate în metadate, fără reverificarea octeților. Conversațiile originale nu au putut fi recuperate din cauza unei erori de acces. Aceste limite sunt blocaje, nu rezultate negative de piață.

Reluarea trebuie să reutilizeze loturile publicate, să rezolve accesul la sursele originale și proveniența exactă în infrastructura existentă și să păstreze istoricul selecției. PRIMARY145 rămâne exploratoriu, cu 18 comparații înghețate și execuția numerică reală neefectuată. Defectul furnizorului rămâne deschis. Nu se deschid rezultate noi, nu se cer date brokerului și nu se tranzacționează în această campanie.
