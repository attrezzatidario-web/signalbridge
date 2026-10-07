"""SignalBridge — motore + app web. Avvio: AVVIA.bat"""
from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
from logging.handlers import RotatingFileHandler

import config
from ai_parser import AIParser
from manager import Manager
from mt5_exec import Broker
from store import Store
from web import WebServer

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)-9s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout),
              RotatingFileHandler(config.BASE / "engine.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")],
)
for noisy in ("telethon", "google_genai", "aiohttp.access"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
log = logging.getLogger("main")


def load_mt5():
    if config.SIMULATE:
        from sim import fake_mt5
        log.warning("MODALITA' SIMULAZIONE: MT5 finto")
        return fake_mt5
    import MetaTrader5
    return MetaTrader5


def start_caddy():
    """Avvia Caddy (HTTPS automatico) se c'e' un dominio configurato."""
    exe = config.BASE / "caddy.exe"
    if not config.DOMAIN:
        log.warning("DOMAIN vuoto: app raggiungibile solo dalla VPS su http://127.0.0.1:%d", config.PORT)
        return None
    if not exe.exists():
        log.error("caddy.exe mancante: esegui INSTALLA.bat")
        return None
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/IM", "caddy.exe", "/F"], capture_output=True)
    (config.BASE / "Caddyfile").write_text(
        f"{config.DOMAIN} {{\n  encode gzip\n  reverse_proxy 127.0.0.1:{config.PORT}\n}}\n", encoding="utf-8")
    p = subprocess.Popen([str(exe), "run", "--config", "Caddyfile", "--adapter", "caddyfile"], cwd=config.BASE,
                         stdout=open(config.BASE / "caddy.log", "a"), stderr=subprocess.STDOUT)
    log.info("App online su https://%s", config.DOMAIN)
    return p


async def every(seconds, fn, name):
    while True:
        try:
            await fn()
        except Exception:
            log.exception("loop %s", name)
        await asyncio.sleep(seconds)


async def main():
    if not config.APP_PASSWORD or len(config.APP_PASSWORD) < 10:
        log.error("Imposta nel file .env una APP_PASSWORD di almeno 10 caratteri")
        sys.exit(1)
    if not config.TG_DISABLED and (not config.TG_API_ID or not config.TG_API_HASH):
        log.error("Mancano TG_API_ID / TG_API_HASH nel file .env")
        sys.exit(1)

    store = Store(config.DB_PATH)
    broker = Broker(load_mt5(), config.MT5_PATH, config.MT5_LOGIN, config.MT5_PASSWORD, config.MT5_SERVER)
    ai = AIParser(config.GEMINI_API_KEY, config.GEMINI_MODEL)
    m = Manager(store, broker, ai)
    holder = {"tg": None}

    log.info("SignalBridge %s — avvio", config.VERSION)
    if await broker.call(broker.connect):
        acc = await broker.call(broker.account)
        log.info("MT5 connesso: %s %s (%s)", acc["account_login"], acc["account_server"], "DEMO" if acc["account_demo"] else "REALE")
    else:
        log.error("MT5 non connesso: apri MetaTrader 5 e fai il login al conto")
    log.info("Gemini: %s", "attivo" if ai.ready else "non configurato (solo regole)")
    await m.refresh()

    server = WebServer(store, m, config.APP_PASSWORD, lambda: holder["tg"])
    await server.start("127.0.0.1", config.PORT)
    caddy = start_caddy()

    tasks = [
        every(30, m.refresh, "refresh"),
        every(3, lambda: m.heartbeat(bool(holder["tg"] and holder["tg"].connected), config.VERSION), "heartbeat"),
        every(6 * 3600, store.cleanup, "cleanup"),
    ]
    if not config.TG_DISABLED:
        from telegram_listener import TG
        tg = TG(config.TG_API_ID, config.TG_API_HASH, config.TG_SESSION, m, store)
        await tg.start()
        holder["tg"] = tg
        tasks.append(tg.run())
    log.info("Pronto. In ascolto su %d gruppi attivi.", len(m.enabled_ids()))
    try:
        await asyncio.gather(*tasks)
    finally:
        await store.set_status({"engine_online": False, "tg_connected": False})
        if caddy:
            caddy.terminate()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Arresto.")
