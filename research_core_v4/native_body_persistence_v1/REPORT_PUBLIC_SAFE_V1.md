# MXM — cercetare direcțională nouă executată, 11 octombrie 2026

Experimentul `LAG1_BODY_RETURN_COVARIANCE_CONDITIONAL_DIRECTION` a fost înghețat și executat o singură dată. Verdictul este `CLOSED_EXACT_NO_NATIVE_PANEL_GROSS_INCREMENT`. Nu există promovare alpha, avantaj NET certificat sau demonstrație HARD21.

## Execuție verificabilă

Baza acceptată: `b664ca56fad6adb03dde9eb1923606341aa627f2`. Commitul de freeze și execuție: `c8e37d6a47fa2d07d8bba03add6e81c96f920192`, descendent direct. Commitul conține șase fișiere noi, 386 linii adăugate; toate cele 3.900 de intrări ale arborelui anterior sunt identice. Șapte bindings SHA256 au fost recalculate local și pe runner. Completarea documentară este exclusiv aditivă și nu modifică freeze-ul sau executorul.

Workflow: `.github/workflows/mxm-native-body-persistence-v1.yml`; [run 38125067899](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/38125067899), [job 114427615149](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/38125067899/job/114427615149), SUCCESS. Șase teste PASS, apoi verificare completă a celor 100 de shards MASTER1576, 3.355.389 rânduri autentice. Calcul nou, fără apelarea vreunui kernel de experiment închis. Zero cereri broker noi, zero ordine și fără protected forward.

Testele acoperă string-ul monedei comisionului minim, BID/ASK long/short și conversia semnată, invarianta direcției față de lipsa ieșirii, witness-ul de informație distinctă de close-location, baza taxei pe P&L și numitorii de cost.

## Mecanism, cohortă și decizie

Pentru cele douăsprezece corpuri M5 completate cauzal, covarianța centrată lag-one a randamentelor log C/O stabilește continuarea sau inversarea ultimului corp. Baseline: direcția ultimului corp. Nicio estimare sau căutare de prag/semn/oră/instrument. Witness-ul software păstrează toate close/high/low și statistica veche de close-location, schimbând doar opens și direcția nouă.

Toate cele 1.576 de identități sunt raportate, fiecare clasă inclusă, pe toate cele 672 de ceasuri orare UTC cu faza :15. Faza reutilizează frontierele acceptate; nu este aleasă după randamente. Rezultatele sunt păstrate pentru cele patru blocuri originale și toate săptămânile ISO, inclusiv cele parțiale. Scorul M5 folosește referințe OHLC, fără afirmație de fill. Panelul economic fix EURUSD/GBPUSD/SpotCrude folosește arhivele acceptate, seriile native și cele 300 de frontiere existente.

Criteriul brut pe întregul panel nativ a eșuat. Nu a fost selectat un instrument, o clasă, un ceas, o inversare sau un orizont câștigător. Extinderea condiționată de frontiere nu a fost declanșată. Agregatul pozitiv fragil al universului larg nu salvează eșecul economic al panelului fix.

## Contabilitatea nouă

`minCommissionAsset` este string valutar în Open API, interpretat împreună cu `minCommissionType`; nu ID în lista assets. Floor-ul minim și comisionul proporțional sunt convertite și comparate în EUR pentru fiecare latură. În snapshot-ul nativ reutilizat, toate cele trei monede ale minimului sunt USD, floor-urile minime sunt zero și `pnlConversionFeeRate` este zero. Aceste valori actuale nu certifică taxele istorice.

LONG cumpără ASK și vinde BID; SHORT vinde BID și răscumpără ASK. Sunt aplicate ambele comisioane, FX de la intrare pentru comisionul de intrare, FX de la ieșire pentru comisionul final și P&L. Obligațiile USD folosesc EURUSD BID; încasările folosesc ASK. Documentația identifică taxa de conversie ca procent din P&L brut realizat, nu din noțional. Convenția pe profit pozitiv și stress-ul pe valoarea absolută a pierderii sunt distincte; ratele actuale zero fac această ambiguitate fără impact numeric în acest panel, fără certificarea debitării istorice.

Numitorii separă toate intrările cu cost de intrare calculabil de intrările eligibile cauzal. Fiecare medie de rezultat folosește n-ul evaluabil explicit; lipsurile de ieșire nu sunt nici zerouri, nici criterii de intrare. Slippage-ul 0/1/2 bps pe fiecare latură și finanțarea 0/0,10/0,50 EUR sunt scenarii, nu istoricul fill-urilor sau al swap-urilor.

Eligibilitatea folosește doar semnalul, range-ul trecut, quote și FX de intrare, metadatele și calendarul actual, volumele minime, marja și proxy-ul range+cost. Alocarea selectează maximum o poziție per ceas după fracția cost/range, apoi ID, înainte de citirea ieșirii. O ieșire lipsă nu permite înlocuirea instrumentului. Ledger-ul monetar parțial se oprește la prima ieșire sau conversie lipsă; nu certifică supraviețuirea capitalului sau drawdown intratrade.

