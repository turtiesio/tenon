#!/usr/bin/env python3
"""inv: inventory service with expiring reservations, driven by a line protocol."""

import heapq
import re
import sys
from dataclasses import dataclass

TIME_RE = re.compile(r"[0-9]{1,12}")
SKU_RE = re.compile(r"[A-Z0-9-]{1,20}")
ID_RE = re.compile(r"[0-9]{1,9}")
COUNT_RE = re.compile(r"[0-9]{1,9}")

BAD_COMMAND = "ERR bad command"

ACTIVE, COMMITTED, RELEASED, EXPIRED = "active", "committed", "released", "expired"


@dataclass
class Hold:
    sku: str
    qty: int
    expires: int
    state: str = ACTIVE


def parse_count(text):
    """A qty or ttl: 1..999999999, or None if malformed."""
    if COUNT_RE.fullmatch(text) and int(text) >= 1:
        return int(text)
    return None


def parse(line):
    """Parse a command line into (time, name, args), or None if malformed.

    Numeric arguments come back already converted.
    """
    parts = line.split(" ")
    if len(parts) < 2 or not TIME_RE.fullmatch(parts[0]):
        return None
    time, name, args = int(parts[0]), parts[1], parts[2:]

    if name in ("ADD", "REMOVE"):
        qty = parse_count(args[1]) if len(args) == 2 else None
        if qty is None or not SKU_RE.fullmatch(args[0]):
            return None
        return time, name, (args[0], qty)
    if name == "RESERVE":
        if len(args) != 3 or not SKU_RE.fullmatch(args[0]):
            return None
        qty, ttl = parse_count(args[1]), parse_count(args[2])
        if qty is None or ttl is None:
            return None
        return time, name, (args[0], qty, ttl)
    if name in ("COMMIT", "RELEASE"):
        if len(args) != 1 or not ID_RE.fullmatch(args[0]):
            return None
        return time, name, (int(args[0]),)
    if name == "AVAIL":
        if len(args) != 1 or not SKU_RE.fullmatch(args[0]):
            return None
        return time, name, (args[0],)
    if name == "STATS":
        return (time, name, ()) if not args else None
    return None


class Inventory:
    def __init__(self):
        self.clock = 0
        self.on_hand = {}  # sku -> quantity in the warehouse
        self.held = {}  # sku -> quantity in active holds
        self.holds = {}  # id -> Hold
        self.expiry_queue = []  # heap of (expires, id)
        self.counts = {COMMITTED: 0, RELEASED: 0, EXPIRED: 0}
        self.active = 0

    def execute(self, line):
        parsed = parse(line)
        if parsed is None:
            return BAD_COMMAND
        time, name, args = parsed
        if time < self.clock:
            return "ERR time went backwards"
        self.clock = time
        self.expire_holds(time)
        return getattr(self, name.lower())(*args)

    def expire_holds(self, now):
        while self.expiry_queue and self.expiry_queue[0][0] <= now:
            _, hold_id = heapq.heappop(self.expiry_queue)
            hold = self.holds[hold_id]
            if hold.state == ACTIVE:
                self.finish(hold, EXPIRED)

    def finish(self, hold, state):
        """Move an active hold to a final state and free its quantity."""
        hold.state = state
        self.held[hold.sku] -= hold.qty
        self.active -= 1
        self.counts[state] += 1

    def available(self, sku):
        return self.on_hand.get(sku, 0) - self.held.get(sku, 0)

    def add(self, sku, qty):
        self.on_hand[sku] = self.on_hand.get(sku, 0) + qty
        return f"OK {self.on_hand[sku]}"

    def remove(self, sku, qty):
        available = self.available(sku)
        if qty > available:
            return f"ERR insufficient {available}"
        self.on_hand[sku] -= qty
        return f"OK {self.on_hand[sku]}"

    def reserve(self, sku, qty, ttl):
        available = self.available(sku)
        if qty > available:
            return f"ERR insufficient {available}"
        hold_id = len(self.holds) + 1
        hold = Hold(sku, qty, self.clock + ttl)
        self.holds[hold_id] = hold
        heapq.heappush(self.expiry_queue, (hold.expires, hold_id))
        self.held[sku] = self.held.get(sku, 0) + qty
        self.active += 1
        return f"HOLD {hold_id}"

    def settle(self, hold_id, new_state):
        hold = self.holds.get(hold_id)
        if hold is None or hold.state in (COMMITTED, RELEASED):
            return "ERR no such hold"
        if hold.state == EXPIRED:
            return "ERR expired"
        if new_state == COMMITTED:
            self.on_hand[hold.sku] -= hold.qty
        self.finish(hold, new_state)
        return "OK"

    def commit(self, hold_id):
        return self.settle(hold_id, COMMITTED)

    def release(self, hold_id):
        return self.settle(hold_id, RELEASED)

    def avail(self, sku):
        on_hand, held = self.on_hand.get(sku, 0), self.held.get(sku, 0)
        return f"{sku} on_hand={on_hand} held={held} available={on_hand - held}"

    def stats(self):
        return (
            f"holds={self.active} committed={self.counts[COMMITTED]} "
            f"expired={self.counts[EXPIRED]} released={self.counts[RELEASED]}"
        )


def main(argv):
    if argv:
        print("usage: inv (takes no arguments)", file=sys.stderr)
        return 2
    inventory = Inventory()
    for raw in sys.stdin.buffer:
        line = raw.decode("latin-1")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        sys.stdout.write(inventory.execute(line) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
