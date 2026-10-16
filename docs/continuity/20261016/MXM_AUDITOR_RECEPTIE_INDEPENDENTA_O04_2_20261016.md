# MXM Quant Greenfield — proces-verbal de recepție independentă O04.2

**Data:** 16 octombrie 2026  
**Calitate:** auditor independent, verificare read-only; fără mutații GitHub și fără rerularea probelor.  
**Repository:** `mariancradulescu/mxm-quant-greenfield`

## Decizie

**ACCEPTED — STAGING SINTETIC EXCLUSIV**

- `WRITER_STATE=STAGED_READY_STOP_ONLY`
- `PRINCIPAL_ISOLATION=VERIFIED_STAGING` **numai ca verdict extern al recepției**
- `OWNER_ACCEPTS_NEW_CHECKPOINTS=false`
- `CAMPAIGN_RESTART_ALLOWED=false`
- `PRODUCTION_GO=false`

Acesta este rezultatul recepției mecanismului sintetic O04.2, **nu** o aprobare pentru a activa writerul de checkpointuri OWNER, cercetarea, tranzacționarea, cBot-ul sau Cloud. Starea sintetică conține în continuare `principal_isolation=UNVERIFIED` ca indicator conservator moștenit. Nu a fost modificată artificial ca să exprime verdictul extern.

## Dosarul auditat și integritatea lui

- Arhivă primită: `MXM_O04_2_RAPORT_SI_DOVEZI_20261016.zip`.
- SHA-256 arhivă: `583ad7eefc5d90f98d94d7fcfb8a96a622348134791142bb6b45e63d3485cdfa`.
- Raport primar: `MXM_O04_2_IDENTITATE_ACCEPTOR_RAPORT_UNIC_20261016.md`, SHA-256 `a83d760eff1ab1e9140e1ed8964b06d93aad37a4d111ffe2f8ed524b66c93196`.
- 148 intrări ZIP; verificare CRC ZIP fără erori; 147/147 fișiere din `SHA256SUMS.txt` au corespuns. Manifestul însuși este singurul fișier neacoperit de manifest.
- Cele 5 arhive Actions esențiale au corespuns digesturilor SHA-256 din raport; conținuturile extrase duplicate sunt semantic identice cu JSON-urile originale (în două cazuri numai formatul a fost schimbat pentru lizibilitate).
- Nu s-au identificat șiruri-cheie brute PEM, PAT sau tokenuri de instalare brute prin inspecția textuală focalizată. Aceasta nu este o dovadă universală că niciun secret nu ar putea exista codificat altfel.

## Dovezi confirmate independent prin GitHub LIVE

| Obiect | Verificare |
|---|---|
| Run issuer/App/CAS | `38885755596`, tentativa 3, `completed/success`; joburi issuer, generic write și read-only `success` |
| Run reader fix | `38898857911`, tentativa 1, `completed/success`; job reader `success` |
| Preflight | `38896722378`, tentativa 3, `completed/success`; `/app` 200 pentru cheia nouă, trei categorii negative 401 în log |
| O04 authority staging | `refs/heads/mxm-o04-stage-authority-v1` = `c6644174244cd92b8e41b17f241b8f5e545fddd9` |
| OWNER STOP | `refs/heads/mxm-o04-accepted-owner-1807-v1` = `a830c132521bd4348454653f713e04f6107484fe` |
| Branch remedieri | `mxm-remediation-p0-p4-20261015-v1` = `6cdf76f5e7bf9c672c24a05c3054f2aa4e137a10` |
| Source issuer înghețat | `mxm-o04-issuer-code-v3` = `639ebc99ab2237f1b68cc152537fe919900f338a` |
| Source preflight înghețat | `mxm-o04-preflight-code-v2` = `ad3fa34c306c6d8f3c521e8839e052f4439185c5` |
| Source reader | `0cf53e3992ab688d502dc0f146a6143075ee8b55` |
| Ruleset authority | `25231211` activ: `creation/update` target numai `mxm-o04-stage-authority-v1`; bypass numai Integration `5343530` |
| Ruleset append-only | `25222248` activ: deletion, non-fast-forward și required_linear_history, fără bypass |
| Freeze OWNER | `25222426` activ: creation/update/deletion/non-fast-forward etc. fără bypass |
| Freeze issuer/preflight | `25232285`, `25236786` active, fără bypass |
| Stare Actions finală | `queued=0`, `in_progress=0` la ultima verificare |

