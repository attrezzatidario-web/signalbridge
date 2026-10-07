"""
Parser dei messaggi Telegram -> segnale / aggiornamento.

Output (dict):
  segnale:      {"kind":"signal","symbol":"XAUUSD","side":"BUY","order_type":"market|limit|stop",
                 "entry":2650.0|None,"entry_range":[a,b]|None,"sl":2640.0|None,"sl_pips":None,
                 "tps":[2660.0,...],"tp_pips":[...]}
  aggiornamento:{"kind":"update","action":"close_all|close_partial|move_sl_be|modify_sl|modify_tp|cancel|info",
                 "percent":50|None,"price":2655.0|None,"symbol":"XAUUSD"|None,"side":"BUY"|None}
  niente:       None
"""
from __future__ import annotations

import re
import unicodedata

CURRENCIES = ["EUR", "USD", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD", "XAU", "XAG", "SGD", "HKD", "NOK", "SEK", "ZAR", "MXN", "TRY", "PLN"]
CRYPTO = ["BTC", "ETH", "XRP", "SOL", "LTC", "ADA", "DOGE", "BNB"]
INDICES = ["US30", "US100", "US500", "NAS100", "SPX500", "GER40", "GER30", "DAX40", "DE40", "UK100", "JP225", "USTEC", "USOIL", "UKOIL", "WTI", "BRENT", "XTIUSD", "XBRUSD"]

DEFAULT_ALIASES = {
    "GOLD": "XAUUSD", "ORO": "XAUUSD", "XAU": "XAUUSD", "SILVER": "XAGUSD", "XAG": "XAGUSD",
    "DJ30": "US30", "DOW": "US30", "DOWJONES": "US30", "NASDAQ": "NAS100", "NAS": "NAS100",
    "SP500": "US500", "SPX500": "US500", "SPX": "US500", "DAX": "GER40",
    "BITCOIN": "BTCUSD", "BTC": "BTCUSD", "ETH": "ETHUSD", "ETHEREUM": "ETHUSD", "OIL": "USOIL",
}

NUM = r"(\d+(?:\.\d+)?)"

_pair_re = re.compile(
    r"\b(" + "|".join(CURRENCIES + CRYPTO) + r")\s?[/\-]?\s?(" + "|".join(CURRENCIES + ["USDT"]) + r")\b"
)
_index_re = re.compile(r"\b(" + "|".join(INDICES) + r")\b")


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "")
    # emoji/simboli -> spazio (mantiene lettere, numeri e punteggiatura base)
    t = "".join(ch if (ch.isalnum() or ch in " .,:;@/+-%#()\n=_|") else " " for ch in t)
    t = t.upper()
    t = re.sub(r"(\d),(\d{3})(?!\d)", r"\1\2", t)       # 2,650 -> 2650
    t = re.sub(r"(\d),(\d{1,2})(?!\d)", r"\1.\2", t)     # 1,5 -> 1.5 (decimali europei brevi)
    t = re.sub(r"[ \t]+", " ", t)
    return t.strip()


def find_symbol(t: str, aliases: dict | None = None) -> str | None:
    al = {**DEFAULT_ALIASES, **{k.upper(): v.upper() for k, v in (aliases or {}).items()}}
    compact = t.replace("#", " ")
    m = _pair_re.search(compact)
    if m:
        a, b = m.group(1), m.group(2)
        if b == "USDT":
            b = "USD"
        if a != b:
            return a + b
    m = _index_re.search(compact)
    if m:
        s = m.group(1)
        return al.get(s, s)
    for k in sorted(al, key=len, reverse=True):
        if re.search(r"(?<![A-Z0-9])" + re.escape(k) + r"(?![A-Z0-9])", compact):
            return al[k]
    return None


SIDE_RE = re.compile(r"\b(BUY|SELL|LONG|SHORT|ACQUISTA|COMPRA|VENDI|VENDERE|COMPRARE)\b(?:\s+(LIMIT|STOP))?")
SIDE_MAP = {"BUY": "BUY", "LONG": "BUY", "ACQUISTA": "BUY", "COMPRA": "BUY", "COMPRARE": "BUY",
            "SELL": "SELL", "SHORT": "SELL", "VENDI": "SELL", "VENDERE": "SELL"}

