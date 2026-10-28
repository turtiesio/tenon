import re
import sys

DENOMINATIONS = (5, 10, 20, 50, 100, 200)
SLOT_RE = re.compile(r"[A-F][1-9]")
NAME_RE = re.compile(r"[a-z]{1,12}")
PRICE_RE = re.compile(r"[1-9][0-9]{0,3}")
COUNT_RE = re.compile(r"0|[1-9][0-9]?")
FILL_N_RE = re.compile(r"[1-9][0-9]{0,2}")
COIN_RE = re.compile(r"[1-9][0-9]{0,5}")

BAD = "ERR bad command"


class Machine:
    def __init__(self):
        self.tubes = {d: 0 for d in DENOMINATIONS}
        self.escrow = {d: 0 for d in DENOMINATIONS}
        self.slots = {}  # slot name -> [name, price, count]

    def credit(self):
        return sum(d * n for d, n in self.escrow.items())

    def handle(self, line):
        tokens = line.split(" ")
        command, args = tokens[0], tokens[1:]
        handler = {
            "LOAD": self.load,
            "FILL": self.fill,
            "INSERT": self.insert,
            "SELECT": self.select,
            "REFUND": self.refund,
            "STOCK": self.stock,
            "COINS": self.coins,
        }.get(command)
        if handler is None:
            return BAD
        return handler(args)

    def load(self, args):
        if len(args) != 4:
            return BAD
        slot, name, price, count = args
        if not (SLOT_RE.fullmatch(slot) and NAME_RE.fullmatch(name)
                and PRICE_RE.fullmatch(price) and int(price) % 5 == 0
                and COUNT_RE.fullmatch(count)):
            return BAD
        self.slots[slot] = [name, int(price), int(count)]
        return "OK"

    def fill(self, args):
        if len(args) != 2:
            return BAD
        coin, n = args
        if not (COIN_RE.fullmatch(coin) and int(coin) in DENOMINATIONS
                and FILL_N_RE.fullmatch(n)):
            return BAD
        self.tubes[int(coin)] += int(n)
        return "OK"

    def insert(self, args):
        if len(args) != 1 or not COIN_RE.fullmatch(args[0]):
            return BAD
        coin = int(args[0])
        if coin not in DENOMINATIONS:
            return f"REJECT {coin}"
        self.escrow[coin] += 1
        return f"CREDIT {self.credit()}"

    def select(self, args):
        if len(args) != 1 or not SLOT_RE.fullmatch(args[0]):
            return BAD
        item = self.slots.get(args[0])
        if item is None:
            return "ERR no such slot"
        name, price, count = item
        if count == 0:
            return "ERR sold out"
        credit = self.credit()
        if credit < price:
            return f"ERR need {price - credit}"

        available = {d: self.tubes[d] + self.escrow[d] for d in DENOMINATIONS}
        change = pay_change(credit - price, available)
        if change is None:
            return "ERR no change"
        self.tubes = {d: available[d] - change[d] for d in DENOMINATIONS}
        self.escrow = {d: 0 for d in DENOMINATIONS}
        item[2] -= 1
        return f"VEND {name} {credit - price} {coin_list(change)}"

    def refund(self, args):
        if args:
            return BAD
        response = f"REFUND {self.credit()} {coin_list(self.escrow)}"
        self.escrow = {d: 0 for d in DENOMINATIONS}
        return response

    def stock(self, args):
        if len(args) != 1 or not SLOT_RE.fullmatch(args[0]):
            return BAD
        item = self.slots.get(args[0])
        if item is None:
            return "ERR no such slot"
        return f"{args[0]} {item[0]} {item[1]} {item[2]}"

    def coins(self, args):
        if args:
            return BAD
        return " ".join(f"{d}x{self.tubes[d]}" for d in DENOMINATIONS)


def pay_change(owed, available):
    """Greedy change from the largest coin down; None if it cannot be paid."""
    change = {d: 0 for d in DENOMINATIONS}
    for d in reversed(DENOMINATIONS):
        take = min(available[d], owed // d)
        change[d] = take
        owed -= take * d
    return change if owed == 0 else None


def coin_list(coins):
    parts = [f"{d}x{coins[d]}" for d in reversed(DENOMINATIONS) if coins[d]]
    return " ".join(parts) if parts else "-"


def main():
    if len(sys.argv) > 1:
        print("usage: vending (takes no arguments)", file=sys.stderr)
        return 2

    machine = Machine()
    for raw in sys.stdin.buffer:
        line = raw.decode("ascii", errors="replace")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        sys.stdout.write(machine.handle(line) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
