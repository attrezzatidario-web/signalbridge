"""Accesso a Supabase (chiamate sincrone eseguite in thread per non bloccare il loop)."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

log = logging.getLogger("db")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class DB:
    def __init__(self, url: str, key: str):
        from supabase import create_client
        self.sb = create_client(url, key)

    async def _run(self, fn):
        try:
            return await asyncio.to_thread(fn)
        except Exception as e:
            log.warning("DB errore: %s", e)
            return None

    @staticmethod
    def _data(res):
        return getattr(res, "data", None) or []

    # ---------------- settings / channels
    async def settings(self) -> dict | None:
        r = await self._run(lambda: self.sb.table("settings").select("*").eq("id", 1).execute())
        d = self._data(r)
        return d[0] if d else None

    async def channels(self) -> list[dict]:
        r = await self._run(lambda: self.sb.table("channels").select("*").execute())
        return self._data(r)

    async def sync_channels(self, dialogs: list[dict], defaults: dict):
        existing = {c["id"] for c in await self.channels()}
        new = [{**d, **defaults} for d in dialogs if d["id"] not in existing]
        if new:
            await self._run(lambda: self.sb.table("channels").insert(new).execute())
        for d in dialogs:
            if d["id"] in existing:
                await self._run(lambda d=d: self.sb.table("channels").update(
                    {"title": d["title"], "username": d.get("username"), "kind": d.get("kind")}).eq("id", d["id"]).execute())
        return len(new)

    async def touch_channel(self, cid: int, trade: bool = False, count: int = 0):
        payload = {"last_message_at": now_iso()}
        if trade:
            payload["trades_count"] = count
        await self._run(lambda: self.sb.table("channels").update(payload).eq("id", cid).execute())

    # ---------------- signals
    async def get_signal(self, channel_id: int, message_id: int) -> dict | None:
        r = await self._run(lambda: self.sb.table("signals").select("*")
                            .eq("channel_id", channel_id).eq("message_id", message_id).limit(1).execute())
        d = self._data(r)
        return d[0] if d else None

    async def upsert_signal(self, row: dict) -> dict | None:
        r = await self._run(lambda: self.sb.table("signals").upsert(row, on_conflict="channel_id,message_id").execute())
        d = self._data(r)
        return d[0] if d else None

    async def update_signal(self, sid: int, payload: dict):
        await self._run(lambda: self.sb.table("signals").update(payload).eq("id", sid).execute())

    async def last_signals(self, channel_id: int, since_iso: str) -> list[dict]:
        r = await self._run(lambda: self.sb.table("signals").select("*")
                            .eq("channel_id", channel_id).eq("kind", "signal")
                            .in_("status", ["executed", "partial"])
                            .gte("created_at", since_iso).order("created_at", desc=True).limit(10).execute())
        return self._data(r)

    # ---------------- trades
    async def insert_trade(self, row: dict):
        await self._run(lambda: self.sb.table("trades").insert(row).execute())

    async def trades_for_signal(self, sid: int, active_only=True) -> list[dict]:
        def q():
            b = self.sb.table("trades").select("*").eq("signal_id", sid)
            if active_only:
                b = b.in_("status", ["open", "pending"])
            return b.order("tp_index").execute()
        return self._data(await self._run(q))

    async def active_trades(self) -> list[dict]:
        r = await self._run(lambda: self.sb.table("trades").select("*").in_("status", ["open", "pending"]).execute())
        return self._data(r)

    async def update_trade(self, ticket: int, payload: dict):
        await self._run(lambda: self.sb.table("trades").update(payload).eq("ticket", ticket).execute())

    async def count_trades(self, channel_id: int) -> int:
        r = await self._run(lambda: self.sb.table("trades").select("id", count="exact").eq("channel_id", channel_id).execute())
        return getattr(r, "count", 0) or 0

    # ---------------- status / commands
    async def set_status(self, payload: dict):
        payload = {**payload, "last_seen": now_iso()}
        await self._run(lambda: self.sb.table("status").update(payload).eq("id", 1).execute())

    async def pending_commands(self) -> list[dict]:
        r = await self._run(lambda: self.sb.table("commands").select("*").eq("status", "pending").order("id").limit(20).execute())
        return self._data(r)

    async def finish_command(self, cid: int, ok: bool, result):
        await self._run(lambda: self.sb.table("commands").update(
            {"status": "done" if ok else "error", "result": result, "done_at": now_iso()}).eq("id", cid).execute())

    async def cleanup(self):
        await self._run(lambda: self.sb.rpc("cleanup_old").execute())
