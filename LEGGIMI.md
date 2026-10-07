# SignalBridge — Telegram → MT5

```
Gruppi Telegram ──► MOTORE (VPS Windows) ──► MetaTrader 5
                         │  ▲
                         ▼  │
                      SUPABASE  ◄──►  APP (PC / telefono)
```

## Cartelle
- `supabase/schema.sql` — database (da incollare una volta in Supabase)
- `.github/workflows/pages.yml` — pubblica da solo l'app su GitHub Pages a ogni modifica
- `app/` — sorgente React dell'app
- `engine/` — motore Python da copiare sulla VPS

## Cosa fa il motore
- Legge i gruppi Telegram con il tuo account e mostra nell'app TUTTI i tuoi gruppi/canali: attivi quelli da copiare.
- Capisce i segnali con regole veloci; se il messaggio è strano chiede a Gemini.
- Apre subito a mercato (o limit/stop se il segnale lo dice), una posizione per ogni TP.
- Segue gli aggiornamenti: chiudi, chiudi metà/%, SL a pareggio, modifica SL/TP, annulla, messaggio modificato.
- SL a pareggio automatico quando prende il TP1.
- Sicurezze: solo conto DEMO (finché non sblocchi), max posizioni, stop perdita giornaliera, interruttore generale, "Chiudi tutto".

## Installazione (ti guido io passo passo)
1. Supabase: nuovo progetto → SQL Editor → incolla `schema.sql` → Run → Authentication: crea il tuo utente e disattiva le registrazioni.
2. App: carica tutto su GitHub, attiva Pages (Source: GitHub Actions) → apri il link → inserisci URL e anon key di Supabase → login.
3. Telegram: my.telegram.org → API development tools → prendi api_id e api_hash.
4. VPS: installa MT5 (login al conto demo, abilita "Algo Trading") e Python 3.12.
5. Copia `engine` sulla VPS → `INSTALLA.bat` → compila `.env` → `LOGIN_TELEGRAM.bat` → `AVVIA.bat`. Per aggiornare: `AGGIORNA.bat`.

## Test
- `engine/tests/test_parser.py` — formati di segnale (13 test)
- `engine/tests/test_sim.py` — simulazione completa con MT5 finto
