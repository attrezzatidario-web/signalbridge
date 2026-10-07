"""MT5 finto per provare il motore senza Windows (SIMULATE=1). Prezzi fissi modificabili da codice."""
from types import SimpleNamespace as NS
import itertools

ACCOUNT_TRADE_MODE_DEMO, ACCOUNT_TRADE_MODE_CONTEST, ACCOUNT_TRADE_MODE_REAL = 0, 1, 2
ORDER_TYPE_BUY, ORDER_TYPE_SELL, ORDER_TYPE_BUY_LIMIT, ORDER_TYPE_SELL_LIMIT, ORDER_TYPE_BUY_STOP, ORDER_TYPE_SELL_STOP = range(6)
POSITION_TYPE_BUY, POSITION_TYPE_SELL = 0, 1
TRADE_ACTION_DEAL, TRADE_ACTION_PENDING, TRADE_ACTION_SLTP, TRADE_ACTION_MODIFY, TRADE_ACTION_REMOVE = 1, 5, 6, 7, 8
ORDER_FILLING_FOK, ORDER_FILLING_IOC, ORDER_FILLING_RETURN = 0, 1, 2
ORDER_TIME_GTC = 0
TRADE_RETCODE_PLACED, TRADE_RETCODE_DONE = 10008, 10009
DEAL_ENTRY_IN, DEAL_ENTRY_OUT, DEAL_ENTRY_OUT_BY = 0, 1, 3

_ids = itertools.count(1000)
SYMBOLS = {
    "XAUUSD": dict(digits=2, point=0.01, contract=100, bid=2650.00, ask=2650.30),
    "EURUSD": dict(digits=5, point=0.00001, contract=100000, bid=1.08500, ask=1.08510),
    "GBPJPY": dict(digits=3, point=0.001, contract=100000, bid=191.500, ask=191.520),
    "US30": dict(digits=1, point=0.1, contract=1, bid=42000.0, ask=42002.0),
    "BTCUSD": dict(digits=2, point=0.01, contract=1, bid=64000.0, ask=64020.0),
}
state = NS(trade_mode=ACCOUNT_TRADE_MODE_DEMO, balance=10000.0, positions={}, orders={}, deals=[])


def initialize(**kw): return True
def shutdown(): pass
def last_error(): return (0, "ok")
def terminal_info(): return NS(connected=True)


def account_info():
    eq = state.balance + sum(_pnl(p) for p in state.positions.values())
    return NS(login=12345678, server="Sim-Demo", name="Simulazione", trade_mode=state.trade_mode,
              currency="EUR", balance=state.balance, equity=eq, margin_free=eq)


def symbol_info(s):
    d = SYMBOLS.get(s)
    if not d:
        return None
    return NS(name=s, digits=d["digits"], point=d["point"], volume_min=0.01, volume_max=100, volume_step=0.01,
              filling_mode=1, trade_stops_level=0)


def symbols_get(pattern="*"):
    key = pattern.strip("*")
    return [NS(name=s) for s in SYMBOLS if key in s]


def symbol_select(s, on=True): return s in SYMBOLS
def symbol_info_tick(s):
    d = SYMBOLS.get(s)
    return NS(bid=d["bid"], ask=d["ask"]) if d else None


def set_price(s, bid, spread=None):
    d = SYMBOLS[s]
    sp = d["ask"] - d["bid"] if spread is None else spread
    d["bid"], d["ask"] = bid, bid + sp
    _check_stops()


def order_calc_profit(t, s, vol, p_open, p_close):
    c = SYMBOLS[s]["contract"]
    diff = (p_close - p_open) if t == ORDER_TYPE_BUY else (p_open - p_close)
    return diff * c * vol


def _pnl(p):
    t = symbol_info_tick(p.symbol)
    cur = t.bid if p.type == POSITION_TYPE_BUY else t.ask
    return order_calc_profit(ORDER_TYPE_BUY if p.type == 0 else ORDER_TYPE_SELL, p.symbol, p.volume, p.price_open, cur)


def _res(code, order=0, price=0.0, comment="done"):
    return NS(retcode=code, order=order, deal=order, price=price, comment=comment)


