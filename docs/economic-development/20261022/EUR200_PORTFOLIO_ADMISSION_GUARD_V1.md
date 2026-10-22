# MXM B–E — capital unic EUR200: aceeași poartă de admitere în C# și cBot

22 octombrie 2026. **Inginerie preventivă, nu avantaj economic validat.**

## Defectul constatat
Produsul C# anterior verifica pozițiile proprii doar la `Positions.FindAll(Label,SymbolName)` și marja noii intrări raportată la `Account.FreeMargin`. Dacă două instanțe distincte folosesc simboluri diferite, fiecare putea admite o nouă poziție fără un plafon explicit la nivelul întregului cont MXM. Simulatorul de referință, în schimb, ținea o singură poziție pe un singur simbol. Nu era o demonstrație de paritate pentru portofoliul unui cont unic de 200 EUR.

## Modificare efectivă
- `MxmCapitalAdmission.cs` este o lege unică deterministă, compilată în proiectul simulatorului C# și în produsul real cTrader .algo.
- Refuză dacă oricare dintre valorile în moneda contului este invalidă, dacă numărul de poziții MXM deja deschise pe **toate simbolurile** atinge limita configurată, dacă marja estimată depășește procentul configurat din marja liberă sau dacă marja și costul anticipat ar încălca rezerva configurată.
- cBot citește pozițiile existente cu `Positions.FindAll(Label)`; configurații `MaxMxmAccountPositions` implicit 1, `MinimumFreeMarginReserveEur` implicit 0, ambele revizuibile pe baza dovezilor, nu impuse de OWNER. Limita tehnică precedentă `MaxMarginFraction` rămâne configurabilă, cu implicit 40%.
- Simulatorul de referință utilizează aceeași lege la deschidere, dar rămâne explicit **un singur simbol** și **un singur canal de cont ipotetic**. Nu pretinde portofoliu multi-instrument.
- Opt cazuri artificiale declarate validează admiteri și respingeri: cont EUR200, marjă 90/150, sensibilitate prag 40/80%, rezervă suplimentară, poziție deja existentă în cont, pierdere anterioară care scade equity, date inconsistente.

## Limite care nu pot fi eliminate prin acest patch
`Positions.FindAll` și `Account.FreeMargin` sunt **instantanee**, fără CAS/lock atomic între instanțe cTrader. Astfel o intrare simultană din două instanțe Cloud poate încă trece ambele verificări. Controlul trebuie considerat fail-closed individual și util, dar **NU certifică mutual exclusion la nivelul contului**. Produsul final ar trebui să aibă un singur orchestrator care serializă comenzile, plus readback broker și reconciliere după fiecare ordin.

Brokerul calculează marja reală pe baza condițiilor sale curente. `Symbol.GetEstimatedMargin` este o estimare curentă, iar fiabilitatea istorică nu este certificată. Comisioanele inițiale sunt necunoscute în adaptor și sunt trimise ca `0` la poarta preliminară; brokerul poate debita comisioane și alte costuri. Nu se garantează un nivel economic sigur post-fill doar fiindcă poarta sintetică a admis cererea. Nu există istoric de fill, swap/funding, convertiri FX istorice sau stop-out cert. Restricția `Account.Asset.Name=="EUR"` previne amestecul accidental al monedelor.

Nicio ordine LIVE, activare Cloud, nouă cerere Pepperstone, nouă identitate de cercetare sau rezultat economic. V2/C033, OWNER1807 și regiunea PROTECTED nemodificate.

## Decizia executivă
Controlul de capital se păstrează în produs ca infrastructură verificabilă. Strategia finală nu este calificată până când un replay al întregului portofoliu pe un singur cont, cu costuri, volum și marjă broker-native, nu dovedește economic compatibilitatea. **Nicio versiune de stop/exit/semnal și nici limitele tehnice implicite nu sunt considerate câștigătoare permanent.**
