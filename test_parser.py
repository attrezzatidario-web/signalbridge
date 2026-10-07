import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from parser import parse, worth_ai  # noqa: E402

def sig(text, **kw):
    r = parse(text, **kw)
    assert r and r["kind"] == "signal", f"non segnale: {text!r} -> {r}"
    return r

def upd(text, action, **kw):
    r = parse(text, **kw)
    assert r and r["kind"] == "update" and r["action"] == action, f"{text!r} -> {r}"
    return r


def test_classic():
    r = sig("XAUUSD BUY 2650\nSL 2640\nTP 2660\nTP 2670")
    assert r["symbol"] == "XAUUSD" and r["side"] == "BUY" and r["entry"] == 2650
    assert r["sl"] == 2640 and r["tps"] == [2660, 2670]

def test_emoji_numbered_tp():
    r = sig("🔥 GOLD SELL NOW 2655-2658 🔥\n\n❌ SL: 2665\n✅ TP1: 2650\n✅ TP2: 2645\n✅ TP3: 2635")
    assert r["symbol"] == "XAUUSD" and r["side"] == "SELL"
    assert r["entry_range"] == [2655, 2658] and r["sl"] == 2665 and r["tps"] == [2650, 2645, 2635]

def test_pair_slash():
    r = sig("EUR/USD Sell @ 1.0850\nStop Loss: 1.0880\nTake Profit 1: 1.0820\nTake Profit 2: 1.0790")
    assert r["symbol"] == "EURUSD" and r["entry"] == 1.085 and r["sl"] == 1.088 and r["tps"] == [1.082, 1.079]

def test_hashtag_limit():
    r = sig("#GBPJPY BUY LIMIT 191.20\nSL 190.70\nTP 191.80 / 192.40")
    assert r["symbol"] == "GBPJPY" and r["order_type"] == "limit" and r["entry"] == 191.2
    assert r["tps"] == [191.8, 192.4]

def test_now_without_levels():
    r = sig("XAUUSD BUY NOW")
    assert r["entry"] is None and r["sl"] is None and r["tps"] == []

def test_pips():
    r = sig("US30 SELL\nSL 50 pips\nTP 100 pips")
    assert r["symbol"] == "US30" and r["sl_pips"] == 50 and r["tp_pips"] == [100]

def test_thousand_comma():
    r = sig("BTCUSD LONG 64,250\nSL 63,500\nTP 65,500")
    assert r["symbol"] == "BTCUSD" and r["entry"] == 64250 and r["sl"] == 63500

def test_italian():
    r = sig("ORO COMPRA ORA\nSL 2640\nTP 2660")
    assert r["symbol"] == "XAUUSD" and r["side"] == "BUY"

def test_suspect():
    r = parse("XAUUSD BUY 2650 SL 2660 TP 2640")
    assert r["kind"] == "signal" and r.get("_suspect")

def test_result_not_signal():
    r = parse("GOLD BUY TP1 HIT ✅ +50 pips")
    assert r is None or r["kind"] == "update"

def test_updates():
    upd("Move SL to BE", "move_sl_be")
    upd("SL to entry now guys", "move_sl_be")
    upd("Close half and let the rest run", "close_partial")
    assert upd("close 70% now", "close_partial")["percent"] == 70
    upd("CLOSE ALL NOW", "close_all")
    upd("Close gold now", "close_all")
    upd("chiudi tutto", "close_all")
    assert upd("move sl to 2655", "modify_sl")["price"] == 2655
    assert upd("new TP 2690", "modify_tp")["price"] == 2690
    upd("cancel the order", "cancel")
    upd("TP1 hit ✅", "info")
    assert upd("SL 2655", "modify_sl", is_reply=True)["price"] == 2655

def test_noise():
    assert parse("Good morning traders! Have a great week") is None
    assert not worth_ai("Good morning traders!")
    assert worth_ai("gold buy 2650 sl 2640")


def test_more_formats():
    r = sig("SELL XAUUSD @ 2655\nSL 2665\nTP 2645")
    assert r["entry"] == 2655 and r["sl"] == 2665 and r["tps"] == [2645]
    r = sig("XAUUSD\nSELL\nEntry: 2655\nSL: 2665\nTP1: 2645\nTP2: 2635")
    assert r["entry"] == 2655 and r["tps"] == [2645, 2635]
    r = sig("GOLD BUY ZONE 2640 - 2636\nSL 2632\nTP 2645\nTP 2650\nTP OPEN")
    assert r["entry_range"] == [2636, 2640] and r["sl"] == 2632 and r["tps"] == [2645, 2650]
    r = sig("Buy gold 2650/2647 sl 2643 tp 2655 tp 2660")
    assert r["entry_range"] == [2647, 2650] and r["sl"] == 2643 and r["tps"] == [2655, 2660]
    r = sig("NAS100 SELL STOP 18250\nSL 18320\nTP 18100")
    assert r["order_type"] == "stop" and r["entry"] == 18250 and r["sl"] == 18320

if __name__ == "__main__":
    import inspect
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and inspect.isfunction(fn):
            fn(); n += 1
    print(f"OK {n} test")
