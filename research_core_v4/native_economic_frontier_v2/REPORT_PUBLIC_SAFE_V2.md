# MXM — continuare economică V2 din datele salvate

Data: 2026-10-10. Rolul acestei misiuni: EXECUTOR_DIRECTOR_MXM_QUANT_GREENFIELD. Raportul descrie execuția Directorului; nu pretinde acceptare independentă.

**Rezultat:** un calcul numeric complet de eligibilitate la intrare, costuri pe ambele laturi, break-even, capacitate pentru 200 EUR și suport istoric anterior. Nu s-a executat un nou exact direcțional. V1 rămâne DATA_LIMITED, cu 13 excluderi de vechime, patru de skew și pragul 95% păstrate. Auditul semantic închis nu a fost reluat.

## Execuție și freeze

Repository: `mariancradulescu/mxm-quant-greenfield`; branch `performance-research-v3-20260922`.

HEAD inițial reconciliat live: `6c1b8a6193422454490cc4f41239423714217059`.

Commit freeze și execuție: [`672ae06acd1080f7be9f735228c0c89106a017ad`](https://github.com/mariancradulescu/mxm-quant-greenfield/commit/672ae06acd1080f7be9f735228c0c89106a017ad), părinte exact HEAD inițial, șapte adăugări, zero modificări ale fișierelor existente. `DESIGN_FREEZE_V2.json`, kernelul, runnerul, testele, recipientul public de sesiune, autoritatea și workflow-ul au fost fixate înaintea primei citiri numerice a acestei misiuni. Recepția și raportul sunt o publicare ulterioară exclusiv aditivă; HEAD final se rezolvă din branch și este dat în răspunsul final.

Run [`38084013421`](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/38084013421), job [`114306587179`](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/38084013421/job/114306587179), tentativa 1: **SUCCESS**. Cele patru teste de contabilitate trec atât local, cât și în Actions. Logul final leagă statusul PASS, ciphertext-ul de atestare și relay-ul de commitul freeze.

Bindings SHA256 complete: `EXECUTION_V2.json`; identitățile fiecărui fișier și SHA256 al designului sunt incluse și în recepția finală. Runnerul verifică ancestry, toate bindings, păstrarea byte-for-byte a fișierelor inițiale, freeze-urile infrastructurii existente și consumul unei singure autorități. Nu modifică validatorii sau guvernanța.

## Ce s-a calculat efectiv

Au fost utilizate exclusiv rezultatul nativ acceptat, release `409145057`, asset `628756517`, SHA256 `e1562c41ff19febf34c3a216fc32fc3b4cbe67a2219c4e921da26206bbafb1f6`, și snapshotul autentic de costuri existent, release `408644252`, asset `626999470`, SHA256 `727b595205c9b8ee734abc6cc6ba83806186d77ba797d385c8b94c59437dad07`. Rezultatul primar conține deja bytes ai celor trei surse M5 acceptate; nu a fost necesară o nouă materializare din broker.

Studiul calculează 120 de înregistrări de intrare: toate cele 40 de ceasuri pentru fiecare dintre EURUSD, GBPUSD și SpotCrude. Nu desemnează câștigători și nu nominalizează instrumente după randamente. Separat calculează evaluabilitatea celor două orizonturi pentru aceeași intrare; acestea nu dublează numărul oportunităților.

Fiecare intrare poate utiliza numai:

- Cele 12 bare M5 contigue din `[t-3900,t-300)`, OHLC și tick_volume native, cu activitate pozitivă.
- Referințele simbolului și EURUSD la `t`, sub aceleași limite de 5 secunde, 2 secunde skew și fără pagină hasMore.
- Volumul minim, pasul, lot size, comisioanele, minimele, marjele și taxa PnL din snapshotul curent, ca **scenariu de termeni actuali**, nu contract cunoscut la intrarea istorică.

Caracteristicile calculate sunt body-ul logaritmic al orei lagged, range-ul high-low și suma volumului tick. Acestea nu sunt un semnal direcțional și range-ul nu este randament realizabil. Deciziile formal posibile sunt LONG la ASK, SHORT la BID și abstinență. Niciuna nu a fost aleasă pentru tranzacționare.

Gate-ul V2 se abține la lipsa M5/activității/cotației de intrare/FX de intrare/lattice/costului rezolvabil. Pentru termeni rezolvabili, cere marjă curentă worst-side ≤50 EUR, range la volumul minim plus overhead-ul scenariului ≤2 EUR și range pre-intrare mai mare decât hurdle-ul ambelor orientări. Overhead-ul principal folosește 2 bps **pe fiecare latură** și un stress ipotetic de finanțare de 0,10 EUR. Aceste convenții sunt distincte de V1 și au fost înghețate înaintea rezultatului. Nu se numesc calificare V1 și nu reduc pragul V1.

Au fost calculate și toate celelalte scenarii: 0/1/2 bps pe latură, respectiv 0/0,10/0,50/1 EUR stress de finanțare. Sunt în detaliile criptate pentru fiecare intrare și orientare. Termenii de finanțare istorici rămân necunoscuți: scenariul cu stress zero nu declară că taxa istorică a fost zero.

## Contabilitate și informație viitoare

Pentru cantitatea minimă `u`:

- Long: PnL USD = `u*(BID_exit-ASK_entry)`.
- Short: PnL USD = `u*(BID_entry-ASK_exit)`.
- Slippage advers afectează prețul fiecărei laturi; spreadul este inclus prin prețurile BID/ASK, nu se scade încă o dată.
- Comisionul se calculează separat la fiecare capăt și la prețul fiecărui capăt, potrivit commissionType, precise rate, lotSize și minimum commission. Nu se presupune aceeași taxă la ieșire prin dublarea automată a comisionului de la intrare. Minimul denominat EUR rămâne o obligație EUR; cel denominat USD este convertit prin BID EURUSD. Moneda necunoscută oprește eligibilitatea.
- PnL USD pozitiv se convertește prin ASK EURUSD de la realizare, cel negativ prin BID. Comisionul este obligație la momentul fiecărui capăt.
- Taxa de conversie PnL este inclusă ca `abs(PnL_EUR)*current_rate_fraction`. Aceasta este o convenție explicită de stress pe termenul curent, nu reconstrucția exactă a taxei aplicate istoric sau certificarea tuturor bazelor de taxare ale brokerului.

[Referința oficială Symbol](https://help.ctrader.com/ctrader-algo/references/MarketData/Symbols/Symbol/) descrie comisionul, minimum commission, moneda acestuia, lattice și rata PnL. [Schema Open API](https://help.ctrader.com/open-api/model-messages/) documentează tipurile și scalele câmpurilor. Acestea nu furnizează extrase ale fill-urilor sau taxelor istorice din datasetul nostru.

Pentru gate-ul de intrare, costul round-trip și break-even se calculează **ipotetic** folosind doar cotația intrării, cu EURUSD ținut fix la valoarea intrării. Kernelul rezolvă prețul viitor ipotetic necesar pentru zero EUR în scenariul declarat; nu citește randamentul viitor pentru a alege o intrare.

La evaluarea unui eventual experiment legitim, prețurile reale de ieșire și EURUSD de la ieșire ar putea intra numai în contabilitatea după decizie. În această misiune s-a calculat doar masca de evaluabilitate viitoare, fără PnL direcțional. Lipsa ieșirii este raportată ca cenzură, nu șterge intrarea. Invariantul numeric PASS confirmă că eliminarea observațiilor care nu sunt ceasuri de intrare nu schimbă înregistrările de intrare; implementarea `entry_row()` cere exclusiv simbol/FX la același `t`.

Costurile istorice, swap, rollover, taxe administrative, slippage efectiv, fill-uri, stopuri și livrarea efectivă clientului rămân necertificate. Capacitatea scenariului nu este o curbă de equity, simulare de supraviețuire sau certificat NET.

## Suportul și decizia direcțională

Ținta de precizie a acestui studiu exploratoriu a fost înghețată la minimum 97 de observații per instrument. Referința optimistă pentru o rată binară este `ceil(1,96²*0,25/0,10²)=97`, pentru semi-lățime normală de referință 10 puncte procentuale la 95%. Nu este un calcul de putere al unui model, un certificat IID ori o regulă universală care interzice orice explorare mai mică. Dependența și istoricul multor încercări împiedică interpretarea simplă a acestei precizii.

Setul oferă cel mult 40 de intrări per instrument și numai trei săptămâni ISO complete, înaintea abstinențelor și cenzurii. Gate-ul ales nu poate trece. De aceea nu a fost desemnat, antrenat sau evaluat un nou exact direcțional și nu există un baseline direcțional calculat. Nu prezentăm numărul de intrări eligibile ca rezultat al unei strategii.

Au fost examinate identitățile designurilor existente pentru breadth, RV, tranziții, extrema, asimetria actualizărilor, round barrier și mecanismele diverse. Nicio modificare a ceasului, semnului, instrumentului sau orizontului lor nu este declarată ipoteză nouă. Misiunea nu dovedește că nicio ipoteză distinctă nu ar putea exista; stabilește că acest eșantion nu justifică o nouă execuție conform gate-ului declarat. Nu inventăm o „noutate” ca să producem încă un rezultat.

## Extensia istorică legitimă deja existentă

Bytes autentici și SHA256 ai arhivelor M5 C031 și Stage A V6 au fost reutilizați. Au fost numărate rândurile anterioare lui 20 august și ceasurile 09:15/13:15 cu cele 12 bare disponibile. Toate timestampurile sunt înaintea domeniului protected forward. Datele sunt ale aceluiași fingerprint acceptat; arhivele demo sau necertificate nu au fost substituite.

Există extensie **M5** reală, inclusiv suport comun pentru toate cele trei instrumente. Dar cele 300 de frontiere din sursa înghețată sunt din fereastra actuală: în acest set nu există frontiere BID/ASK live și FX pentru extensia anterioară. Astfel, extensia poate sprijini o cercetare gross separată după un design realmente distinct și un inventar al expunerilor precedente; nu produce acum mai multe episoade NET evaluabile și nu este confirmare independentă. Nu s-au citit randamentele acelor extensii.

## HARD21 și 200 EUR

În fiecare săptămână ISO completă sunt cinci zile × două ceasuri = **10 momente distincte**, per instrument și pentru calendarul comun al portofoliului. Până la 30 de intrări nominale instrument × ceas pot proveni din aceste momente. Cele două orizonturi sunt alternative, nu încă 30 de intrări. Statistica nu transformă cele trei instrumente simultane sau EURUSD comun în trei observații independente. Numărul efectiv de observații independente nu a fost estimat.

S-au calculat două limite superioare pentru subseturile simultane: numai cap-ul de marjă 50 EUR și rezerva 150 EUR; separat același cap plus 1 EUR loss budget planificat pentru fiecare poziție și overhead de cost, cu total ≤2 EUR. Nu este ales vreun subset pentru trading. În ambele cazuri sunt limite de scenariu optimiste, care ignoră orice reducere ulterioară de equity sau imposibilitate de fill. Datele nu certifică protecția stopului.

Rezultatele private arată limita exactă sub acești parametri pentru fiecare săptămână. **HARD21 nu este susținut de această grilă.** Acest verdict nu spune că 200 EUR fac imposibilă orice strategie cu 21 de ticketuri. Alte ceasuri sau mecanisme ar necesita un viitor design independent, justificat ex ante și date autentice la acele momente; nu selectăm ceasuri după randamente și nu achiziționăm acum alte date.

## Artefacte și CI

[Release criptat `409189173`](https://github.com/mariancradulescu/mxm-quant-greenfield/releases/tag/mxm-owner-frontier-nativeeconomicv2-20261010_nat-38084013421):

| Asset | ID | SHA256 |
|---|---|---|
| `nativeeconomicv2-private-result.mxmenc` | `628926741` | `9cdcc7ab20e9d441553b8b44cd64ae173669e96ad0e9ff5a89c5600d3eec93ca` |
| `nativeeconomicv2-private-delivery.mxmenc` | `628926803` | `84ba2ff8396c556252b099e4abd5a4bd207bff16da2c2c80acab9bec0aabd6b2` |
| `nativeeconomicv2-attestation.mxmenc` | `628926842` | `f053b07bd80758a13bd3ebbf0510f544b54c02e68b3163df3bca40b08ea10f37` |

Relay criptat `409189244`, SHA256 envelope `c105628779a2ecb015a55406df042c8dd2146f9ca0d86d4e041baca7be2f97ec`. A fost decriptat local exclusiv sumarul de sesiune, folosind cheia locală a noului recipient public; cheia owner existentă nu a fost exportată. Detaliile private ale intrărilor, prețurile și calculele de cost rămân în artefactul criptat owner. Nu se publică numeric aceste rezultate în repository sau loguri.

Cele trei CI generale pornite automat au FAILURE, același gard existent: `PUBLICATION_ONLY_FAIL_CLOSED prospective boundary response_execution_authorized`.

| Run | Job publication-state |
|---|---|
| `38084013435` | `114306587358` |
| `38084013307` | `114306586765` |
| `38084013377` | `114306587098` |

Aceste eșecuri sunt distincte de SUCCESS-ul calculului economic. Nu au fost ocolite, ascunse sau reparate prin alterarea guvernanței înghețate.

Pachetul `MXM_DeliveryProbe_20261012.algo`, SHA256 `137259adc7d021272d2415f1887d3a5edb2310c0da8e611e3458690fe0d321a3`, sursa și bindings sunt păstrate. Proba fără ordine din 12 octombrie rămâne separată; nu certifică direct profitabilitatea, execuția sau disponibilitatea barelor.

Zero cereri broker, tokeni noi, autentificări modificate, ordine, protected forward, deploymenturi sau replay al exacturilor. Progresul acestei misiuni este numeric și economic: eligibilitate cauzală, costuri și hurdles complete în scenariile declarate, cenzură distinctă, limite de capital/frecvență și extensie autentică cuantificată. Nu există o afirmație nouă de alpha, NET robust sau implementare Cloud verificată.
