import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name(".env"))
except ImportError:
    pass

VERSION = "1.1.0"
BASE = Path(__file__).parent


def env(name, default=""):
    return os.getenv(name, default).strip()


# App web
APP_PASSWORD = env("APP_PASSWORD")
DOMAIN = env("DOMAIN")                      # es. signalbridge-dario.duckdns.org (vuoto = solo locale)
PORT = int(env("PORT", "8080") or 8080)
DB_PATH = str(BASE / "dati.db")

# Telegram
TG_API_ID = int(env("TG_API_ID", "0") or 0)
TG_API_HASH = env("TG_API_HASH")
TG_SESSION = str(BASE / "telegram")
TG_DISABLED = env("TG_DISABLED", "0") == "1"   # solo per prove

# Gemini
GEMINI_API_KEY = env("GEMINI_API_KEY")
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-2.5-flash")

# MT5
MT5_PATH = env("MT5_PATH")
MT5_LOGIN = int(env("MT5_LOGIN", "0") or 0)
MT5_PASSWORD = env("MT5_PASSWORD")
MT5_SERVER = env("MT5_SERVER")

SIMULATE = env("SIMULATE", "0") == "1"   # MT5 finto (per prove senza Windows)
