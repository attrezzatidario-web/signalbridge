"""SignalBridge — motore. Avvio: python main.py (o AVVIA.bat)"""
from __future__ import annotations

import asyncio
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import config
from ai_parser import AIParser
from db import DB
from manager import Manager
from mt5_exec import Broker

LOG = Path(__file__).with_name("engine.log")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)-9s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), RotatingFileHandler(LOG, maxBytes=2_000_000, backupCount=3, encoding="utf-8")],
)
for noisy in ("httpx", "telethon", "hpack", "google_genai"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
log = logging.getLogger("main")


def load_mt5():
    if config.SIMULATE:
        from sim import fake_mt5
        log.warning("MODALITA' SIMULAZIONE: MT5 finto")
        return fake_mt5
    import MetaTrader5
    return MetaTrader5


def check_config():
    missing = [k for k in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "TG_API_HASH") if not getattr(config, k)]
    if not config.TG_API_ID:
        missing.append("TG_API_ID")
    if missing:
        log.error("Mancano nel file .env: %s", ", ".join(missing))
        sys.exit(1)


async def every(seconds, fn, name):
    while True:
        try:
            await fn()
        except Exception:
            log.exception("loop %s", name)
        await asyncio.sleep(seconds)


async def main():
    check_config()
    db = DB(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
    broker = Broker(load_mt5(), config.MT5_PATH, config.MT5_LOGIN, config.MT5_PASSWORD, config.MT5_SERVER)
    ai = AIParser(config.GEMINI_API_KEY, config.GEMINI_MODEL)
    m = Manager(db, broker, ai)

    log.info("SignalBridge %s — avvio", config.VERSION)
    if await broker.call(broker.connect):
        acc = await broker.call(broker.account)
        log.info("MT5 connesso: %s %s (%s)", acc["account_login"], acc["account_server"], "DEMO" if acc["account_demo"] else "REALE")
    else:
        log.error("MT5 non connesso: apri MetaTrader 5 e fai il login al conto")
    log.info("Gemini: %s", "attivo" if ai.ready else "non configurato (solo regole)")

    await m.refresh()
    from telegram_listener import TG
    tg = TG(config.TG_API_ID, config.TG_API_HASH, config.TG_SESSION, m, db)
    await tg.start()

    async def commands():
        for c in await db.pending_commands():
            try:
                ok, res = await m.run_command(c, tg)
            except Exception as e:
                ok, res = False, {"msg": str(e)}
            await db.finish_command(c["id"], ok, res)

    tasks = [
        every(5, m.refresh, "refresh"),
        every(3, lambda: m.heartbeat(tg.connected, config.VERSION), "heartbeat"),
        every(1.5, commands, "commands"),
        every(6 * 3600, db.cleanup, "cleanup"),
        tg.run(),
    ]
    log.info("Pronto. In ascolto su %d gruppi attivi.", len(m.enabled_ids()))
    try:
        await asyncio.gather(*tasks)
    finally:
        await db.set_status({"engine_online": False, "tg_connected": False})


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Arresto.")
