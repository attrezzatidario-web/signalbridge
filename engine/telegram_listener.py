"""Ascolto dei gruppi/canali Telegram con il TUO account (Telethon)."""
from __future__ import annotations

import logging

from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat

log = logging.getLogger("telegram")


class TG:
    def __init__(self, api_id, api_hash, session, manager, db):
        self.client = TelegramClient(session, api_id, api_hash, device_model="SignalBridge", system_version="Windows")
        self.m, self.db = manager, db

    @property
    def connected(self) -> bool:
        return self.client.is_connected()

    async def start(self):
        await self.client.connect()
        if not await self.client.is_user_authorized():
            raise RuntimeError("Telegram non autorizzato: esegui prima LOGIN_TELEGRAM.bat")
        me = await self.client.get_me()
        log.info("Telegram connesso come %s", me.first_name)

        @self.client.on(events.NewMessage())
        async def on_new(ev):
            await self._handle(ev, edited=False)

        @self.client.on(events.MessageEdited())
        async def on_edit(ev):
            await self._handle(ev, edited=True)

        await self.sync_dialogs()

    async def _handle(self, ev, edited):
        cid = ev.chat_id
        if cid not in self.m.enabled_ids():
            return
        msg = ev.message
        text = msg.message or ""
        if not text.strip():
            return
        reply_to = msg.reply_to.reply_to_msg_id if msg.reply_to else None
        try:
            await self.m.on_message(cid, msg.id, text, reply_to, date=msg.date, edited=edited)
        except Exception:
            log.exception("errore gestione messaggio")

    async def sync_dialogs(self) -> int:
        dialogs = []
        async for d in self.client.iter_dialogs():
            e = d.entity
            if isinstance(e, Channel):
                kind = "channel" if e.broadcast else "group"
            elif isinstance(e, Chat):
                kind = "group"
            else:
                continue
            dialogs.append({"id": d.id, "title": d.name or str(d.id), "username": getattr(e, "username", None), "kind": kind})
        s = self.m.settings
        defaults = {"risk_mode": s.get("default_risk_mode", "fixed_lot"), "risk_value": s.get("default_risk_value", 0.01)}
        n = await self.db.sync_channels(dialogs, defaults)
        await self.m.refresh()
        log.info("Gruppi/canali trovati: %d (nuovi %d)", len(dialogs), n)
        return n

    async def run(self):
        await self.client.run_until_disconnected()
