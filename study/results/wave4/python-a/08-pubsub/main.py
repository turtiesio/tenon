import re
import sys
from collections import deque

CLIENT_RE = re.compile(r"[a-z][a-z0-9]{0,15}")
SEGMENT_RE = re.compile(r"[a-z0-9]{1,16}")
PATTERN_SEGMENT_RE = re.compile(r"[a-z0-9]{1,16}|\*|#")
TEXT_RE = re.compile(r"[A-Za-z0-9_.!?-]{1,32}")
MAX_RE = re.compile(r"[1-9][0-9]{0,2}")

MAILBOX_SIZE = 3
MAX_SEGMENTS = 8


def valid_topic(topic):
    segments = topic.split(".")
    return len(segments) <= MAX_SEGMENTS and all(SEGMENT_RE.fullmatch(s) for s in segments)


def valid_pattern(pattern):
    segments = pattern.split(".")
    if len(segments) > MAX_SEGMENTS:
        return False
    if not all(PATTERN_SEGMENT_RE.fullmatch(s) for s in segments):
        return False
    return "#" not in segments[:-1]


def matches(pattern, topic):
    p = pattern.split(".")
    t = topic.split(".")
    if p[-1] == "#":
        p = p[:-1]
        if len(t) < len(p):
            return False
        t = t[:len(p)]
    elif len(p) != len(t):
        return False
    return all(ps == "*" or ps == ts for ps, ts in zip(p, t))


class Client:
    def __init__(self):
        self.subs = set()
        self.mailbox = deque()
        self.dropped = 0

    def deliver(self, message):
        if len(self.mailbox) >= MAILBOX_SIZE:
            self.mailbox.popleft()
            self.dropped += 1
        self.mailbox.append(message)


class Broker:
    def __init__(self):
        self.clients = {}

    def client(self, name):
        if name not in self.clients:
            self.clients[name] = Client()
        return self.clients[name]

    def handle(self, line):
        tokens = line.split(" ")
        cmd, args = tokens[0], tokens[1:]
        if cmd == "SUB" and len(args) == 2 and CLIENT_RE.fullmatch(args[0]) and valid_pattern(args[1]):
            return self.subscribe(*args)
        if cmd == "UNSUB" and len(args) == 2 and CLIENT_RE.fullmatch(args[0]) and valid_pattern(args[1]):
            return self.unsubscribe(*args)
        if cmd == "PUB" and len(args) == 2 and valid_topic(args[0]) and TEXT_RE.fullmatch(args[1]):
            return self.publish(*args)
        if cmd == "POLL" and len(args) == 2 and CLIENT_RE.fullmatch(args[0]) and MAX_RE.fullmatch(args[1]):
            return self.poll(args[0], int(args[1]))
        if cmd == "STATS" and len(args) == 1 and CLIENT_RE.fullmatch(args[0]):
            return self.stats(args[0])
        return "ERR bad command"

    def subscribe(self, name, pattern):
        client = self.client(name)
        if pattern in client.subs:
            return "ERR already subscribed"
        client.subs.add(pattern)
        return "OK"

    def unsubscribe(self, name, pattern):
        client = self.client(name)
        if pattern not in client.subs:
            return "ERR not subscribed"
        client.subs.remove(pattern)
        return "OK"

    def publish(self, topic, text):
        message = f"{topic}={text}"
        delivered = 0
        for client in self.clients.values():
            if any(matches(p, topic) for p in client.subs):
                client.deliver(message)
                delivered += 1
        return f"DELIVERED {delivered}"

    def poll(self, name, limit):
        client = self.client(name)
        count = min(limit, len(client.mailbox))
        taken = [client.mailbox.popleft() for _ in range(count)]
        return " ".join([f"MSGS {count}"] + taken)

    def stats(self, name):
        client = self.client(name)
        return f"subs={len(client.subs)} queued={len(client.mailbox)} dropped={client.dropped}"


def main():
    if len(sys.argv) > 1:
        print("pubsub: no arguments expected", file=sys.stderr)
        sys.exit(2)
    broker = Broker()
    for raw in sys.stdin.buffer:
        line = raw.decode("latin-1")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        sys.stdout.write(broker.handle(line) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
