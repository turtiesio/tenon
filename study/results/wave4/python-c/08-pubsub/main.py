"""pubsub: an in-memory topic-based message broker driven by a line protocol."""
import re
import sys
from collections import deque
from dataclasses import dataclass, field

CLIENT = r"[a-z][a-z0-9]{0,15}"
SEG = r"[a-z0-9]{1,16}"
TOPIC = rf"{SEG}(?:\.{SEG}){{0,7}}"
PSEG = rf"(?:{SEG}|\*)"
# Up to 8 segments; '#' only as the last one.
PATTERN = rf"(?:{PSEG}(?:\.{PSEG}){{0,7}}|(?:{PSEG}\.){{0,7}}#)"
TEXT = r"[A-Za-z0-9_.!?-]{1,32}"
MAX = r"[1-9][0-9]{0,2}"

COMMANDS = {
    "SUB": re.compile(rf"SUB ({CLIENT}) ({PATTERN})"),
    "UNSUB": re.compile(rf"UNSUB ({CLIENT}) ({PATTERN})"),
    "PUB": re.compile(rf"PUB ({TOPIC}) ({TEXT})"),
    "POLL": re.compile(rf"POLL ({CLIENT}) ({MAX})"),
    "STATS": re.compile(rf"STATS ({CLIENT})"),
}
MAILBOX_SIZE = 3


def matches(pattern, topic):
    """Match pattern segments against topic segments (rule 4)."""
    if pattern[-1] == "#":
        prefix = pattern[:-1]
        if len(topic) < len(prefix):
            return False
    else:
        prefix = pattern
        if len(topic) != len(prefix):
            return False
    return all(p == "*" or p == t for p, t in zip(prefix, topic))


@dataclass
class Client:
    subs: dict = field(default_factory=dict)  # pattern string -> segment list
    mailbox: deque = field(default_factory=deque)
    dropped: int = 0


class Broker:
    def __init__(self):
        self.clients = {}

    def client(self, name):
        if name not in self.clients:
            self.clients[name] = Client()
        return self.clients[name]

    def handle(self, line):
        name, _, _ = line.partition(" ")
        pattern = COMMANDS.get(name)
        m = pattern.fullmatch(line) if pattern else None
        if not m:
            return "ERR bad command"
        return getattr(self, "do_" + name.lower())(*m.groups())

    def do_sub(self, who, pattern):
        client = self.client(who)
        if pattern in client.subs:
            return "ERR already subscribed"
        client.subs[pattern] = pattern.split(".")
        return "OK"

    def do_unsub(self, who, pattern):
        client = self.client(who)
        if pattern not in client.subs:
            return "ERR not subscribed"
        del client.subs[pattern]
        return "OK"

    def do_pub(self, topic, text):
        segments = topic.split(".")
        message = f"{topic}={text}"
        delivered = 0
        for client in self.clients.values():
            if any(matches(p, segments) for p in client.subs.values()):
                if len(client.mailbox) == MAILBOX_SIZE:
                    client.mailbox.popleft()
                    client.dropped += 1
                client.mailbox.append(message)
                delivered += 1
        return f"DELIVERED {delivered}"

    def do_poll(self, who, limit):
        client = self.client(who)
        k = min(int(limit), len(client.mailbox))
        taken = [client.mailbox.popleft() for _ in range(k)]
        return " ".join([f"MSGS {k}", *taken])

    def do_stats(self, who):
        client = self.client(who)
        return f"subs={len(client.subs)} queued={len(client.mailbox)} dropped={client.dropped}"


def main(argv):
    if argv:
        print("usage: pubsub  (commands on stdin)", file=sys.stderr)
        return 2

    broker = Broker()
    stdin = sys.stdin.buffer
    while True:
        raw = stdin.readline()
        if not raw:
            break
        line = raw.decode("latin-1").removesuffix("\n").removesuffix("\r")
        sys.stdout.write(broker.handle(line) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
