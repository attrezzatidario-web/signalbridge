"""Database locale (SQLite) sulla VPS + notifiche live verso l'app."""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("store")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


DEFAULT_SETTINGS = {
    "trading_enabled": False,
    "allow_real_account": False,
    "symbol_suffix": "",
    "symbol_aliases": {"GOLD": "XAUUSD", "XAU": "XAUUSD", "SILVER": "XAGUSD", "DJ30": "US30",
                       "NASDAQ": "NAS100", "US100": "NAS100", "SPX500": "US500", "BTC": "BTCUSD", "ETH": "ETHUSD"},
    "max_open_positions": 20,
    "daily_loss_limit_pct": 5,
    "magic_number": 770077,
    "ai_enabled": True,
    "default_risk_mode": "fixed_lot",
    "default_risk_value": 0.01,
}

CHANNEL_DEFAULTS = {
    "enabled": False, "risk_mode": "fixed_lot", "risk_value": 0.01, "max_lot": 1.0, "tp_mode": "split",
    "default_sl_pips": 40, "max_slippage_pips": 0, "be_after_tp1": True, "follow_updates": True,
    "trades_count": 0, "last_message_at": None,
}

SCHEMA = """
create table if not exists kv (k text primary key, v text not null);
create table if not exists channels (id integer primary key, data text not null);
create table if not exists signals (
  id integer primary key autoincrement,
  channel_id integer not null, channel_title text, message_id integer not null, reply_to_id integer,
  text text not null, kind text not null default 'unknown', parsed text, parser text,
  status text not null default 'received', reason text, edited integer not null default 0,
  created_at text not null, unique (channel_id, message_id));
create index if not exists signals_created on signals(created_at);
create table if not exists trades (
  id integer primary key autoincrement, signal_id integer, channel_id integer, channel_title text,
  ticket integer not null unique, symbol text not null, side text not null, order_kind text not null default 'market',
  volume real not null, open_price real, sl real, tp real, tp_index integer,
  status text not null default 'open', close_price real, profit real, opened_at text not null, closed_at text);
create index if not exists trades_status on trades(status);
"""

SIGNAL_COLS = ["channel_id", "channel_title", "message_id", "reply_to_id", "text", "kind", "parsed", "parser",
               "status", "reason", "edited", "created_at"]
TRADE_COLS = ["signal_id", "channel_id", "channel_title", "ticket", "symbol", "side", "order_kind", "volume",
              "open_price", "sl", "tp", "tp_index", "status", "close_price", "profit", "opened_at", "closed_at"]


