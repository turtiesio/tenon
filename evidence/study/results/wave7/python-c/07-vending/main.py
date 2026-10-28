"""vending: vending machine controller with coin change."""
import re
import sys
from collections import Counter
from dataclasses import dataclass

DENOMINATIONS = (5, 10, 20, 50, 100, 200)
SLOT = r"([A-F][1-9])"
COIN = r"(5|10|20|50|100|200)"

COMMANDS = [
    ("LOAD", re.compile(rf"LOAD {SLOT} ([a-z]{{1,12}}) ([1-9][0-9]{{0,3}}) (0|[1-9][0-9]?)")),
    ("FILL", re.compile(rf"FILL {COIN} ([1-9][0-9]{{0,2}})")),
    ("INSERT", re.compile(r"INSERT ([1-9][0-9]{0,5})")),
    ("SELECT", re.compile(rf"SELECT {SLOT}")),
    ("REFUND", re.compile(r"REFUND")),
    ("STOCK", re.compile(rf"STOCK {SLOT}")),
    ("COINS", re.compile(r"COINS")),
]


@dataclass
class Slot:
    name: str
    price: int
    count: int


def coin_list(coins):
    parts = [f"{d}x{coins[d]}" for d in reversed(DENOMINATIONS) if coins[d]]
    return " ".join(parts) if parts else "-"


def greedy_change(amount, available):
    """Return a Counter of coins paying amount by the greedy rule, or None."""
    change = Counter()
    for d in reversed(DENOMINATIONS):
        take = min(available[d], amount // d)
        if take:
            change[d] = take
            amount -= take * d
    return change if amount == 0 else None


class Machine:
    def __init__(self):
        self.tubes = Counter({d: 0 for d in DENOMINATIONS})
        self.escrow = Counter()
        self.slots = {}

    @property
    def credit(self):
        return sum(d * n for d, n in self.escrow.items())

    def load(self, slot, name, price, count):
        if price % 5:
            return "ERR bad command"
        self.slots[slot] = Slot(name, price, count)
        return "OK"

    def fill(self, coin, n):
        self.tubes[coin] += n
        return "OK"

    def insert(self, coin):
        if coin not in DENOMINATIONS:
            return f"REJECT {coin}"
        self.escrow[coin] += 1
        return f"CREDIT {self.credit}"

    def select(self, slot_name):
        slot = self.slots.get(slot_name)
        if slot is None:
            return "ERR no such slot"
        if slot.count == 0:
            return "ERR sold out"
        credit = self.credit
        if credit < slot.price:
            return f"ERR need {slot.price - credit}"
        pool = self.tubes + self.escrow
        owed = credit - slot.price
        change = greedy_change(owed, pool)
        if change is None:
            return "ERR no change"
        for d in DENOMINATIONS:
            self.tubes[d] = pool[d] - change[d]
        self.escrow.clear()
        slot.count -= 1
        return f"VEND {slot.name} {owed} {coin_list(change)}"

    def refund(self):
        response = f"REFUND {self.credit} {coin_list(self.escrow)}"
        self.escrow.clear()
        return response

    def stock(self, slot_name):
        slot = self.slots.get(slot_name)
        if slot is None:
            return "ERR no such slot"
        return f"{slot_name} {slot.name} {slot.price} {slot.count}"

    def coins(self):
        return " ".join(f"{d}x{self.tubes[d]}" for d in DENOMINATIONS)

    def handle(self, line):
        for command, pattern in COMMANDS:
            m = pattern.fullmatch(line)
            if m:
                break
        else:
            return "ERR bad command"
        args = m.groups()
        if command == "LOAD":
            return self.load(args[0], args[1], int(args[2]), int(args[3]))
        if command == "FILL":
            return self.fill(int(args[0]), int(args[1]))
        if command == "INSERT":
            return self.insert(int(args[0]))
        if command == "SELECT":
            return self.select(args[0])
        if command == "REFUND":
            return self.refund()
        if command == "STOCK":
            return self.stock(args[0])
        return self.coins()


def main(argv):
    if argv:
        print("usage: vending < commands", file=sys.stderr)
        return 2
    machine = Machine()
    for raw in sys.stdin.buffer:
        line = raw.decode("latin-1")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        sys.stdout.write(machine.handle(line) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