**Loguri native / receipts verificate:** App a creat și avansat referința, cu recuperare după pierderea ACK; writer generic `contents:write` → HTTP 422, cititor `contents:read` → HTTP 403, ambele fără schimbare OID; App force rollback/delete → `GH013`; tokenul App revocat a primit HTTP 401. Cititorul cu `contents:read`, fără secret și fără token App, a verificat semnătura fixată pe noua cheie, parent-OID, digesturile, ROOT și `STAGED_READY_STOP_ONLY` și a respins încercările de spoof și tamper. Integrarea Codex: dosarul conține transcriptul erorii `UNPROCESSABLE / protected ref` și OID înainte/după identic; acest control nu a fost rerulat de auditor.

**Starea `state.json` de la OID final, citită direct din GitHub:** `marker=SYNTHETIC_ONLY`, `mode=STAGED_READY_STOP_ONLY`, `owner=null`, `session=null`, `pending=null`, `lease_until=0`, `OWNER_ACCEPTS_NEW_CHECKPOINTS=false`, `CAMPAIGN_RESTART_ALLOWED=false`, `PRODUCTION_GO=false`; ROOT include OWNER 1807 și jurnalul conservat.

## Custodie administrativă — probă și limită

Probele de interfață din arhiva Directorului arată **o singură** cheie privată GitHub App cu amprenta `SHA256:if9s0/vBUMyiKrKc5p6RJoXtcI2sL6HGIWRjNhpRKpk=`, după revocarea celei vechi `SHA256:SwoXRrvOz1/KtsJiDjEvHD9R7dSP431kk5KyuMEOaYU=`; pagina instalării oferă din nou opțiunea `Suspend`, indicator coerent cu instalarea reactivată. Captura environment-ului indică `O04_ACCEPTOR_APP_PRIVATE_KEY`, allowlist exact `mxm-o04-issuer-code-v3` și `O04_CODE_FREEZE_RULE_ID=25232285`.

**Limită de audit:** accesul read-only prin connectorul GitHub public nu poate citi independent cheia privată, registrul privat administrativ al cheilor App ori starea UI a instalării. Așadar revocarea și reactivarea sunt **atestate documentar de capturile de UI** și coroborate de succesul autentificării App/CAS, nu certificate printr-un GET administrativ independent direct. Nu există motiv tehnic observat pentru a relansa testele doar în vederea suplinirii acestei limite de acces.

În arhivă există și o comparație UI read-only pentru politica 7689: activă, 145 ținte (144 istorice + fixture), restricții fără actori/evenimente permise. Acest aspect nu a fost reextras independent printr-un endpoint administrativ.

## Scope, rezerve, continuare

**Închis pentru scopul autorizat:** preflight key/App, App/CAS real pe fixture sintetic, principal fencing, reader dry-run, protecții rollback/delete și conservarea checkpointului OWNER STOP 1807.

**Nu este închis/nu este autorizat prin această recepție:** writer pentru checkpointuri OWNER reale, tranziția la un writer de producție, restart campanie, cercetare alpha, economie NET/HARD21, cBot, ordine sau Cloud. Recepția O04.2 nu certifică implicit închiderea tuturor celor 191 de contracte P0–P4; acestea au propriul registru și propria recepție.

**Pasul administrativ următor:** se poate efectua handoff către un chat nou al Directorului cu **acest proces-verbal și arhiva finală**, ca repere factuale ale stării. Nu se emite un nou mandat de executare sau de restart. Orice mutație ulterioară trebuie să rămână în limitele unui mandat OWNER valid separat.

## Referințe de verificare

- https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/38885755596
- https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/38898857911
- https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/38896722378
- https://github.com/mariancradulescu/mxm-quant-greenfield/commit/c6644174244cd92b8e41b17f241b8f5e545fddd9
- Arhiva de dovezi furnizată de proprietar, SHA-256 menționat mai sus.
