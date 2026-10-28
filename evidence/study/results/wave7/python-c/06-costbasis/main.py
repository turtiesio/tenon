"""costbasis: realized gains with first-in, first-out lots."""
import re
import sys
from collections import defaultdict

SYM = r"([A-Z]{1,5})"
QTY = r"([1-9][0-9]{0,5})"
PRICE = r"((?:0|[1-9][0-9]{0,5})\.[0-9]{2})"
TRADE = re.compile(rf"(BUY|SELL) {SYM} {QTY} {PRICE}")
SPLIT = re.compile(rf"SPLIT {SYM} ([2-9]|10)")


def parse_cents(price):
    units, frac = price.split(".")
    return int(units) * 100 + int(frac)


def money(cents):
    sign = "-" if cents < 0 else ""
    units, frac = divmod(abs(cents), 100)
    return f"{sign}{units}.{frac:02d}"


class Portfolio:
    def __init__(self):
        # symbol -> list of [quantity, cost in cents], oldest first
        self.lots = defaultdict(list)

    def held(self, sym):
        return sum(q for q, _ in self.lots.get(sym, []))

    def buy(self, sym, qty, price):
        self.lots[sym].append([qty, qty * price])

    def sell(self, sym, qty):
        """Remove qty shares FIFO and return their cost. Caller checks holdings."""
        lots = self.lots[sym]
        cost = 0
        remaining = qty
        while remaining:
            q, c = lots[0]
            if remaining >= q:
                cost += c
                remaining -= q
                lots.pop(0)
            else:
                part = (2 * c * remaining + q) // (2 * q)
                cost += part
                lots[0] = [q - remaining, c - part]
                remaining = 0
        if not lots:
            del self.lots[sym]
        return cost

    def split(self, sym, ratio):
        for lot in self.lots[sym]:
            lot[0] *= ratio

    def holdings(self):
        for sym in sorted(self.lots):
            lots = self.lots[sym]
            yield sym, sum(q for q, _ in lots), sum(c for _, c in lots), len(lots)


def read_lines(text):
    lines = text.split("\n") if text else []
    if text.endswith("\n"):
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def main(argv):
    if argv:
        print("usage: costbasis < trades", file=sys.stderr)
        return 2

    portfolio = Portfolio()
    total_gain = 0
    had_error = False
    out = []
    text = sys.stdin.buffer.read().decode("latin-1")
    for n, line in enumerate(read_lines(text), start=1):
        if line == "" or line.startswith("#"):
            continue
        if m := TRADE.fullmatch(line):
            action, sym, qty, price = m.group(1), m.group(2), int(m.group(3)), parse_cents(m.group(4))
            if action == "BUY":
                portfolio.buy(sym, qty, price)
                continue
            held = portfolio.held(sym)
            if qty > held:
                out.append(f"{n}: ERR insufficient {sym} held={held}")
                had_error = True
                continue
            cost = portfolio.sell(sym, qty)
            proceeds = qty * price
            gain = proceeds - cost
            total_gain += gain
            out.append(f"{n}: SELL {sym} {qty} proceeds={money(proceeds)} "
                       f"cost={money(cost)} gain={money(gain)}")
        elif m := SPLIT.fullmatch(line):
            sym, ratio = m.group(1), int(m.group(2))
            if portfolio.held(sym) == 0:
                out.append(f"{n}: ERR not held {sym}")
                had_error = True
                continue
            portfolio.split(sym, ratio)
            out.append(f"{n}: SPLIT {sym} {ratio} held={portfolio.held(sym)}")
        else:
            out.append(f"{n}: ERR bad line")
            had_error = True

    for sym, held, cost, count in portfolio.holdings():
        out.append(f"HOLD {sym} {held} cost={money(cost)} lots={count}")
    out.append(f"TOTAL gain={money(total_gain)}")
    sys.stdout.write("".join(line + "\n" for line in out))
    return 1 if had_error else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