SL_RE = re.compile(r"\b(?:SL|S/L|S\.L\.?|STOP\s*LOSS|STOPLOSS)\b\s*[:=@\-]?\s*" + NUM + r"(\s*PIPS?|\s*PIP|\s*PUNTI)?")
TP_RE = re.compile(r"\b(?:TP|T/P|T\.P\.?|TAKE\s*PROFIT|TARGET)(?:\s*(\d)(?![\d.]))?+\s*[:=@\-]?\s*" + NUM + r"(\s*PIPS?|\s*PUNTI)?")
TP_LIST_RE = re.compile(r"\b(?:TP|TAKE\s*PROFIT|TARGETS?)S?\s*[:=]?\s*(" + NUM + r"(?:\s*[/,|]\s*" + NUM + r")+)")
ENTRY_RE = re.compile(r"\b(?:ENTRY|ENTRATA|ENTER|PRICE|OPEN|PREZZO|EP)\b\s*(?:PRICE|ZONE|AREA)?\s*[:=@\-]?\s*" + NUM + r"(?:\s*[-/~]\s*" + NUM + r")?")
RESULT_WORDS = re.compile(r"\b(HIT|HITTED|SMASHED|RESULT|RESULTS|REPORT|CLOSED|RUNNING|PROFIT\s+BOOKED|BOOM|SECURED|DONE)\b")


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_signal(t: str, aliases=None) -> dict | None:
    side_m = SIDE_RE.search(t)
    if not side_m:
        return None
    symbol = find_symbol(t, aliases)
    if not symbol:
        return None
    side = SIDE_MAP[side_m.group(1)]
    order_type = (side_m.group(2) or "market").lower()

    sl = sl_pips = None
    m = SL_RE.search(t)
    if m:
        if m.group(2):
            sl_pips = _f(m.group(1))
        else:
            sl = _f(m.group(1))

    tps, tp_pips = [], []
    lm = TP_LIST_RE.search(t)
    if lm:
        tps = [_f(x) for x in re.findall(NUM, lm.group(1))]
    else:
        for m in TP_RE.finditer(t):
            if m.group(3):
                tp_pips.append(_f(m.group(2)))
            else:
                v = _f(m.group(2))
                if v is not None and v not in tps:
                    tps.append(v)

    entry, entry_range = None, None
    em = ENTRY_RE.search(t)
    if em:
        entry = _f(em.group(1))
        if em.group(2):
            entry_range = sorted([_f(em.group(1)), _f(em.group(2))])
    else:
        # "BUY 2650" / "BUY @ 2650" / "BUY NOW 2650-2645" / "XAUUSD BUY 2650"
        after = t[side_m.end(): side_m.end() + 50]
        am = re.match(
            r"\s*(?:NOW|ORA|MARKET|SUBITO|ADESSO)?\s*[@:]?\s*"
            r"(?:(?!SL\b|TP|STOP|TAKE|TARGET)#?[A-Z][A-Z0-9/]{1,9})?\s*"
            r"(?:NOW|ORA|MARKET|SUBITO|ADESSO)?\s*(?:AT|ZONE|AREA)?\s*[@:]?\s*"
            + NUM + r"(?:\s*[-/~]\s*" + NUM + r")?", after)
        if am:
            entry = _f(am.group(1))
            if am.group(2):
                entry_range = sorted([entry, _f(am.group(2))])

    # risultati / report (es. "GOLD BUY TP1 HIT +50 PIPS") -> non e' un segnale nuovo
    if RESULT_WORDS.search(t) and sl is None and not tps:
        return None

    has_levels = sl is not None or sl_pips is not None or tps or tp_pips
    is_now = bool(re.search(r"\b(NOW|ORA|MARKET|ADESSO|SUBITO)\b", t))
    if not has_levels and entry is None and not is_now:
        return None

    sig = {
        "kind": "signal", "symbol": symbol, "side": side, "order_type": order_type,
        "entry": entry, "entry_range": entry_range,
        "sl": sl, "sl_pips": sl_pips, "tps": [x for x in tps if x is not None], "tp_pips": tp_pips,
    }
    if not sanity_ok(sig):
        sig["_suspect"] = True
    return sig


def sanity_ok(s: dict) -> bool:
    ref = s.get("entry")
    if ref is None and s.get("entry_range"):
        ref = sum(s["entry_range"]) / 2
    sl, tps = s.get("sl"), s.get("tps") or []
    buy = s["side"] == "BUY"
    if sl is not None and tps:
        if buy and not all(tp > sl for tp in tps):
            return False
        if not buy and not all(tp < sl for tp in tps):
            return False
    if ref is not None:
        if sl is not None and (buy and sl >= ref or not buy and sl <= ref):
            return False
        if tps and (buy and min(tps) <= ref or not buy and max(tps) >= ref):
            return False
    return True


