"""Interfaccia con MetaTrader 5. Tutte le chiamate passano da un unico thread (la libreria MT5 non e' thread-safe)."""
from __future__ import annotations

import asyncio
import logging
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

log = logging.getLogger("mt5")

FX = {"EUR", "USD", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD", "SGD", "HKD", "NOK", "SEK", "ZAR", "MXN", "TRY", "PLN"}


class Broker:
    def __init__(self, mt5, path="", login=0, password="", server=""):
        self.mt5 = mt5
        self.path, self.login, self.password, self.server = path, login, password, server
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mt5")
        self.connected = False
        self._sym_cache: dict[str, str | None] = {}

    async def call(self, fn, *a, **kw):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.pool, lambda: fn(*a, **kw))

    # ------------------------------------------------------------ connessione
    def connect(self) -> bool:
        m = self.mt5
        kw = {}
        if self.path:
            kw["path"] = self.path
        if self.login:
            kw.update(login=self.login, password=self.password, server=self.server)
        ok = m.initialize(**kw)
        if not ok:
            log.error("MT5 initialize fallito: %s", m.last_error())
        self.connected = bool(ok and m.account_info())
        return self.connected

    def ensure(self) -> bool:
        if self.mt5.terminal_info() is None or self.mt5.account_info() is None:
            self.connected = False
            return self.connect()
        self.connected = True
        return True

    def account(self) -> dict | None:
        a = self.mt5.account_info()
        if not a:
            return None
        return {
            "account_login": a.login, "account_server": a.server, "account_name": a.name,
            "account_demo": a.trade_mode != self.mt5.ACCOUNT_TRADE_MODE_REAL,
            "currency": a.currency, "balance": a.balance, "equity": a.equity, "margin_free": a.margin_free,
        }

    # ------------------------------------------------------------ simboli
    def resolve(self, base: str, suffix: str = "") -> str | None:
        key = f"{base}|{suffix}"
        if key in self._sym_cache:
            return self._sym_cache[key]
        m = self.mt5
        found = None
        for cand in [base + suffix, base]:
            if cand and m.symbol_info(cand) is not None:
                found = cand
                break
        if not found:
            syms = m.symbols_get(f"*{base}*") or []
            names = sorted((s.name for s in syms), key=len)
            found = names[0] if names else None
        if found:
            m.symbol_select(found, True)
        self._sym_cache[key] = found
        return found

    def pip(self, sym: str) -> float:
        s = sym.upper()
        if "XAU" in s:
            return 0.1
        if "XAG" in s:
            return 0.01
        core = re.sub(r"[^A-Z]", "", s)[:6]
        if len(core) == 6 and core[:3] in FX and core[3:] in FX:
            return 0.01 if "JPY" in core else 0.0001
        info = self.mt5.symbol_info(sym)
        return 1.0 if info is None or info.point >= 0.01 else info.point * 10

    def tick(self, sym):
        return self.mt5.symbol_info_tick(sym)

    def info(self, sym):
        return self.mt5.symbol_info(sym)

    def norm_price(self, sym, price):
        if price is None:
            return 0.0
        return round(price, self.mt5.symbol_info(sym).digits)

    def norm_volume(self, sym, vol: float) -> float:
        i = self.mt5.symbol_info(sym)
        step = i.volume_step or 0.01
        v = math.floor(vol / step + 1e-9) * step
        v = min(v, i.volume_max)
        return round(v, 2 if step >= 0.01 else 3)

    def vol_limits(self, sym):
        i = self.mt5.symbol_info(sym)
        return i.volume_min, i.volume_max, i.volume_step

    def loss_per_lot(self, sym, side, entry, sl) -> float | None:
        m = self.mt5
        t = m.ORDER_TYPE_BUY if side == "BUY" else m.ORDER_TYPE_SELL
        p = m.order_calc_profit(t, sym, 1.0, entry, sl)
        return abs(p) if p else None

    # ------------------------------------------------------------ ordini
    def _fillings(self, sym):
        m = self.mt5
        fm = getattr(m.symbol_info(sym), "filling_mode", 0) or 0
        out = []
        if fm & 1:
            out.append(m.ORDER_FILLING_FOK)
        if fm & 2:
            out.append(m.ORDER_FILLING_IOC)
        out.append(m.ORDER_FILLING_RETURN)
        return out

    def _send(self, req, sym):
        m = self.mt5
        res = None
        for f in self._fillings(sym):
            req["type_filling"] = f
            res = m.order_send(req)
            if res is None:
                return False, None, f"order_send None {m.last_error()}"
            if res.retcode == 10030:   # filling non supportato -> prova il successivo
                continue
            break
        ok = res.retcode in (m.TRADE_RETCODE_DONE, m.TRADE_RETCODE_PLACED, 10008)
        return ok, res, f"{res.retcode} {res.comment}"

    def market(self, sym, side, vol, sl, tp, comment, magic, deviation=30):
        m = self.mt5
        t = self.tick(sym)
        req = {
            "action": m.TRADE_ACTION_DEAL, "symbol": sym, "volume": float(vol),
            "type": m.ORDER_TYPE_BUY if side == "BUY" else m.ORDER_TYPE_SELL,
            "price": t.ask if side == "BUY" else t.bid,
            "sl": self.norm_price(sym, sl), "tp": self.norm_price(sym, tp),
            "deviation": deviation, "magic": magic, "comment": comment[:31],
            "type_time": m.ORDER_TIME_GTC,
        }
        ok, res, msg = self._send(req, sym)
        if not ok and res is not None and res.retcode == 10016 and (sl or tp):
            # stop non validi: apri senza e prova a impostarli dopo
            req["sl"], req["tp"] = 0.0, 0.0
            ok, res, msg = self._send(req, sym)
            if ok:
                self.modify(res.order, sym, sl, tp)
                msg += " (SL/TP impostati dopo)"
        return ok, (res.order if ok else None), (res.price if ok else None), msg

    def pending(self, sym, side, kind, price, vol, sl, tp, comment, magic):
        m = self.mt5
        types = {("BUY", "limit"): m.ORDER_TYPE_BUY_LIMIT, ("SELL", "limit"): m.ORDER_TYPE_SELL_LIMIT,
                 ("BUY", "stop"): m.ORDER_TYPE_BUY_STOP, ("SELL", "stop"): m.ORDER_TYPE_SELL_STOP}
        req = {
            "action": m.TRADE_ACTION_PENDING, "symbol": sym, "volume": float(vol), "type": types[(side, kind)],
            "price": self.norm_price(sym, price), "sl": self.norm_price(sym, sl), "tp": self.norm_price(sym, tp),
            "magic": magic, "comment": comment[:31], "type_time": m.ORDER_TIME_GTC,
        }
        ok, res, msg = self._send(req, sym)
        return ok, (res.order if ok else None), price, msg

    def modify(self, ticket, sym, sl=None, tp=None):
        m = self.mt5
        pos = m.positions_get(ticket=ticket)
        if pos:
            p = pos[0]
            req = {"action": m.TRADE_ACTION_SLTP, "position": ticket, "symbol": p.symbol,
                   "sl": self.norm_price(p.symbol, sl if sl is not None else p.sl),
                   "tp": self.norm_price(p.symbol, tp if tp is not None else p.tp), "magic": p.magic}
            res = m.order_send(req)
            return bool(res and res.retcode == m.TRADE_RETCODE_DONE), f"{getattr(res, 'retcode', None)} {getattr(res, 'comment', m.last_error())}"
        od = m.orders_get(ticket=ticket)
        if od:
            o = od[0]
            req = {"action": m.TRADE_ACTION_MODIFY, "order": ticket, "symbol": o.symbol, "price": o.price_open,
                   "sl": self.norm_price(o.symbol, sl if sl is not None else o.sl),
                   "tp": self.norm_price(o.symbol, tp if tp is not None else o.tp), "type_time": m.ORDER_TIME_GTC}
            res = m.order_send(req)
            return bool(res and res.retcode == m.TRADE_RETCODE_DONE), f"{getattr(res, 'retcode', None)}"
        return False, "ticket non trovato"

    def close(self, ticket, volume=None):
        m = self.mt5
        pos = m.positions_get(ticket=ticket)
        if not pos:
            od = m.orders_get(ticket=ticket)
            if od:
                return self.cancel(ticket)
            return False, "posizione non trovata"
        p = pos[0]
        vol = p.volume if volume is None else min(volume, p.volume)
        t = self.tick(p.symbol)
        sell = p.type == m.POSITION_TYPE_BUY
        req = {"action": m.TRADE_ACTION_DEAL, "symbol": p.symbol, "volume": float(vol), "position": ticket,
               "type": m.ORDER_TYPE_SELL if sell else m.ORDER_TYPE_BUY,
               "price": t.bid if sell else t.ask, "deviation": 50, "magic": p.magic,
               "comment": "SB close", "type_time": m.ORDER_TIME_GTC}
        ok, res, msg = self._send(req, p.symbol)
        return ok, msg

    def cancel(self, ticket):
        m = self.mt5
        res = m.order_send({"action": m.TRADE_ACTION_REMOVE, "order": ticket})
        return bool(res and res.retcode == m.TRADE_RETCODE_DONE), f"{getattr(res, 'retcode', None)}"

    # ------------------------------------------------------------ lettura
    def positions(self, magic=None) -> list[dict]:
        m = self.mt5
        out = []
        for p in m.positions_get() or []:
            if magic and p.magic != magic:
                continue
            out.append({"ticket": p.ticket, "symbol": p.symbol, "side": "BUY" if p.type == m.POSITION_TYPE_BUY else "SELL",
                        "volume": p.volume, "price_open": p.price_open, "price_current": p.price_current,
                        "sl": p.sl, "tp": p.tp, "profit": round(p.profit + getattr(p, "swap", 0), 2),
                        "comment": p.comment, "kind": "position"})
        return out

    def orders(self, magic=None) -> list[dict]:
        m = self.mt5
        out = []
        for o in m.orders_get() or []:
            if magic and o.magic != magic:
                continue
            out.append({"ticket": o.ticket, "symbol": o.symbol, "volume": o.volume_current,
                        "price_open": o.price_open, "sl": o.sl, "tp": o.tp, "comment": o.comment, "kind": "order"})
        return out

    def closed_info(self, ticket):
        m = self.mt5
        deals = m.history_deals_get(position=ticket) or []
        outs = [d for d in deals if d.entry in (m.DEAL_ENTRY_OUT, m.DEAL_ENTRY_OUT_BY)]
        if not outs:
            return None, None
        profit = sum(d.profit + getattr(d, "swap", 0) + getattr(d, "commission", 0) for d in deals)
        return outs[-1].price, round(profit, 2)

    def closed_profit_today(self, magic) -> float:
        m = self.mt5
        start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        deals = m.history_deals_get(start, datetime.now() + timedelta(days=1)) or []
        return sum(d.profit + getattr(d, "swap", 0) + getattr(d, "commission", 0) for d in deals if d.magic == magic)
