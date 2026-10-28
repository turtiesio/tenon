import re
import sys

SYM_RE = re.compile(r"[A-Z]{1,5}")
QTY_RE = re.compile(r"[1-9][0-9]{0,5}")
PRICE_RE = re.compile(r"(0|[1-9][0-9]{0,5})\.([0-9]{2})")
RATIO_RE = re.compile(r"10|[2-9]")


class Lot:
    def __init__(self, qty, cost):
        self.qty = qty
        self.cost = cost


def money(cents):
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(cents), 100)
    return f"{sign}{whole}.{frac:02d}"


def parse_price(token):
    m = PRICE_RE.fullmatch(token)
    if m is None:
        return None
    return int(m.group(1)) * 100 + int(m.group(2))


def parse_trade(line):
    """Return a tuple describing the trade, or None for a bad line."""
    tokens = line.split(" ")
    kind = tokens[0]
    if kind in ("BUY", "SELL") and len(tokens) == 4:
        _, sym, qty, price = tokens
        cents = parse_price(price)
        if SYM_RE.fullmatch(sym) and QTY_RE.fullmatch(qty) and cents is not None:
            return kind, sym, int(qty), cents
    elif kind == "SPLIT" and len(tokens) == 3:
        _, sym, ratio = tokens
        if SYM_RE.fullmatch(sym) and RATIO_RE.fullmatch(ratio):
            return kind, sym, int(ratio)
    return None


def sell(lots, k):
    """Take k shares from the lots, oldest first; return the cost in cents."""
    cost = 0
    while k > 0:
        lot = lots[0]
        if lot.qty <= k:
            cost += lot.cost
            k -= lot.qty
            lots.pop(0)
        else:
            part = (2 * lot.cost * k + lot.qty) // (2 * lot.qty)
            cost += part
            lot.qty -= k
            lot.cost -= part
            k = 0
    return cost


def main():
    if len(sys.argv) > 1:
        print("usage: costbasis (takes no arguments)", file=sys.stderr)
        return 2

    text = sys.stdin.buffer.read().decode("ascii", errors="replace")
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()

    holdings = {}
    total_gain = 0
    had_error = False
    out = []

    for n, line in enumerate(lines, start=1):
        if line.endswith("\r"):
            line = line[:-1]
        if line == "" or line.startswith("#"):
            continue
        trade = parse_trade(line)
        if trade is None:
            out.append(f"{n}: ERR bad line")
            had_error = True
            continue

        kind, sym = trade[0], trade[1]
        lots = holdings.setdefault(sym, [])
        if kind == "BUY":
            _, _, qty, price = trade
            lots.append(Lot(qty, qty * price))
        elif kind == "SELL":
            _, _, k, price = trade
            held = sum(lot.qty for lot in lots)
            if k > held:
                out.append(f"{n}: ERR insufficient {sym} held={held}")
                had_error = True
                continue
            cost = sell(lots, k)
            proceeds = k * price
            gain = proceeds - cost
            total_gain += gain
            out.append(
                f"{n}: SELL {sym} {k} proceeds={money(proceeds)} "
                f"cost={money(cost)} gain={money(gain)}"
            )
        else:
            ratio = trade[2]
            if not lots:
                out.append(f"{n}: ERR not held {sym}")
                had_error = True
                continue
            for lot in lots:
                lot.qty *= ratio
            held = sum(lot.qty for lot in lots)
            out.append(f"{n}: SPLIT {sym} {ratio} held={held}")

    for sym in sorted(holdings):
        lots = holdings[sym]
        if lots:
            qty = sum(lot.qty for lot in lots)
            cost = sum(lot.cost for lot in lots)
            out.append(f"HOLD {sym} {qty} cost={money(cost)} lots={len(lots)}")
    out.append(f"TOTAL gain={money(total_gain)}")

    sys.stdout.write("".join(line + "\n" for line in out))
    return 1 if had_error else 0


if __name__ == "__main__":
    sys.exit(main())