# ------------------------------------------------------------------ updates
UPD = [
    ("cancel", re.compile(r"\b(CANCEL|CANCELLED|DELETE\s+(?:THE\s+)?(?:ORDER|PENDING|LIMIT)|ANNULLA|ANNULLATO|IGNORE\s+(?:THE\s+)?(?:SIGNAL|ORDER)|REMOVE\s+(?:THE\s+)?ORDER)\b")),
    ("close_partial", re.compile(r"\b(CLOSE\s+(?:HALF|PARTIAL|PARTIALS|SOME|(\d{1,2})\s*%)|PARTIAL(?:LY)?\s+CLOS\w*|TAKE\s+(?:SOME\s+)?PARTIALS?|SECURE\s+(?:SOME\s+)?(?:PROFIT|PARTIAL)S?|BOOK\s+(?:SOME\s+)?PARTIALS?|CHIUDI\s+(?:META|PARZIALE)|CHIUDERE\s+META)")),
    ("close_all", re.compile(r"\b(CLOSE\s+(?:ALL|NOW|IT|EARLY|(?:THE\s+|YOUR\s+|ALL\s+)?(?:TRADES?|POSITIONS?|ORDERS?|BUYS?|SELLS?))|CLOSE\s+[A-Z]{3,6}\s+(?:NOW|TRADES?|BUYS?|SELLS?)|EXIT\s+(?:NOW|ALL|THE\s+TRADE)|CHIUDI(?:\s+TUTTO)?|CHIUDERE\s+TUTTO|CLOSE\s*$)")),
    ("move_sl_be", re.compile(r"(\b(?:SL|STOP\s*LOSS|STOP)\s+(?:TO|AT|ON|A)\s+(?:BE|B\.E\.?|BREAK\s*EVEN|BREAKEVEN|ENTRY|ENTRATA|PAREGGIO|OPEN(?:ING)?\s+PRICE)\b|\b(?:MOVE|SET|PUT)\s+(?:THE\s+|YOUR\s+)?(?:SL|STOP\s*LOSS|STOP)\s+(?:TO\s+)?(?:BE|B\.E\.?|BREAK\s*EVEN|BREAKEVEN|ENTRY)\b|\bBREAK\s*EVEN\b|\bBREAKEVEN\b|\bRISK\s*FREE\b|\bSL\s*=\s*ENTRY\b|\bPAREGGIO\b)")),
    ("modify_sl", re.compile(r"\b(?:MOVE|NEW|CHANGE|UPDATE|SET|SPOSTA|MODIFY|TRAIL)\s+(?:THE\s+|YOUR\s+)?(?:SL|STOP\s*LOSS|STOP)\s*(?:TO|AT|A|:|=)?\s*" + NUM)),
    ("modify_tp", re.compile(r"\b(?:MOVE|NEW|CHANGE|UPDATE|SET|SPOSTA|MODIFY)\s+(?:THE\s+|YOUR\s+)?(?:TP|TAKE\s*PROFIT|TARGET)\s*(?:TO|AT|A|:|=)?\s*" + NUM)),
    ("info", re.compile(r"\b(TP\s*\d?\s+(?:HIT|DONE|REACHED|SMASHED|PRESO)|SL\s+(?:HIT|PRESO)|STOP(?:PED)?\s+OUT|\+\s?\d+\s*PIPS?|RUNNING|IN\s+PROFIT)\b")),
]


def parse_update(t: str, is_reply: bool, aliases=None) -> dict | None:
    short = len(t) <= 220
    for action, rx in UPD:
        m = rx.search(t)
        if not m:
            continue
        if action == "move_sl_be" and not (short or is_reply):
            continue
        if action == "close_all" and not (short or is_reply):
            continue
        u = {"kind": "update", "action": action, "percent": None, "price": None,
             "symbol": find_symbol(t, aliases), "side": None}
        sm = SIDE_RE.search(t)
        if sm:
            u["side"] = SIDE_MAP[sm.group(1)]
        if action == "close_partial":
            pm = re.search(r"(\d{1,2})\s*%", t)
            u["percent"] = float(pm.group(1)) if pm else 50.0
        if action in ("modify_sl", "modify_tp"):
            u["price"] = _f(m.group(m.lastindex))
        return u
    # reply corta "SL 2655" / "TP 2680" senza BUY/SELL -> modifica
    if is_reply and short and not SIDE_RE.search(t):
        m = SL_RE.search(t)
        if m and not m.group(2):
            return {"kind": "update", "action": "modify_sl", "price": _f(m.group(1)), "percent": None, "symbol": None, "side": None}
        m = TP_RE.search(t)
        if m and not m.group(3):
            return {"kind": "update", "action": "modify_tp", "price": _f(m.group(2)), "percent": None, "symbol": None, "side": None}
    return None


def parse(text: str, is_reply: bool = False, aliases: dict | None = None) -> dict | None:
    t = normalize(text)
    if not t:
        return None
    sig = parse_signal(t, aliases)
    if sig and not sig.get("_suspect"):
        return sig
    upd = parse_update(t, is_reply, aliases)
    if upd:
        return upd
    return sig  # eventualmente sospetto: il chiamante puo' chiedere a Gemini


def worth_ai(text: str) -> bool:
    """Vale la pena chiedere a Gemini? (evita chiamate su chiacchiere/foto/saluti)"""
    t = normalize(text)
    if len(t) < 4 or len(t) > 1500:
        return False
    if re.search(r"\d", t) and re.search(r"\b(BUY|SELL|LONG|SHORT|SL|TP|STOP|TARGET|ENTRY|COMPRA|VENDI)\b", t):
        return True
    if re.search(r"\b(CLOSE|CHIUDI|BE|BREAK|EVEN|CANCEL|PARTIAL|SECURE|EXIT|MOVE|SPOSTA)\b", t) and len(t) < 300:
        return True
    return False