def order_send(r):
    a = r["action"]
    if a == TRADE_ACTION_DEAL:
        if r.get("position"):
            p = state.positions.get(r["position"])
            if not p:
                return _res(10013, comment="no position")
            _close(p, r["volume"])
            return _res(TRADE_RETCODE_DONE, r["position"], r["price"])
        tk = next(_ids)
        t = symbol_info_tick(r["symbol"])
        price = t.ask if r["type"] == ORDER_TYPE_BUY else t.bid
        state.positions[tk] = NS(ticket=tk, symbol=r["symbol"], type=0 if r["type"] == ORDER_TYPE_BUY else 1,
                                 volume=r["volume"], price_open=price, price_current=price, sl=r.get("sl", 0),
                                 tp=r.get("tp", 0), magic=r.get("magic", 0), comment=r.get("comment", ""), swap=0.0,
                                 profit=0.0)
        state.deals.append(NS(position_id=tk, entry=DEAL_ENTRY_IN, price=price, profit=0.0, magic=r.get("magic", 0), swap=0, commission=0))
        return _res(TRADE_RETCODE_DONE, tk, price)
    if a == TRADE_ACTION_PENDING:
        tk = next(_ids)
        state.orders[tk] = NS(ticket=tk, symbol=r["symbol"], type=r["type"], volume_current=r["volume"],
                              price_open=r["price"], sl=r["sl"], tp=r["tp"], magic=r["magic"], comment=r["comment"])
        return _res(TRADE_RETCODE_DONE, tk, r["price"])
    if a == TRADE_ACTION_SLTP:
        p = state.positions.get(r["position"])
        if not p:
            return _res(10013)
        p.sl, p.tp = r["sl"], r["tp"]
        return _res(TRADE_RETCODE_DONE, p.ticket)
    if a == TRADE_ACTION_MODIFY:
        o = state.orders.get(r["order"])
        if not o:
            return _res(10013)
        o.sl, o.tp = r["sl"], r["tp"]
        return _res(TRADE_RETCODE_DONE, o.ticket)
    if a == TRADE_ACTION_REMOVE:
        return _res(TRADE_RETCODE_DONE if state.orders.pop(r["order"], None) else 10013, r["order"])
    return _res(10013, comment="unsupported")


def _close(p, vol, price=None):
    t = symbol_info_tick(p.symbol)
    price = price or (t.bid if p.type == 0 else t.ask)
    vol = min(vol, p.volume)
    prof = order_calc_profit(ORDER_TYPE_BUY if p.type == 0 else ORDER_TYPE_SELL, p.symbol, vol, p.price_open, price)
    state.balance += prof
    state.deals.append(NS(position_id=p.ticket, entry=DEAL_ENTRY_OUT, price=price, profit=prof, magic=p.magic, swap=0, commission=0))
    p.volume = round(p.volume - vol, 2)
    if p.volume <= 0:
        del state.positions[p.ticket]


def _check_stops():
    for p in list(state.positions.values()):
        t = symbol_info_tick(p.symbol)
        cur = t.bid if p.type == 0 else t.ask
        if p.tp and ((p.type == 0 and cur >= p.tp) or (p.type == 1 and cur <= p.tp)):
            _close(p, p.volume, p.tp)
        elif p.sl and ((p.type == 0 and cur <= p.sl) or (p.type == 1 and cur >= p.sl)):
            _close(p, p.volume, p.sl)


def positions_get(ticket=None, **kw):
    for p in state.positions.values():
        p.price_current = symbol_info_tick(p.symbol).bid
        p.profit = _pnl(p)
    if ticket is not None:
        p = state.positions.get(ticket)
        return (p,) if p else ()
    return tuple(state.positions.values())


def orders_get(ticket=None, **kw):
    if ticket is not None:
        o = state.orders.get(ticket)
        return (o,) if o else ()
    return tuple(state.orders.values())


def history_deals_get(*a, position=None, **kw):
    if position is not None:
        return tuple(d for d in state.deals if d.position_id == position)
    return tuple(state.deals)
