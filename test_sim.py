"""Simulazione end-to-end del motore con MT5 finto e DB in memoria."""
import asyncio, os, sys, itertools
from datetime import datetime, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sim import fake_mt5 as mt5  # noqa
from mt5_exec import Broker      # noqa
from manager import Manager      # noqa


class FakeDB:
    def __init__(self):
        self.settings_row = {"id": 1, "trading_enabled": True, "allow_real_account": False, "symbol_suffix": "",
                             "symbol_aliases": {}, "max_open_positions": 20, "daily_loss_limit_pct": 5,
                             "magic_number": 770077, "ai_enabled": False}
        self.chans = {-100: {"id": -100, "title": "Gold VIP", "enabled": True, "risk_mode": "fixed_lot", "risk_value": 0.03,
                             "max_lot": 1, "tp_mode": "split", "default_sl_pips": 40, "max_slippage_pips": 0,
                             "be_after_tp1": True, "follow_updates": True}}
        self.signals, self.trades, self.status = {}, {}, {}
        self.ids = itertools.count(1)

    async def settings(self): return self.settings_row
    async def channels(self): return list(self.chans.values())
    async def touch_channel(self, *a, **k): pass
    async def get_signal(self, c, m):
        return next((s for s in self.signals.values() if s["channel_id"] == c and s["message_id"] == m), None)
    async def upsert_signal(self, row):
        ex = await self.get_signal(row["channel_id"], row["message_id"])
        if ex:
            ex.update(row); return ex
        row = {**row, "id": next(self.ids), "created_at": datetime.now(timezone.utc).isoformat()}
        self.signals[row["id"]] = row; return row
    async def update_signal(self, sid, p): self.signals[sid].update(p)
    async def last_signals(self, c, since):
        r = [s for s in self.signals.values() if s["channel_id"] == c and s["kind"] == "signal" and s["status"] in ("executed", "partial")]
        return sorted(r, key=lambda s: s["id"], reverse=True)
    async def insert_trade(self, row): self.trades[row["ticket"]] = dict(row)
    async def trades_for_signal(self, sid, active_only=True):
        return sorted([t for t in self.trades.values() if t["signal_id"] == sid and (not active_only or t["status"] in ("open", "pending"))], key=lambda t: t["tp_index"])
    async def active_trades(self): return [dict(t) for t in self.trades.values() if t["status"] in ("open", "pending")]
    async def update_trade(self, tk, p): self.trades[tk].update(p)
    async def count_trades(self, c): return len(self.trades)
    async def set_status(self, p): self.status = p


def last(db): return db.signals[max(db.signals)]


