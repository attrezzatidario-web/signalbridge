import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name(".env"))
except ImportError:
    pass

VERSION = "1.0.0"


def env(name, default=""):
    return os.getenv(name, default).strip()


SUPABASE_URL = env("SUPABASE_URL")
SUPABASE_SERVICE_KEY = env("SUPABASE_SERVICE_KEY")

TG_API_ID = int(env("TG_API_ID", "0") or 0)
TG_API_HASH = env("TG_API_HASH")
TG_SESSION = str(Path(__file__).with_name("telegram"))

GEMINI_API_KEY = env("GEMINI_API_KEY")
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-2.5-flash")

MT5_PATH = env("MT5_PATH")
MT5_LOGIN = int(env("MT5_LOGIN", "0") or 0)
MT5_PASSWORD = env("MT5_PASSWORD")
MT5_SERVER = env("MT5_SERVER")

SIMULATE = env("SIMULATE", "0") == "1"   # usa un MT5 finto (per prove senza Windows)
