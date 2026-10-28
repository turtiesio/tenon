import re
import sys

NAME_RE = re.compile(r"[a-z0-9]{1,12}")
MODES = ("S", "X")


class Resource:
    def __init__(self):
        self.holders = {}  # client -> mode
        self.queue = []  # [(client, mode)], front first

    def compatible(self, mode):
        return not self.holders or (mode == "S" and all(m == "S" for m in self.holders.values()))

    def pump(self, name):
        """Grant queued requests from the front while possible; return grant strings."""
        grants = []
        while self.queue and self.compatible(self.queue[0][1]):
            client, mode = self.queue.pop(0)
            self.holders[client] = mode
            grants.append(f"{client}:{name}:{mode}")
        return grants

    def waiting_index(self, client):
        for i, (c, _) in enumerate(self.queue):
            if c == client:
                return i
        return None


class LockManager:
    def __init__(self):
        self.resources = {}

    def handle(self, line):
        tokens = line.split(" ")
        cmd, args = tokens[0], tokens[1:]
        valid = all(NAME_RE.fullmatch(a) for a in args[:2])
        if cmd == "LOCK" and len(args) == 3 and valid and args[2] in MODES:
            return self.lock(*args)
        if cmd == "UNLOCK" and len(args) == 2 and valid:
            return self.unlock(*args)
        if cmd == "DROP" and len(args) == 1 and valid:
            return self.drop(args[0])
        if cmd == "STATUS" and len(args) == 1 and valid:
            return self.status(args[0])
        if cmd == "HELD" and len(args) == 1 and valid:
            return self.held(args[0])
        return "ERR bad command"

    def lock(self, client, name, mode):
        res = self.resources.setdefault(name, Resource())
        if client in res.holders:
            return "ERR already held"
        if res.waiting_index(client) is not None:
            return "ERR already waiting"
        if not res.queue and res.compatible(mode):
            res.holders[client] = mode
            return "GRANTED"
        res.queue.append((client, mode))
        return "WAITING"

    def unlock(self, client, name):
        res = self.resources.get(name)
        if res is None or client not in res.holders:
            return "ERR not held"
        del res.holders[client]
        return " ".join(["OK"] + res.pump(name))

    def drop(self, client):
        touched = set()
        cancelled = 0
        for name, res in self.resources.items():
            i = res.waiting_index(client)
            if i is not None:
                del res.queue[i]
                cancelled += 1
                touched.add(name)
        released = 0
        for name, res in self.resources.items():
            if client in res.holders:
                del res.holders[client]
                released += 1
                touched.add(name)
        grants = []
        for name in sorted(touched):
            grants.extend(self.resources[name].pump(name))
        return " ".join([f"OK released={released} cancelled={cancelled}"] + grants)

    def status(self, name):
        res = self.resources.get(name)
        holders = sorted(res.holders.items()) if res else []
        queue = res.queue if res else []
        h = ",".join(f"{c}:{m}" for c, m in holders) or "-"
        q = ",".join(f"{c}:{m}" for c, m in queue) or "-"
        return f"{name} holders={h} queue={q}"

    def held(self, client):
        locks = sorted((name, res.holders[client])
                       for name, res in self.resources.items() if client in res.holders)
        return ",".join(f"{name}:{mode}" for name, mode in locks) or "-"


def main(argv):
    if argv:
        print("usage: locks", file=sys.stderr)
        return 2
    manager = LockManager()
    for raw in sys.stdin.buffer:
        line = raw.decode("latin-1")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        sys.stdout.write(manager.handle(line) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
