"""Server web del motore: app + API + aggiornamenti live, protetto da password."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time
from pathlib import Path

from aiohttp import WSMsgType, web

log = logging.getLogger("web")

WEB_DIR = Path(__file__).with_name("web")
COOKIE = "sb_session"
SESSION_DAYS = 30
MAX_FAILS, LOCK_MIN = 5, 15


def _h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class WebServer:
    def __init__(self, store, manager, password: str, tg_ref=lambda: None):
        self.store, self.m, self.password = store, manager, password
        self.tg_ref = tg_ref
        self.clients: set[web.WebSocketResponse] = set()
        self.fails: dict[str, list[float]] = {}
        self.sessions: dict = store.kv_get("sessions", {}) or {}
        store.listeners.append(self._on_change)
        self.app = web.Application(middlewares=[self._security])
        r = self.app.router
        r.add_post("/api/login", self.login)
        r.add_post("/api/logout", self.logout)
        r.add_get("/api/me", self.me)
        r.add_get("/api/settings", self.get_settings)
        r.add_patch("/api/settings", self.patch_settings)
        r.add_get("/api/status", self.get_status)
        r.add_get("/api/channels", self.get_channels)
        r.add_patch("/api/channels/{id}", self.patch_channel)
        r.add_get("/api/signals", self.get_signals)
        r.add_get("/api/trades", self.get_trades)
        r.add_post("/api/command", self.command)
        r.add_get("/ws", self.ws)
        r.add_get("/", self.index)
        r.add_get("/{path:.*}", self.static)

    # ------------------------------------------------------------ sicurezza
    def _ip(self, req):
        return req.headers.get("X-Forwarded-For", req.remote or "?").split(",")[0].strip()

    def _authed(self, req) -> bool:
        tok = req.cookies.get(COOKIE)
        if not tok:
            return False
        exp = self.sessions.get(_h(tok))
        return bool(exp and exp > time.time())

    @web.middleware
    async def _security(self, req, handler):
        p = req.path
        if (p.startswith("/api/") and p != "/api/login") or p == "/ws":
            if not self._authed(req):
                return web.json_response({"error": "non autorizzato"}, status=401)
        resp = await handler(req)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        if p.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    async def login(self, req):
        ip = self._ip(req)
        now = time.time()
        recent = [t for t in self.fails.get(ip, []) if now - t < LOCK_MIN * 60]
        if len(recent) >= MAX_FAILS:
            return web.json_response({"error": f"Troppi tentativi. Riprova tra {LOCK_MIN} minuti."}, status=429)
        try:
            pw = (await req.json()).get("password", "")
        except Exception:
            pw = ""
        if not self.password or not hmac.compare_digest(pw.encode(), self.password.encode()):
            recent.append(now)
            self.fails[ip] = recent
            log.warning("Login fallito da %s", ip)
            await asyncio.sleep(1)
            return web.json_response({"error": "Password errata"}, status=401)
        self.fails.pop(ip, None)
        tok = secrets.token_urlsafe(32)
        self.sessions = {k: v for k, v in self.sessions.items() if v > now}
        self.sessions[_h(tok)] = now + SESSION_DAYS * 86400
        self.store.kv_set("sessions", self.sessions)
        resp = web.json_response({"ok": True})
        secure = req.headers.get("X-Forwarded-Proto", req.scheme) == "https"
        resp.set_cookie(COOKIE, tok, max_age=SESSION_DAYS * 86400, httponly=True, secure=secure, samesite="Strict", path="/")
        log.info("Login ok da %s", ip)
        return resp

    async def logout(self, req):
        tok = req.cookies.get(COOKIE)
        if tok:
            self.sessions.pop(_h(tok), None)
            self.store.kv_set("sessions", self.sessions)
        resp = web.json_response({"ok": True})
        resp.del_cookie(COOKIE, path="/")
        return resp

    async def me(self, req):
        return web.json_response({"ok": True})

    # ------------------------------------------------------------ dati
    async def get_settings(self, req):
        return web.json_response(self.store.get_settings())

    async def patch_settings(self, req):
        s = self.store.update_settings(await req.json())
        self.m.settings = s
        return web.json_response(s)

    async def get_status(self, req):
        return web.json_response(self.store.status)

    async def get_channels(self, req):
        return web.json_response(self.store.list_channels())

    async def patch_channel(self, req):
        c = self.store.update_channel(int(req.match_info["id"]), await req.json())
        if not c:
            return web.json_response({"error": "non trovato"}, status=404)
        self.m.channels[c["id"]] = c
        return web.json_response(c)

    async def get_signals(self, req):
        return web.json_response(self.store.list_signals(int(req.query.get("limit", 150))))

    async def get_trades(self, req):
        return web.json_response(self.store.list_trades(int(req.query.get("limit", 2000))))

    async def command(self, req):
        body = await req.json()
        try:
            ok, res = await self.m.run_command({"type": body.get("type"), "payload": body.get("payload") or {}}, self.tg_ref())
        except Exception as e:
            ok, res = False, {"msg": str(e)}
        return web.json_response({"status": "done" if ok else "error", "result": res})

    # ------------------------------------------------------------ live
    def _on_change(self, table, row):
        if not self.clients or row is None:
            return
        msg = json.dumps({"t": table, "row": row}, default=str)
        for ws in list(self.clients):
            if ws.closed:
                self.clients.discard(ws)
                continue
            asyncio.ensure_future(self._send(ws, msg))

    async def _send(self, ws, msg):
        try:
            await ws.send_str(msg)
        except Exception:
            self.clients.discard(ws)

    async def ws(self, req):
        ws = web.WebSocketResponse(heartbeat=25)
        await ws.prepare(req)
        self.clients.add(ws)
        try:
            async for msg in ws:
                if msg.type == WSMsgType.ERROR:
                    break
        finally:
            self.clients.discard(ws)
        return ws

    # ------------------------------------------------------------ app statica
    async def index(self, req):
        f = WEB_DIR / "index.html"
        if not f.exists():
            return web.Response(text="App non ancora compilata: esegui AGGIORNA.bat", status=503)
        resp = web.FileResponse(f)
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    async def static(self, req):
        rel = req.match_info["path"]
        f = (WEB_DIR / rel).resolve()
        if WEB_DIR.resolve() not in f.parents or not f.is_file():
            return await self.index(req)
        resp = web.FileResponse(f)
        if "/assets/" in f.as_posix():
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif f.name in ("sw.js", "manifest.webmanifest", "registerSW.js"):
            resp.headers["Cache-Control"] = "no-cache"
        return resp

    async def start(self, host="127.0.0.1", port=8080):
        runner = web.AppRunner(self.app, access_log=None)
        await runner.setup()
        await web.TCPSite(runner, host, port).start()
        log.info("App web su http://%s:%d", host, port)
