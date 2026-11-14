# Bandi NucleoBoard

Sito statico che raccoglie i bandi utili al NucleoBoard di Cascina Roccafranca, più un controllo automatico giornaliero delle pagine dei finanziatori.

## Come funziona

- `index.html` è il sito. Legge `bandi.json` (i bandi) e `novita.json` (le novità trovate dal controllo).
- `monitor/monitor.py` ogni giorno scarica le pagine elencate in `monitor/pagine.json` e confronta i link con quelli visti il giorno prima.
- Se compare un link nuovo, o cambia il testo di una pagina con `"controlla_testo": true`, GitHub apre una segnalazione (Issue) e ti arriva una mail.
- Non serve un database: lo stato sta in `monitor/state.json`, salvato nel repository.

## Limiti

- Lo script vede che una pagina è cambiata. Non capisce da solo se un bando è adatto: lo decidi tu.
- Alcuni siti possono bloccare lo script. In quel caso l'errore compare una volta nella segnalazione.
- Il primo giorno memorizza lo stato di partenza e non segnala nulla.
- Le Issue sono visibili a chi ha accesso al repository. Se il repository è pubblico lo sono a tutti: tieni privato il repository se non vuoi.

## Messa online, passo per passo

1. Crea un account su github.com, se non l'hai.
2. Nuovo repository, nome `bandi-nucleoboard`, **Private**.
3. Carica tutti i file di questa cartella (pulsante Add file, Upload files). Attenzione: la cartella `.github` deve esserci, anche se nascosta.
4. Scheda **Settings → Actions → General**: sotto Workflow permissions scegli *Read and write permissions* e salva.
5. Scheda **Actions → Controllo bandi → Run workflow** per il primo avvio. Il giorno dopo parte da solo.
6. Scheda **Settings → Notifications** (profilo GitHub): lascia attive le mail per le Issue del repository, poi premi **Watch → All activity** sul repository.
7. Sito gratuito su Cloudflare Pages: dashboard Cloudflare → Workers & Pages → Create → Pages → Connect to Git → scegli il repository. Build command: vuoto. Output directory: `/`. Ogni volta che lo script aggiorna il repository, il sito si aggiorna da solo.

Alternativa: GitHub Pages (Settings → Pages), ma su un account gratuito richiede un repository pubblico.

## Aggiungere un bando

Apri `bandi.json` su GitHub, premi la matita e copia un blocco esistente. Campi principali: `id`, `ente`, `titolo`, `stato` (`aperto`, `atteso`, `verifica`, `chiuso`), `scadenza`, `importo`, `fit` (`ok`, `warn`, `none`), `temi`, `nota`, `todo`, `link`.

## Aggiungere una pagina da controllare

Aggiungi una riga a `monitor/pagine.json`.
