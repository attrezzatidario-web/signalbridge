# SignalBridge — Telegram → MT5

```
Gruppi Telegram ──► VPS Windows: MOTORE + DATABASE + APP ──► MetaTrader 5
                                     ▲
                          https://TUO-NOME.duckdns.org  (PC / telefono, con password)
```

Niente servizi esterni: tutto gira sulla VPS. GitHub conserva il codice e compila l'app.

## Cartelle
- `engine/` — motore Python + server web (va sulla VPS)
- `engine/web/` — app compilata (la crea GitHub da sola)
- `app/` — sorgente React dell'app
- `.github/workflows/pages.yml` — compila l'app a ogni modifica

## Cosa fa
- Legge i tuoi gruppi Telegram; nell'app scegli quali copiare e con che rischio.
- Capisce i segnali (regole + Gemini), apre a mercato o limit/stop, una posizione per TP.
- Segue gli aggiornamenti: chiudi, chiudi metà/%, SL a pareggio, modifica SL/TP, annulla, messaggi modificati.
- SL a pareggio automatico dopo TP1.
- Sicurezze: solo DEMO finché non sblocchi, max posizioni, stop perdita giornaliera, interruttore generale, "Chiudi tutto".
- App protetta da password, HTTPS automatico, blocco dopo 5 tentativi sbagliati.

## Installazione sulla VPS (ti guido io)
1. DuckDNS: crea il nome (es. signalbridge-dario) e mettici l'IP della VPS.
2. Installa Python 3.12, MetaTrader 5 (login demo, Algo Trading attivo).
3. Scarica il codice da GitHub, copia la cartella `engine` in `C:\SignalBridge`.
4. `INSTALLA.bat` → compila `.env` (password app, dominio, Telegram, Gemini).
5. `LOGIN_TELEGRAM.bat` → `AVVIA.bat`.
6. Aggiornamenti futuri: `AGGIORNA.bat`.
