# B — componente verificate și traseu nativ pregătit, fără writer activ

Sursa: `95fc312a84f803276a408ca4f821a09b007e56b0`, ramura `mxm-o04-successor-code-b-v1`. [Run 39057507405](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/39057507405) SUCCESS, toate cele4 joburi SUCCESS. B1 acceptată de OWNER ca verificată independent: nerepetată. Mandatul B–E rămâne valabil; nu se cere mandat nou.

## Rezultate efective

- 11 teste noi de continuitate: lease determinist derivat din același root OWNER, buget finit, replay/rollback, ACK pending, revocare, tranziții de fază și CAS Git concurent.
- 8 teste noi de admitere: review nativ reutilizat după24h, refuz actor/hash/config/TTL greșit, ACL exact fără alți actori, nicio emitere token înaintea admiterii, izolare env Git și receive-pack real pe Git bare local cu concurență și readback rece.
- Două joburi distincte au transferat o autoritate **fixture Git locală**, au restaurat-o rece și au reînnoit la timp simulat +172800s. Nu este probă App/GitHub active.
- Jurnalul **real** OWNER1807 a fost descărcat, verificat pe ciphertext/gzip/canonical și decriptat machine-side cu cheia OWNER existentă. Adaptorul nou a restaurat generația1807, runtime sequence19 și inventarul celor77 referințe directe. Zero source assets recitite, zero broker requests, zero research, zero ordine. UNKNOWN rămâne carantină. Acesta este input runtime read-only, nu certificare economică.
- Workflow-ul nativ B a fost înregistrat pe main la `bcdf70015d54c8b860207593147d7572383cb883`, blob `162f329f952c99a48c5a4da314b6c6e5bddc4603`, byte-identical cu sursa B. Nu a fost dispatch-uit.

## Traseu nativ implementat, nearmat

`native.py` și workflow-ul B verifică review-ul inițial pe manifestul exact care leagă source/root/access. Runurile obișnuite verifică aceeași recepție nativă și ACL-urile proaspete, apoi derivă lease-uri finite fără review pe run. Secretul App rămâne în procesul issuer; tokenul contents-write este emis pentru repository-ul unic și revocat în finally. Git copil are mediu minim, fără cheia OWNER sau App. Se reutilizează Git receive-pack CAS, fără PATCH de ref și fără force necondiționat. Pending/ACK incert produce STOP, fără callback/reexecuție ori bootstrap repetat.

Proba B nativă este limitată la două segmente reale de restaurare. Lease-ul scurt60s permite demonstrarea expirării/reînnoirii între rulări, pe același grant. Schedulerul solicită singur continuarea după expirare. După generația de control1809 se oprește cu `C_INSTALLATION_PENDING`: nu pretinde că workerul științific C este instalat. Numerele1808/1809 din proba viitoare vor fi generații noi de control, nu rezultate economice noi.

## Frontieră administrativă observată direct

Interfața administrativă GitHub este disponibilă și autentificată; nu este tratată ca indisponibilitate generală B. Sursa B a fost creată la HEAD testat. Formularul noului sigiliu este pregătit pentru **numai** sursa B: Active; creation/update/deletion/non-fast-forward; bypass gol. La Create, GitHub cere `Confirm access`, cu GitHub Mobile sau email. **Sigiliul B nu este încă salvat**. Nu se cere o nouă autorizare OWNER; numai reconfirmarea personală cerută de platformă.

Cheia App curentă este încă în `mxm-o04-staging-issuer/O04_ACCEPTOR_APP_PRIVATE_KEY`; destinația existentă `mxm-p0-successor-issuer-v1` este fără cheie App. Nu a fost citită/expusă cheia și nu s-a creat o alta. GitHub nu permite citirea secretului existent pentru o mutare UI. După sigiliu, pasul indispensabil de credential/custodie trebuie realizat prin interfața nativă, fără PEM în chat. Nu retrage cheia veche înainte ca destinația și amprenta corectă să fie verificate; fără bypass active până la închiderea vechii rute și TTL3600.

## Stare păstrată și limite

OWNER1807 = `a830c132521bd4348454653f713e04f6107484fe`; active-v1 absentă;25268790 active/bypass[]; sigiliul A25295948 active/bypass[]. Nicio regulă veche modificată. Nicio activare writer, token App, migrare credential, cercetare, ordin sau cBot.163PASS/28BLOCKED neschimbate. B **nu** este declarată operațională; C–E nu sunt declarate începute/închise.

Erorile proprii intermediare sunt păstrate în Actions: YAML înainte de runner; apoi diferența newline dintre encoderul jurnalului original și encoderul control-plane. Ambele sunt corectate; versiunea finală este SUCCESS. Probele vechi A/B1 și163PASS nu au fost reluate.
