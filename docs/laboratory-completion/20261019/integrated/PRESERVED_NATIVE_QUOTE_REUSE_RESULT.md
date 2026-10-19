# MXM — reutilizare verificată a checkpointurilor native de cotații

19 octombrie 2026. Întrebarea prospectivă: tranșa nativă deja colectată la14octombrie acoperă aceiași29 de identificatori în perioada20–26august, absentă din cache-ul restrâns verificat în B?

## Rezultat material

Au fost reutilizate toate cele39 de checkpointuri raw quotes-N din release412526716, numai369.925octeți criptați. Acestea conțin2.462 de momente native deja colectate, nu2.462 de observații achiziționate acum. Din eșantionul fix29 există58 de momente în această tranșă, dintre care28 în perioada B;17 trec criteriile bilaterale stricte, pentru șase identificatori:

| Instrument | Clasă | Momente în perioada B | Bilaterale stricte valide |
|---|---|---:|---:|
| LTCUSD | Crypto Currency (Spot) | 4 | 4 |
| ITX.ES | ES Equities | 4 | 1 |
| OR.FR | FR Equities | 4 | 1 |
| EURJPY | Forex (Spot) | 8 | 6 |
| WTOIL-PERP | Perpetual Commodity | 4 | 4 |
| SPCX.US-PERP | Perpetual Stock | 4 | 1 |

Cele11 momente rămase din perioada B au cinci cazuri cu laturi neconfirmate autentic-cauzal, cinci cazuri stale și un decalaj bid/ask peste limita permisă. Nu au fost găsite conflicte. Regula de verificare este aceeași ca în B: age≤5sec, sincronizare≤2sec, timestamps cauzale și age exact, paginare rezolvată, prețuri finite pozitive și bid≤ask. Nu am relaxat praguri și nu am înlocuit identificatori.

Cele17 momente nu sunt17 semnale, tranzacții sau fills. Nu certifică perechi intrare/ieșire complete, frecvență de strategie, putere statistică, costuri istorice sau fezabilitate EUR200. Celelalte23 de identități fără suport bilateral strict în această fereastră/tranșă NU sunt respinse economic și nu sunt declarate lipsite global de date.

## Corecția hărții de suport, nu a rezultatului B

Rezultatul B rămâne corect pentru cache-ul lui: zero momente în20–26august. Nu mai trebuie generalizat drept absență a cotațiilor în toate arhivele. Tranșa raw nativă este o sursă păstrată distinctă, identificată prin release/run/source și verificată fără deschiderea coverage-economic-result sau complete-economic-result.

Sursele actuale au poziții separate: cache-ul B are493 de momente bilaterale valide în alte date; checkpointurile native regăsite adaugă suport documentat pentru17 momente în fereastra vizată. Nu se însumează mecanic în încercări independente sau confirmări. Nici grupul de șase regăsit aici, nici eșantionul29 nu sunt un nou plafon al universului.

Arhivele DEMO EURUSD.zip/SpotCrude.zip nu au fost folosite. Nu s-a reluat vechea campanie full-native-frontier, chiar dacă pagina ei de release păstrează o etichetă istorică RUNNING_NATIVE_WORK. Autoritățile și opririle istorice rămân nemodificate. Workflow-ul periodic ordinary-recovery verificat separat nu a emis un bootstrap nou: REGISTERED_RESEARCH_COMPLETE_INSUFFICIENT_EVIDENCE, bootstrap_dispatches=0.

## Execuție și dovezi

Planul finit este research_programs/reconciliation/PRESERVED_NATIVE_QUOTE_REUSE.json: o singură invocare, cele39 de active raw fixate prospectiv, fără active cu rezultate economice, fără selecție după prețuri/randamente și fără cereri broker. Este o întrebare de reconciliere a unei alte surse de date, nu redeschiderea B sau multiplicarea unui buget economic prin redenumire.

Sursa nouă: 8b6e24096192ca285f494520692a0b2a6f222afe; trigger:deb564a3eda31a09b0a43888fc86a53bc9c7a8eb; run:39292923427, attempt1, reader și durable-reuse în SUCCESS. Cele trei teste focalizate pentru potrivirea identităților/ferestrelor și respingerea conflictelor au trecut; nicio probă de recepție sau strategie închisă nu a fost reluată.

Originea datelor: run38540231625 SUCCESS, source7fb3b5185da610f6f4dc6432c22f9bdba6ec2fc4; release412526716. Fiecare activ raw a fost verificat prin ID/nume/mărime/digest, integritatea ciphertextului, schema checkpointului, sursa din header și marcajul de captură autentificată al transportului existent. Nu este o recertificare independentă a tuturor vechilor decodoare sau a tuturor arhivelor.

Dovada durabilă nouă:0fc5128b686dca5ac8e08aa5dbe7fe9185ec62a7, director diagnostics/preserved-native-quote-reuse/. Ciphertext SHA256:5b86d3bc84e3e5f702a15c44d8f6d900a6c490cbc12c3c57cb6591655094a536. Rezultatul criptat conține sumarul și proveniența per activ; sursele raw rămân în release-ul original. Nu pretindem că s-a materializat deja o nouă copie normalizată a tuturor prețurilor în shared_catalogue.

Publisherul separat, fără cheie, a folosit succesul readerului din graful nativ GitHub needs.reader.result, artefactul aceluiași run și legăturile source/trigger/runtime/ciphertext. Nu se bazează pe listarea REST eventual întârziată a jobului curent. Integritatea remote a ciphertextului a fost verificată, chitanța a fost recitită și concordă exact cu rezultatul nativ. program-state.json este identic octet cu octet cu părintele1f5cd4e6df827d61d3231edd48440c66aa14c0a5; checkpoint16, pending=null, safe_stop=true sunt conservate.

## Contabilizare și limite economice

Acum: zero identități/rezervări economice noi, zero outcomes, zero cereri Pepperstone, zero ordine; numai reutilizare de date autentice existente. B rămâne închis la cele două execuții și opt arhive M5. Limita noii citiri de sursă este, de asemenea, consumată fără extensie automată. V2 rămâne21 de identități taxate la outcome,29 de observații, o rezervare C033 păstrată și contorul tehnic22; nu există restituiri sau plafon global84.

Condițiile de comision/marjă/sesiuni din catalogul11octombrie rămân referință curentă, nu autoritate istorică. Nu există un nou candidat economic calificat. protected forward, confirmarea independentă și deployment-ul rămân închise; HARD21 nu este demonstrat.

## Continuare justificată

Actualizarea hărții separă acum explicit: suport reutilizabil la ceasuri exacte; cotații stale/laturi neconfirmate; ceasuri încă fără sursă; autoritate istorică a costurilor nerezolvată. Nu justifică o colectare exhaustivă nouă și nici redeschiderea parametrilor C033.

Pasul următor este pregătirea unui registru de dependențe prospectiv pentru un mecanism realmente distinct de cele deja închise: ceasuri M5 complet disponibile, quote/FX lipsă și costuri necesare sau limite justificate. Momentele raw deja disponibile trebuie extrase din sursele autentificate și reutilizate, nu solicitate din nou brokerului. O colectare read-only ulterioară poate cere numai lipsurile exact demonstrate, în buget finit, după verificarea celorlalte surse native relevante. Admiterea economică rămâne separată și necesită implementarea prospectivă a contabilizării rezervare–outcome și suportul cauzal relevant; această citire nu o acordă automat.
