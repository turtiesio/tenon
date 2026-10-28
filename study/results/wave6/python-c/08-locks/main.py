"""locks: shared/exclusive lock manager over a line protocol."""
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field

NAME = re.compile(r"[a-z0-9]{1,12}")
MODES = ("S", "X")


class CommandError(Exception):
    pass


@dataclass
class Resource:
    holders: dict[str, str] = field(default_factory=dict)  # client -> mode
    queue: list[tuple[str, str]] = field(default_factory=list)  # (client, mode)

    def compatible(self, mode: str) -> bool:
        if not self.holders:
            return True
        return mode == "S" and all(m == "S" for m in self.holders.values())


def by_bytes(s: str) -> bytes:
    return s.encode()


class LockManager:
    def __init__(self) -> None:
        self.resources: dict[str, Resource] = defaultdict(Resource)
        self.held: dict[str, dict[str, str]] = defaultdict(dict)  # client -> res -> mode
        self.waiting: dict[str, set[str]] = defaultdict(set)  # client -> resources

    def handle(self, line: str) -> str:
        tokens = line.split(" ")
        command, args = tokens[0], tokens[1:]
        handlers = {
            "LOCK": (self.lock, 3),
            "UNLOCK": (self.unlock, 2),
            "DROP": (self.drop, 1),
            "STATUS": (self.status, 1),
            "HELD": (self.held_by, 1),
        }
        handler = handlers.get(command)
        try:
            if handler is None or len(args) != handler[1]:
                raise CommandError("bad command")
            names = args[:2] if command == "LOCK" else args
            if not all(NAME.fullmatch(a) for a in names):
                raise CommandError("bad command")
            if command == "LOCK" and args[2] not in MODES:
                raise CommandError("bad command")
            return handler[0](*args)
        except CommandError as e:
            return f"ERR {e}"

    def grant(self, client: str, res: str, mode: str) -> None:
        self.resources[res].holders[client] = mode
        self.held[client][res] = mode

    def pump(self, res: str) -> list[str]:
        resource = self.resources[res]
        grants = []
        while resource.queue and resource.compatible(resource.queue[0][1]):
            client, mode = resource.queue.pop(0)
            self.waiting[client].discard(res)
            self.grant(client, res, mode)
            grants.append(f"{client}:{res}:{mode}")
        return grants

    def lock(self, client: str, res: str, mode: str) -> str:
        if res in self.held[client]:
            raise CommandError("already held")
        if res in self.waiting[client]:
            raise CommandError("already waiting")
        resource = self.resources[res]
        if not resource.queue and resource.compatible(mode):
            self.grant(client, res, mode)
            return "GRANTED"
        resource.queue.append((client, mode))
        self.waiting[client].add(res)
        return "WAITING"

    def unlock(self, client: str, res: str) -> str:
        if res not in self.held[client]:
            raise CommandError("not held")
        del self.held[client][res]
        del self.resources[res].holders[client]
        return " ".join(["OK", *self.pump(res)])

    def drop(self, client: str) -> str:
        touched = set()
        cancelled = 0
        for res in self.waiting.pop(client, set()):
            resource = self.resources[res]
            resource.queue = [(c, m) for c, m in resource.queue if c != client]
            cancelled += 1
            touched.add(res)
        held = self.held.pop(client, {})
        for res in held:
            del self.resources[res].holders[client]
            touched.add(res)
        grants = []
        for res in sorted(touched, key=by_bytes):
            grants.extend(self.pump(res))
        return " ".join([f"OK released={len(held)} cancelled={cancelled}", *grants])

    def status(self, res: str) -> str:
        resource = self.resources.get(res, Resource())
        holders = ",".join(f"{c}:{resource.holders[c]}"
                           for c in sorted(resource.holders, key=by_bytes)) or "-"
        queue = ",".join(f"{c}:{m}" for c, m in resource.queue) or "-"
        return f"{res} holders={holders} queue={queue}"

    def held_by(self, client: str) -> str:
        locks = self.held.get(client, {})
        return ",".join(f"{r}:{locks[r]}" for r in sorted(locks, key=by_bytes)) or "-"


def main(argv: list[str]) -> int:
    if argv:
        print("usage: locks", file=sys.stderr)
        return 2
    manager = LockManager()
    for raw in sys.stdin.buffer:
        line = raw.decode("ascii", errors="replace")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        sys.stdout.write(manager.handle(line) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
