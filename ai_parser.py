"""Fallback con Gemini per i messaggi che le regole non capiscono."""
from __future__ import annotations

import json
import logging

log = logging.getLogger("ai")

PROMPT = """Sei un parser di segnali di trading da Telegram. Rispondi SOLO con JSON valido.

Classifica il messaggio:
1) NUOVO SEGNALE ->
{"kind":"signal","symbol":"XAUUSD","side":"BUY|SELL","order_type":"market|limit|stop",
 "entry":numero|null,"entry_range":[min,max]|null,"sl":numero|null,"sl_pips":numero|null,
 "tps":[numeri],"tp_pips":[numeri]}
   - symbol: ticker MT5 standard senza suffissi (GOLD->XAUUSD, EUR/USD->EURUSD, DOW->US30, NASDAQ->NAS100, BTC->BTCUSD)
   - order_type "market" se dice NOW/market o non specifica limit/stop
   - "TP open" va ignorato; SL/TP espressi in pips vanno in sl_pips/tp_pips
2) AGGIORNAMENTO su un trade gia' aperto ->
{"kind":"update","action":"close_all|close_partial|move_sl_be|modify_sl|modify_tp|cancel|info",
 "percent":numero|null,"price":numero|null,"symbol":"..."|null,"side":"BUY|SELL"|null}
   - "info" = solo report di risultato (TP hit, +50 pips, SL hit) senza azione da fare
3) Nient'altro (pubblicita', saluti, analisi senza ordine) -> {"kind":"none"}

Messaggio{reply}:
<<<
{text}
>>>"""


class AIParser:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.model = model
        self.client = None
        if api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=api_key)
            except Exception as e:  # pragma: no cover
                log.warning("Gemini non disponibile: %s", e)

    @property
    def ready(self) -> bool:
        return self.client is not None

    async def parse(self, text: str, is_reply: bool = False) -> dict | None:
        if not self.client:
            return None
        prompt = PROMPT.replace("{text}", text[:1500]).replace(
            "{reply}", " (e' una RISPOSTA a un segnale precedente)" if is_reply else "")
        try:
            resp = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "temperature": 0,
                    "thinking_config": {"thinking_budget": 0},
                },
            )
            data = json.loads(resp.text)
        except Exception as e:
            log.warning("Gemini errore: %s", e)
            return None
        if not isinstance(data, dict) or data.get("kind") not in ("signal", "update"):
            return None
        if data["kind"] == "signal":
            if not data.get("symbol") or data.get("side") not in ("BUY", "SELL"):
                return None
            data["symbol"] = str(data["symbol"]).upper().replace("/", "").replace("#", "")
            data.setdefault("order_type", "market")
            data["tps"] = [float(x) for x in (data.get("tps") or []) if x is not None]
            data["tp_pips"] = [float(x) for x in (data.get("tp_pips") or []) if x is not None]
            for k in ("entry", "sl", "sl_pips"):
                data[k] = float(data[k]) if data.get(k) not in (None, "") else None
            er = data.get("entry_range")
            data["entry_range"] = sorted(float(x) for x in er) if er and len(er) == 2 else None
        return data