class Store:
    def __init__(self, path: str | Path):
        self.con = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.con.row_factory = sqlite3.Row
        self.con.execute("pragma journal_mode=wal")
        self.con.executescript(SCHEMA)
        self.lock = threading.Lock()
        self.listeners = []          # funzioni(table, row) chiamate a ogni modifica
        self.status: dict = {"engine_online": False, "positions": []}

    # ------------------------------------------------------------ utilità
    def _emit(self, table, row):
        for fn in list(self.listeners):
            try:
                fn(table, row)
            except Exception:
                log.exception("listener")

    def _q(self, sql, args=()):
        with self.lock:
            return self.con.execute(sql, args).fetchall()

    def _x(self, sql, args=()):
        with self.lock:
            cur = self.con.execute(sql, args)
            return cur.lastrowid

    @staticmethod
    def _sig(r):
        if r is None:
            return None
        d = dict(r)
        d["parsed"] = json.loads(d["parsed"]) if d.get("parsed") else None
        d["edited"] = bool(d.get("edited"))
        return d

    def kv_get(self, k, default=None):
        r = self._q("select v from kv where k=?", (k,))
        return json.loads(r[0]["v"]) if r else default

    def kv_set(self, k, v):
        self._x("insert into kv(k,v) values(?,?) on conflict(k) do update set v=excluded.v", (k, json.dumps(v)))

    # ------------------------------------------------------------ settings
    def get_settings(self) -> dict:
        return {**DEFAULT_SETTINGS, **(self.kv_get("settings", {}) or {})}

    def update_settings(self, patch: dict) -> dict:
        s = self.get_settings()
        s.update({k: v for k, v in patch.items() if k in DEFAULT_SETTINGS})
        self.kv_set("settings", s)
        self._emit("settings", s)
        return s

    async def settings(self):
        return self.get_settings()

    # ------------------------------------------------------------ channels
    def list_channels(self) -> list[dict]:
        return [{**CHANNEL_DEFAULTS, **json.loads(r["data"]), "id": r["id"]} for r in self._q("select * from channels")]

    def get_channel(self, cid):
        r = self._q("select * from channels where id=?", (cid,))
        return {**CHANNEL_DEFAULTS, **json.loads(r[0]["data"]), "id": cid} if r else None

    def update_channel(self, cid: int, patch: dict):
        c = self.get_channel(cid)
        if not c:
            return None
        allowed = set(CHANNEL_DEFAULTS) | {"title", "username", "kind"}
        c.update({k: v for k, v in patch.items() if k in allowed})
        c.pop("id", None)
        self._x("update channels set data=? where id=?", (json.dumps(c), cid))
        c["id"] = cid
        self._emit("channels", c)
        return c

    async def channels(self):
        return self.list_channels()

    async def sync_channels(self, dialogs: list[dict], defaults: dict) -> int:
        new = 0
        for d in dialogs:
            if self.get_channel(d["id"]):
                self.update_channel(d["id"], {"title": d["title"], "username": d.get("username"), "kind": d.get("kind")})
            else:
                data = {**CHANNEL_DEFAULTS, **defaults, "title": d["title"], "username": d.get("username"), "kind": d.get("kind")}
                self._x("insert into channels(id,data) values(?,?)", (d["id"], json.dumps(data)))
                self._emit("channels", {**data, "id": d["id"]})
                new += 1
        return new

    async def touch_channel(self, cid, trade=False, count=0):
        patch = {"last_message_at": now_iso()}
        if trade:
            patch["trades_count"] = count
        self.update_channel(cid, patch)

    # ------------------------------------------------------------ signals
    def list_signals(self, limit=150):
        return [self._sig(r) for r in self._q("select * from signals order by id desc limit ?", (limit,))]

    async def get_signal(self, channel_id, message_id):
        r = self._q("select * from signals where channel_id=? and message_id=?", (channel_id, message_id))
        return self._sig(r[0]) if r else None

    def _signal_by_id(self, sid):
        r = self._q("select * from signals where id=?", (sid,))
        return self._sig(r[0]) if r else None

    async def upsert_signal(self, row: dict):
        row = {**row}
        row.setdefault("created_at", now_iso())
        row["parsed"] = json.dumps(row.get("parsed")) if row.get("parsed") is not None else None
        row["edited"] = int(bool(row.get("edited")))
        cols = [c for c in SIGNAL_COLS if c in row]
        upd = ",".join(f"{c}=excluded.{c}" for c in cols if c not in ("channel_id", "message_id", "created_at"))
        self._x(f"insert into signals({','.join(cols)}) values({','.join('?' * len(cols))}) "
                f"on conflict(channel_id,message_id) do update set {upd}", [row[c] for c in cols])
        s = await self.get_signal(row["channel_id"], row["message_id"])
        self._emit("signals", s)
        return s

    async def update_signal(self, sid, patch: dict):
        patch = {k: v for k, v in patch.items() if k in SIGNAL_COLS}
        if "parsed" in patch:
            patch["parsed"] = json.dumps(patch["parsed"]) if patch["parsed"] is not None else None
        if "edited" in patch:
            patch["edited"] = int(bool(patch["edited"]))
        if not patch:
            return
        self._x(f"update signals set {','.join(f'{k}=?' for k in patch)} where id=?", [*patch.values(), sid])
        self._emit("signals", self._signal_by_id(sid))

    async def last_signals(self, channel_id, since_iso):
        rows = self._q("select * from signals where channel_id=? and kind='signal' and status in ('executed','partial') "
                       "and created_at>=? order by id desc limit 10", (channel_id, since_iso))
        return [self._sig(r) for r in rows]

    # ------------------------------------------------------------ trades
    def list_trades(self, limit=2000):
        return [dict(r) for r in self._q("select * from trades order by id desc limit ?", (limit,))]

    def _trade(self, ticket):
        r = self._q("select * from trades where ticket=?", (ticket,))
        return dict(r[0]) if r else None

    async def insert_trade(self, row: dict):
        row = {**row, "opened_at": row.get("opened_at") or now_iso()}
        cols = [c for c in TRADE_COLS if c in row]
        self._x(f"insert or replace into trades({','.join(cols)}) values({','.join('?' * len(cols))})", [row[c] for c in cols])
        self._emit("trades", self._trade(row["ticket"]))

    async def trades_for_signal(self, sid, active_only=True):
        q = "select * from trades where signal_id=?" + (" and status in ('open','pending')" if active_only else "") + " order by tp_index"
        return [dict(r) for r in self._q(q, (sid,))]

    async def active_trades(self):
        return [dict(r) for r in self._q("select * from trades where status in ('open','pending')")]

    async def update_trade(self, ticket, patch: dict):
        patch = {k: v for k, v in patch.items() if k in TRADE_COLS}
        if not patch:
            return
        self._x(f"update trades set {','.join(f'{k}=?' for k in patch)} where ticket=?", [*patch.values(), ticket])
        self._emit("trades", self._trade(ticket))

    async def count_trades(self, channel_id):
        return self._q("select count(*) n from trades where channel_id=?", (channel_id,))[0]["n"]

    # ------------------------------------------------------------ status
    async def set_status(self, payload: dict):
        self.status.update(payload)
        self.status["last_seen"] = now_iso()
        self._emit("status", self.status)

    async def cleanup(self):
        self._x("delete from signals where status='ignored' and created_at < datetime('now','-30 days')")
