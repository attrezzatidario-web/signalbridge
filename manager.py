"""Logica: messaggio -> segnale/aggiornamento -> ordini MT5, sicurezze, monitoraggio."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from parser import parse, worth_ai

log = logging.getLogger("manager")

MAX_SIGNAL_AGE = timedelta(minutes=3)
EDIT_WINDOW = timedelta(minutes=15)


def utcnow():
    return datetime.now(timezone.utc)


class Manager:
    def __init__(self, db, broker, ai):
        self.db, self.broker, self.ai = db, broker, ai
        self.settings: dict = {}
        self.channels: dict[int, dict] = {}
        self.lock = asyncio.Lock()
        self.day = None
        self.day_start_balance = None
        self.account: dict | None = None
        self.be_done: set[int] = set()

    # ------------------------------------------------------------ stato
    async def refresh(self):
        s = await self.db.settings()
        if s:
            self.settings = s
        chs = await self.db.channels()
        if chs is not None:
            self.channels = {c["id"]: c for c in chs}

    def enabled_ids(self) -> set[int]:
        return {cid for cid, c in self.channels.items() if c.get("enabled")}

    @property
    def magic(self) -> int:
        return int(self.settings.get("magic_number") or 770077)

    def aliases(self) -> dict:
        return self.settings.get("symbol_aliases") or {}

    # ------------------------------------------------------------ parsing
    async def parse(self, text: str, is_reply: bool):
        p = parse(text, is_reply, self.aliases())
        if p and not p.get("_suspect"):
            return p, "regex"
        if self.ai and self.ai.ready and self.settings.get("ai_enabled", True) and (p or worth_ai(text)):
            a = await self.ai.parse(text, is_reply)
            if a:
                return a, "ai"
        if p:
            return p, "regex"
        return None, None

    # ------------------------------------------------------------ ingresso messaggi
    async def on_message(self, chat_id: int, msg_id: int, text: str, reply_to: int | None,
                         date: datetime | None = None, edited: bool = False):
        ch = self.channels.get(chat_id)
        if not ch or not ch.get("enabled") or not text:
            return
        await self.db.touch_channel(chat_id)
        parsed, src = await self.parse(text, bool(reply_to))

        if edited:
            existing = await self.db.get_signal(chat_id, msg_id)
            if existing:
                return await self.on_edit(existing, parsed, src, text, ch, date)
            if date and utcnow() - date > EDIT_WINDOW:
                return

        if parsed is None:
            return
        row = await self.db.upsert_signal({
            "channel_id": chat_id, "channel_title": ch.get("title"), "message_id": msg_id,
            "reply_to_id": reply_to, "text": text[:4000], "kind": parsed["kind"],
            "parsed": parsed, "parser": src, "status": "received", "edited": edited,
        })
        if not row:
            return
        if date and utcnow() - date > (EDIT_WINDOW if edited else MAX_SIGNAL_AGE) and parsed["kind"] == "signal":
            return await self.db.update_signal(row["id"], {"status": "skipped", "reason": "messaggio troppo vecchio"})

        if parsed["kind"] == "signal":
            await self.exec_signal(row, parsed, ch)
        else:
            await self.route_update(row, parsed, ch, reply_to)

    async def route_update(self, row, u, ch, reply_to):
        if u["action"] == "info":
            return await self.db.update_signal(row["id"], {"status": "ignored", "reason": "solo report risultato"})
        if not ch.get("follow_updates", True):
            return await self.db.update_signal(row["id"], {"status": "skipped", "reason": "aggiornamenti disattivati per il gruppo"})
        await self.exec_update(row, u, ch, reply_to)

    async def on_edit(self, existing, parsed, src, text, ch, date):
        await self.db.update_signal(existing["id"], {"text": text[:4000], "edited": True})
        if not parsed or parsed["kind"] != "signal":
            return
        if existing["kind"] == "signal" and existing["status"] in ("executed", "partial"):
            # aggiorna SL/TP dei trade gia' aperti
            trades = await self.db.trades_for_signal(existing["id"])
            tps = parsed.get("tps") or []
            changed = 0
            async with self.lock:
                for t in trades:
                    new_sl = parsed.get("sl")
                    idx = t.get("tp_index")
                    new_tp = tps[idx] if idx is not None and idx < len(tps) else None
                    if new_sl is None and new_tp is None:
                        continue
                    ok, _ = await self.broker.call(self.broker.modify, t["ticket"], t["symbol"], new_sl, new_tp)
                    if ok:
                        changed += 1
                        await self.db.update_trade(t["ticket"], {k: v for k, v in (("sl", new_sl), ("tp", new_tp)) if v is not None})
            await self.db.update_signal(existing["id"], {"parsed": parsed, "reason": f"modifica messaggio: aggiornati {changed} ordini"})
        elif existing["status"] not in ("executed", "partial") and (not date or utcnow() - date < EDIT_WINDOW):
            row = {**existing, "parsed": parsed}
            await self.db.update_signal(existing["id"], {"kind": "signal", "parsed": parsed, "parser": src})
            await self.exec_signal(row, parsed, ch)

    # ------------------------------------------------------------ sicurezze
    async def guard(self) -> str | None:
        s = self.settings
        if not s.get("trading_enabled"):
            return "trading generale SPENTO"
        acc = await self.broker.call(self.broker.account)
        if not acc:
            return "MT5 non connesso"
        self.account = acc
        if not acc["account_demo"] and not s.get("allow_real_account"):
            return "conto REALE bloccato (abilitalo nelle impostazioni)"
        pos = await self.broker.call(self.broker.positions, self.magic)
        if len(pos) >= int(s.get("max_open_positions") or 20):
            return "raggiunto massimo posizioni aperte"
        lim = float(s.get("daily_loss_limit_pct") or 0)
        if lim > 0 and self.day_start_balance:
            if acc["equity"] <= self.day_start_balance * (1 - lim / 100):
                return f"limite perdita giornaliera {lim}% raggiunto"
        return None

    # ------------------------------------------------------------ nuovo segnale
    async def exec_signal(self, row: dict, s: dict, ch: dict):
        async with self.lock:
            try:
                status, reason = await self._exec_signal(row, s, ch)
            except Exception as e:
                log.exception("errore esecuzione")
                status, reason = "error", f"errore: {e}"
        await self.db.update_signal(row["id"], {"status": status, "reason": reason})
        log.info("[%s] %s %s -> %s %s", ch.get("title"), s.get("side"), s.get("symbol"), status, reason)

    async def _exec_signal(self, row, s, ch):
        b = self.broker
        if s.get("_suspect"):
            return "skipped", "livelli SL/TP incoerenti"
        g = await self.guard()
        if g:
            return "skipped", g

        base = (self.aliases().get(s["symbol"]) or s["symbol"]).upper()
        sym = await b.call(b.resolve, base, self.settings.get("symbol_suffix") or "")
        if not sym:
            return "skipped", f"simbolo {base} non trovato sul broker"
        tick = await b.call(b.tick, sym)
        if not tick:
            return "skipped", f"nessun prezzo per {sym}"
        side = s["side"]
        buy = side == "BUY"
        price = tick.ask if buy else tick.bid
        pip = await b.call(b.pip, sym)

        # ---- tipo di ingresso
        kind, entry = "market", price
        rng = s.get("entry_range")
        ref = s.get("entry")
        if rng:
            ref = rng[1] if buy else rng[0]          # bordo peggiore accettabile
        if s.get("order_type") in ("limit", "stop") and s.get("entry"):
            e = s["entry"]
            better_now = (price <= e) if (buy == (s["order_type"] == "limit")) else (price >= e)
            if not better_now:
                kind, entry = s["order_type"], e
        elif ref is not None:
            slip = float(ch.get("max_slippage_pips") or 0)
            worse = (price - ref) if buy else (ref - price)
            if slip > 0 and worse > slip * pip:
                kind, entry = "limit", ref

        # ---- stop loss
        sl, sl_note = s.get("sl"), ""
        if sl is None and s.get("sl_pips"):
            sl = entry - s["sl_pips"] * pip if buy else entry + s["sl_pips"] * pip
        if sl is None:
            d = float(ch.get("default_sl_pips") or 0)
            if d <= 0:
                return "skipped", "segnale senza SL (imposta SL d'emergenza nel gruppo)"
            sl = entry - d * pip if buy else entry + d * pip
            sl_note = f" · SL emergenza {d:g} pips"
        if (buy and sl >= entry) or (not buy and sl <= entry):
            return "skipped", f"prezzo {price} gia' oltre lo SL {sl}"

        # ---- take profit
        tps = list(s.get("tps") or [])
        if not tps and s.get("tp_pips"):
            tps = [entry + p * pip if buy else entry - p * pip for p in s["tp_pips"]]
        tps = [tp for tp in tps if (tp > entry if buy else tp < entry)]
        if s.get("tps") and not tps:
            return "skipped", "prezzo gia' oltre tutti i TP"
        mode = ch.get("tp_mode") or "split"
        if mode == "first":
            tps = tps[:1]
        elif mode == "last":
            tps = tps[-1:]

        # ---- volume
        vmin, vmax, step = await b.call(b.vol_limits, sym)
        rm, rv = ch.get("risk_mode") or "fixed_lot", float(ch.get("risk_value") or 0.01)
        if rm == "fixed_lot":
            total = rv
        else:
            acc = self.account or await b.call(b.account)
            money = acc["balance"] * rv / 100 if rm == "risk_pct" else rv
            lpl = await b.call(b.loss_per_lot, sym, side, entry, sl)
            if not lpl:
                return "error", "impossibile calcolare il lotto"
            total = money / lpl
        total = min(total, float(ch.get("max_lot") or vmax), vmax)
        n = max(1, len(tps))
        per = await b.call(b.norm_volume, sym, total / n)
        if per < vmin:
            n = max(1, int(total / vmin + 1e-9))
            per = max(vmin, await b.call(b.norm_volume, sym, total / n))
        targets = tps[:n] if tps else [None]

        # ---- invio
        opened, errors = 0, []
        for i, tp in enumerate(targets):
            comment = f"SB{row['id']}-{i + 1}"
            if kind == "market":
                ok, ticket, fill, msg = await b.call(b.market, sym, side, per, sl, tp, comment, self.magic)
            else:
                ok, ticket, fill, msg = await b.call(b.pending, sym, side, kind, entry, per, sl, tp, comment, self.magic)
            if ok:
                opened += 1
                await self.db.insert_trade({
                    "signal_id": row["id"], "channel_id": ch["id"], "channel_title": ch.get("title"),
                    "ticket": ticket, "symbol": sym, "side": side, "order_kind": kind, "volume": per,
                    "open_price": fill, "sl": sl, "tp": tp, "tp_index": i,
                    "status": "open" if kind == "market" else "pending",
                })
            else:
                errors.append(msg)
        if opened:
            cnt = await self.db.count_trades(ch["id"])
            await self.db.touch_channel(ch["id"], trade=True, count=cnt)
        what = f"{opened}x {per} lotti {sym} {kind}" + sl_note
        if opened == len(targets):
            return "executed", what
        if opened:
            return "partial", what + " · errori: " + "; ".join(errors)
        return "error", "; ".join(errors) or "ordine rifiutato"

    # ------------------------------------------------------------ aggiornamenti
    async def find_target(self, ch, u, reply_to):
        if reply_to:
            sig = await self.db.get_signal(ch["id"], reply_to)
            if sig and sig["kind"] == "signal":
                return sig
            if sig and sig.get("reply_to_id"):   # risposta a una risposta
                sig2 = await self.db.get_signal(ch["id"], sig["reply_to_id"])
                if sig2 and sig2["kind"] == "signal":
                    return sig2
        since = (utcnow() - timedelta(hours=48)).isoformat()
        for sig in await self.db.last_signals(ch["id"], since):
            p = sig.get("parsed") or {}
            if u.get("symbol") and p.get("symbol") and u["symbol"] != p["symbol"]:
                continue
            if u.get("side") and p.get("side") and u["side"] != p["side"]:
                continue
            if await self.db.trades_for_signal(sig["id"]):
                return sig
        return None

    async def exec_update(self, row, u, ch, reply_to):
        async with self.lock:
            try:
                status, reason = await self._exec_update(u, ch, reply_to)
            except Exception as e:
                log.exception("errore update")
                status, reason = "error", str(e)
        await self.db.update_signal(row["id"], {"status": status, "reason": reason})
        log.info("[%s] update %s -> %s %s", ch.get("title"), u["action"], status, reason)

    async def _exec_update(self, u, ch, reply_to):
        b = self.broker
        target = await self.find_target(ch, u, reply_to)
        if not target:
            return "skipped", "nessun trade aperto collegato"
        trades = await self.db.trades_for_signal(target["id"])
        if not trades:
            return "skipped", "trade gia' chiusi"
        a, done = u["action"], 0
        opens = [t for t in trades if t["status"] == "open"]
        pend = [t for t in trades if t["status"] == "pending"]

        if a == "close_all":
            for t in trades:
                ok, _ = await b.call(b.close, t["ticket"])
                done += ok
        elif a == "cancel":
            for t in pend:
                ok, _ = await b.call(b.cancel, t["ticket"])
                done += ok
            if not pend:
                return "skipped", "nessun ordine pendente da annullare"
        elif a == "close_partial":
            pct = float(u.get("percent") or 50) / 100
            if not opens:
                return "skipped", "nessuna posizione aperta"
            vmin, _, _ = await b.call(b.vol_limits, opens[0]["symbol"])
            if all(float(t["volume"]) < 2 * vmin for t in opens) and len(opens) > 1:
                k = max(1, round(len(opens) * pct))
                for t in opens[:k]:
                    ok, _ = await b.call(b.close, t["ticket"])
                    done += ok
            else:
                for t in opens:
                    v = await b.call(b.norm_volume, t["symbol"], float(t["volume"]) * pct)
                    if v >= vmin:
                        ok, _ = await b.call(b.close, t["ticket"], v)
                        done += ok
                        if ok:
                            await self.db.update_trade(t["ticket"], {"volume": round(float(t["volume"]) - v, 3)})
        elif a == "move_sl_be":
            for t in opens:
                pos = await b.call(lambda tk=t["ticket"]: b.mt5.positions_get(ticket=tk))
                if not pos:
                    continue
                be = pos[0].price_open
                ok, _ = await b.call(b.modify, t["ticket"], t["symbol"], be, None)
                done += ok
                if ok:
                    await self.db.update_trade(t["ticket"], {"sl": be})
        elif a in ("modify_sl", "modify_tp"):
            price = u.get("price")
            if not price:
                return "skipped", "prezzo mancante"
            for t in trades:
                sl, tp = (price, None) if a == "modify_sl" else (None, price)
                ok, _ = await b.call(b.modify, t["ticket"], t["symbol"], sl, tp)
                done += ok
                if ok:
                    await self.db.update_trade(t["ticket"], {"sl": price} if sl else {"tp": price})
        else:
            return "ignored", "azione non gestita"
        return ("executed" if done else "error"), f"{a}: {done} ordini (segnale #{target['id']})"

    # ------------------------------------------------------------ monitor
    async def monitor(self):
        b = self.broker
        positions = await b.call(b.positions, self.magic)
        orders = await b.call(b.orders, self.magic)
        pos_map = {p["ticket"]: p for p in positions}
        ord_set = {o["ticket"] for o in orders}
        active = await self.db.active_trades()
        by_signal: dict[int, list] = {}
        for t in active:
            by_signal.setdefault(t["signal_id"], []).append(t)
            tk = t["ticket"]
            if tk in pos_map:
                if t["status"] == "pending":
                    await self.db.update_trade(tk, {"status": "open", "open_price": pos_map[tk]["price_open"]})
                    t["status"] = "open"
                continue
            if tk in ord_set:
                continue
            close_price, profit = await b.call(b.closed_info, tk)
            if close_price is None and t["status"] == "pending":
                await self.db.update_trade(tk, {"status": "cancelled", "closed_at": utcnow().isoformat()})
            else:
                await self.db.update_trade(tk, {"status": "closed", "close_price": close_price, "profit": profit,
                                                "closed_at": utcnow().isoformat()})
                t["status"] = "closed"
                t["_profit"] = profit or 0
        # break-even dopo TP1
        for sid, ts in by_signal.items():
            if sid is None or sid in self.be_done:
                continue
            ch = self.channels.get(ts[0]["channel_id"]) or {}
            if not ch.get("be_after_tp1", True):
                continue
            closed_win = [t for t in ts if t["status"] == "closed" and t.get("_profit", 0) > 0 and t.get("tp")]
            still = [t for t in ts if t["status"] == "open" and t["ticket"] in pos_map]
            if closed_win and still:
                async with self.lock:
                    for t in still:
                        p = pos_map[t["ticket"]]
                        better = (p["sl"] < p["price_open"]) if p["side"] == "BUY" else (p["sl"] == 0 or p["sl"] > p["price_open"])
                        if better:
                            ok, _ = await b.call(b.modify, t["ticket"], t["symbol"], p["price_open"], None)
                            if ok:
                                await self.db.update_trade(t["ticket"], {"sl": p["price_open"]})
                self.be_done.add(sid)
                log.info("Segnale #%s: TP1 preso -> SL a pareggio su %d posizioni", sid, len(still))
        return positions, orders

    async def heartbeat(self, tg_connected: bool, version: str):
        b = self.broker
        ok = await b.call(b.ensure)
        payload = {"engine_online": True, "mt5_connected": ok, "tg_connected": tg_connected, "version": version}
        if ok:
            acc = await b.call(b.account)
            self.account = acc
            today = datetime.now().date()
            if acc and self.day != today:
                closed_today = await b.call(b.closed_profit_today, self.magic)
                self.day = today
                self.day_start_balance = acc["balance"] - closed_today
            positions, orders = await self.monitor()
            titles = {t["ticket"]: t for t in await self.db.active_trades()}
            for p in positions + orders:
                t = titles.get(p["ticket"]) or {}
                p["channel"] = t.get("channel_title")
                p["signal_id"] = t.get("signal_id")
            payload.update(acc or {})
            payload["day_start_balance"] = self.day_start_balance
            payload["positions"] = positions + orders
            payload["message"] = None
        else:
            payload["message"] = "MT5 non raggiungibile: apri il terminale ed effettua il login"
        await self.db.set_status(payload)

    # ------------------------------------------------------------ comandi dall'app
    async def run_command(self, cmd: dict, tg=None):
        b, t, p = self.broker, cmd["type"], cmd.get("payload") or {}
        if t == "close_ticket":
            async with self.lock:
                ok, msg = await b.call(b.close, int(p["ticket"]))
            return ok, {"msg": msg}
        if t == "close_all":
            n = 0
            async with self.lock:
                for x in await b.call(b.positions, self.magic) + await b.call(b.orders, self.magic):
                    ok, _ = await b.call(b.close, x["ticket"])
                    n += ok
            return True, {"closed": n}
        if t == "close_signal":
            n = 0
            async with self.lock:
                for x in await self.db.trades_for_signal(int(p["signal_id"])):
                    ok, _ = await b.call(b.close, x["ticket"])
                    n += ok
            return True, {"closed": n}
        if t == "refresh_channels" and tg:
            n = await tg.sync_dialogs()
            return True, {"new": n}
        if t == "parse_test":
            parsed, src = await self.parse(p.get("text", ""), bool(p.get("is_reply")))
            return True, {"parsed": parsed, "parser": src}
        return False, {"msg": f"comando sconosciuto {t}"}