async def run():
    db = FakeDB()
    b = Broker(mt5)
    m = Manager(db, b, None)
    await b.call(b.connect)
    await m.refresh()
    await m.heartbeat(True, "test")
    now = datetime.now(timezone.utc)

    # 1) segnale classico, 3 TP -> 3 posizioni da 0.01
    await m.on_message(-100, 1, "XAUUSD BUY 2650\nSL 2640\nTP 2655\nTP 2660\nTP 2670", None, now)
    s = last(db); print("1:", s["status"], s["reason"])
    assert s["status"] == "executed" and len(mt5.state.positions) == 3

    # 2) prezzo raggiunge TP1 -> la posizione 1 chiude, le altre a pareggio
    mt5.set_price("XAUUSD", 2656)
    await m.heartbeat(True, "test")
    ps = list(mt5.state.positions.values())
    print("2: aperte", len(ps), "SL", [p.sl for p in ps])
    assert len(ps) == 2 and all(abs(p.sl - p.price_open) < 1e-6 for p in ps)

    # 3) risposta "close half" -> chiude 1 delle 2 posizioni da 0.01
    await m.on_message(-100, 2, "close half", 1, now)
    print("3:", last(db)["status"], last(db)["reason"])
    assert len(mt5.state.positions) == 1

    # 4) "CLOSE ALL" senza reply -> trova ultimo segnale
    await m.on_message(-100, 3, "CLOSE ALL NOW", None, now)
    print("4:", last(db)["status"], last(db)["reason"])
    assert len(mt5.state.positions) == 0

    # 5) BUY NOW senza SL -> SL emergenza 40 pips, poi modifica messaggio con SL/TP veri
    mt5.set_price("XAUUSD", 2650)
    await m.on_message(-100, 4, "GOLD BUY NOW", None, now)
    s = last(db); print("5:", s["status"], s["reason"])
    p = list(mt5.state.positions.values())[0]
    assert abs(p.sl - (2650.30 - 4.0)) < 0.01
    await m.on_message(-100, 4, "GOLD BUY NOW\nSL 2644\nTP 2662", None, now, edited=True)
    p = list(mt5.state.positions.values())[0]
    print("5b: SL", p.sl, "TP", p.tp)
    assert p.sl == 2644 and p.tp == 2662

    # 6) move sl / be
    await m.on_message(-100, 5, "move sl to 2648", 4, now)
    assert list(mt5.state.positions.values())[0].sl == 2648
    await m.on_message(-100, 6, "SL to BE", 4, now)
    p = list(mt5.state.positions.values())[0]
    assert p.sl == p.price_open
    print("6: ok BE")

    # 7) rischio % : 1% di 10000 = 100€ con SL 10$ su XAU -> 0.10 lotti
    db.chans[-100].update(risk_mode="risk_pct", risk_value=1, tp_mode="first")
    await m.on_message(-100, 7, "XAUUSD SELL 2650\nSL 2660.00\nTP 2640", None, now)
    s = last(db); print("7:", s["status"], s["reason"])
    assert "0.1 lotti" in s["reason"]

    # 8) ordine limit lontano + cancel
    await m.on_message(-100, 8, "EURUSD BUY LIMIT 1.0800\nSL 1.0770\nTP 1.0850", None, now)
    print("8:", last(db)["status"], last(db)["reason"]); assert len(mt5.state.orders) == 1
    await m.on_message(-100, 9, "cancel", 8, now)
    assert len(mt5.state.orders) == 0
    await m.heartbeat(True, "test")

    # 9) sicurezze: conto reale bloccato, trading spento, SL incoerente, simbolo assente
    mt5.state.trade_mode = mt5.ACCOUNT_TRADE_MODE_REAL
    await m.on_message(-100, 10, "XAUUSD BUY 2650 SL 2640 TP 2660", None, now)
    print("9a:", last(db)["reason"]); assert "REALE" in last(db)["reason"]
    mt5.state.trade_mode = 0
    db.settings_row["trading_enabled"] = False
    await m.on_message(-100, 11, "XAUUSD BUY 2650 SL 2640 TP 2660", None, now)
    assert "SPENTO" in last(db)["reason"]
    db.settings_row["trading_enabled"] = True
    await m.on_message(-100, 12, "XAUUSD BUY 2650 SL 2660 TP 2640", None, now)
    print("9c:", last(db)["reason"]); assert last(db)["status"] == "skipped"
    await m.on_message(-100, 13, "AUDNZD BUY 1.10 SL 1.09 TP 1.11", None, now)
    print("9d:", last(db)["reason"]); assert "non trovato" in last(db)["reason"]

    # 10) chiacchiere ignorate (non salvate)
    n = len(db.signals)
    await m.on_message(-100, 14, "Buongiorno a tutti, oggi mercato tranquillo", None, now)
    assert len(db.signals) == n

    # 11) comando close_all dall'app
    ok, res = await m.run_command({"type": "close_all", "payload": {}})
    print("11:", res); assert not mt5.state.positions
    await m.heartbeat(True, "test")
    print("status balance", round(db.status["balance"], 2), "posizioni", len(db.status["positions"]))
    print("\nSIMULAZIONE OK")


asyncio.run(run())