## EUR200 și HARD21

Cele 168 de momente orare nominale per săptămână completă reprezintă o limită geometrică. Observațiile simultane ale celor trei instrumente nu sunt independente. Dependența temporală, expunerea comună USD și conversia comună EURUSD rămân; numărul efectiv independent și corelațiile de risc nu sunt certificate. Alocatorul păstrează maximum o poziție simultană și marjă curentă maximum 50 EUR, cu rezervă inițială 150 EUR. Acestea sunt screens de capacitate, fără garanție de stop sau gap.

Frecvența portofoliului eligibil nu atinge pragul în fiecare săptămână completă; subsetul evaluabil și rezultatele NET modelate nu susțin avantajul. Tranzacțiile executate și cele cu avantaj NET certificat sunt zero. Nu se forțează frecvența și nu se promovează baseline-ul după rezultatul modelului.

## Date, criptare și integritate

[Release primar 409539620](https://github.com/mariancradulescu/mxm-quant-greenfield/releases/tag/mxm-owner-frontier-bodypersistence-20261011_bod-38125067899): asset `630225718`, `bodypersistence-private-result.mxmenc`, 1.263.292 bytes, SHA256 `7f245b4ad821d68e59229d48563ab2823a4884bb34b2c2b603baa63d4b9e7987`. Bytes și SHA256 au fost recalculate local independent; runner-ul a făcut și roundtrip-ul remote autentificat al plaintextului. Local nu a fost redecriptat primarul cu cheia owner.

Atestare asset `630225824`, SHA256 `2afb854c844d2947e477f85808adb6a67875004efe71282a63c3d849498f4a71`. Delivery asset `630225777`, SHA256 `51d6cd9f3cbd0158decbe04b6b959fe834210442e4625c37c157fae7cd6161a1`.

[Relay 409539727](https://github.com/mariancradulescu/mxm-quant-greenfield/releases/tag/mxm-executable-diagnostic-relay-20261011_body_persistence-38125067899), SHA256 `467aaa9433967d96873b212660ab132df6d38bf632a8c3860098e5c9421b5423`. Agregatele au fost efectiv redecriptate cu cheia de sesiune existentă, verificate RSA-OAEP/AES-GCM, recipient, HEAD și SHA al payloadului comprimat. Nu a fost pornit un readback separat sau reexecutat un experiment vechi.

Surse reutilizate: calificare release `409145057`/asset `628756517`, SHA `e1562c41ff19febf34c3a216fc32fc3b4cbe67a2219c4e921da26206bbafb1f6`; costuri release `408644252`/asset `626999470`, SHA `727b595205c9b8ee734abc6cc6ba83806186d77ba797d385c8b94c59437dad07`. Binding-urile complete și SHA-urile logurilor sunt în `FINAL_RECEIPT_V1.json`; toate cele 100 de proveniențe ciphertext/canonical sunt în primarul criptat. Valorile numerice detaliate, toate clasele și vectorii privați rămân criptate.

## CI și Cloud

Cele trei eșecuri generale la commitul de execuție rămân distincte de SUCCESS-ul cercetării:

| Workflow | Run | Job publication-state | Job ulterior |
|---|---:|---:|---|
| Recovery Governance | 38125067846 | 114427614974 | audit SKIPPED |
| Exact Geometry | 38125067837 | 114427615070 | calibrate SKIPPED |
| Method Validation | 38125067848 | 114427615141 | method-validation SKIPPED |

Cauza în toate cele trei loguri: `PermissionError: PUBLICATION_ONLY_FAIL_CLOSED prospective boundary response_execution_authorized`. Validatorii și guvernanța înghețată nu au fost modificați. Orice runs ale commitului documentar final se raportează separat, fără cerere de rerun.

V1 rămâne DATA_LIMITED, cu 13 age, patru skew și 95% nemodificate; V2 nu este reexecutat. Probe-ul `MXM_DeliveryProbe_20261012.algo`, SHA256 `137259adc7d021272d2415f1887d3a5edb2310c0da8e611e3458690fe0d321a3`, nu este modificat/recompilat și nu există deployment nou. Proba limitată de luni rămâne verificare tehnică separată, fără ordine, fără certificat de profitabilitate/fill/M5 complet.

## Următorul pas economic

Acest exact este închis. Nu este justificată achiziția unei grile complete de quote-uri pentru el. O întrebare viitoare cu informație distinctă este activitatea surpriză față de aceeași oră din săptămânile precedente, utilizând prefixele M5 native autentice deja acceptate. Ea necesită un design nou și o singură execuție integrată de suport, baseline cauzal și rezultat, fără alegerea claselor pozitive ale studiului de față. Nu există încă un avantaj NET implementabil pentru cBot-ul EUR200.

Surse oficiale: [Open API model messages](https://help.ctrader.com/open-api/model-messages/), [cTrader Algo Symbol](https://help.ctrader.com/ctrader-algo/references/MarketData/Symbols/Symbol/), [Pepperstone costs and fees](https://pepperstone.com/en/trading/costs-and-fees).
