"""inv: inventory service with expiring reservations."""
import heapq
import re
import sys

TIME_RE = re.compile(r"[0-9]{1,12}")
SKU_RE = re.compile(r"[A-Z0-9-]{1,20}")
NUMBER_RE = re.compile(r"[0-9]{1,9}")
# command -> argument kinds
COMMANDS = {
    "ADD": ("sku", "qty"),
    "REMOVE": ("sku", "qty"),
    "RESERVE": ("sku", "qty", "qty"),
    "COMMIT": ("id",),
    "RELEASE": ("id",),
    "AVAIL": ("sku",),
    "STATS": (),
}


class CommandError(Exception):
    pass


def parse_arg(kind, tok):
    if kind == "sku":
        if SKU_RE.fullmatch(tok):
            return tok
    elif NUMBER_RE.fullmatch(tok):
        value = int(tok)
        if kind == "id" or value >= 1:
            return value
    raise CommandError("bad command")


def parse(line):
    tokens = line.split(" ")
    if len(tokens) < 2 or not TIME_RE.fullmatch(tokens[0]):
        raise CommandError("bad command")
    command, args = tokens[1], tokens[2:]
    kinds = COMMANDS.get(command)
    if kinds is None or len(args) != len(kinds):
        raise CommandError("bad command")
    return int(tokens[0]), command, [parse_arg(k, a) for k, a in zip(kinds, args)]


class Hold:
    def __init__(self, sku, qty, expires):
        self.sku = sku
        self.qty = qty
        self.expires = expires
        self.state = "active"


class Inventory:
    def __init__(self):
        self.clock = 0
        self.on_hand = {}
        self.held = {}
        self.holds = {}
        self.expiry_queue = []  # (expires, id) of holds that may still be active
        self.next_id = 1
        self.counts = {"active": 0, "committed": 0, "expired": 0, "released": 0}

    def handle(self, line):
        try:
            t, command, args = parse(line)
            if t < self.clock:
                raise CommandError("time went backwards")
            self.clock = t
            self.expire(t)
            return getattr(self, "do_" + command.lower())(t, *args)
        except CommandError as e:
            return f"ERR {e}"

    def expire(self, now):
        queue = self.expiry_queue
        while queue and queue[0][0] <= now:
            _, hold_id = heapq.heappop(queue)
            hold = self.holds[hold_id]
            if hold.state == "active":
                self.finish(hold, "expired")

    def finish(self, hold, state):
        hold.state = state
        self.held[hold.sku] -= hold.qty
        self.counts["active"] -= 1
        self.counts[state] += 1

    def available(self, sku):
        return self.on_hand.get(sku, 0) - self.held.get(sku, 0)

    def require(self, sku, qty):
        available = self.available(sku)
        if qty > available:
            raise CommandError(f"insufficient {available}")

    def do_add(self, t, sku, qty):
        self.on_hand[sku] = self.on_hand.get(sku, 0) + qty
        return f"OK {self.on_hand[sku]}"

    def do_remove(self, t, sku, qty):
        self.require(sku, qty)
        self.on_hand[sku] -= qty
        return f"OK {self.on_hand[sku]}"

    def do_reserve(self, t, sku, qty, ttl):
        self.require(sku, qty)
        hold_id = self.next_id
        self.next_id += 1
        self.holds[hold_id] = Hold(sku, qty, t + ttl)
        heapq.heappush(self.expiry_queue, (t + ttl, hold_id))
        self.held[sku] = self.held.get(sku, 0) + qty
        self.counts["active"] += 1
        return f"HOLD {hold_id}"

    def active_hold(self, hold_id):
        hold = self.holds.get(hold_id)
        if hold is None or hold.state in ("committed", "released"):
            raise CommandError("no such hold")
        if hold.state == "expired":
            raise CommandError("expired")
        return hold

    def do_commit(self, t, hold_id):
        hold = self.active_hold(hold_id)
        self.on_hand[hold.sku] -= hold.qty
        self.finish(hold, "committed")
        return "OK"

    def do_release(self, t, hold_id):
        self.finish(self.active_hold(hold_id), "released")
        return "OK"

    def do_avail(self, t, sku):
        on_hand, held = self.on_hand.get(sku, 0), self.held.get(sku, 0)
        return f"{sku} on_hand={on_hand} held={held} available={on_hand - held}"

    def do_stats(self, t):
        c = self.counts
        return (f"holds={c['active']} committed={c['committed']} "
                f"expired={c['expired']} released={c['released']}")


def main(argv):
    if argv:
        print("usage: inv (takes no arguments)", file=sys.stderr)
        return 2
    inventory = Inventory()
    stdin, stdout = sys.stdin.buffer, sys.stdout
    while True:
        raw = stdin.readline()
        if not raw:
            break
        line = raw.decode("latin-1")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        stdout.write(inventory.handle(line) + "\n")
        stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
