from collections import deque
from dataclasses import dataclass, field
import re
import sys

CLIENT = r'[a-z][a-z0-9]{0,15}'
SEGMENT = r'[a-z0-9]{1,16}'
TOPIC = rf'{SEGMENT}(?:\.{SEGMENT}){{0,7}}'
PATTERN = rf'(?:{SEGMENT}|\*|#)(?:\.(?:{SEGMENT}|\*|#)){{0,7}}'
FORMS = [
    re.compile(rf'(SUB|UNSUB) ({CLIENT}) ({PATTERN})'),
    re.compile(rf'(PUB) ({TOPIC}) ([A-Za-z0-9_.!?-]{{1,32}})'),
    re.compile(rf'(POLL) ({CLIENT}) ([1-9][0-9]{{0,2}})'),
    re.compile(rf'(STATS) ({CLIENT})'),
]


@dataclass
class Client:
    subscriptions: set = field(default_factory=set)
    messages: deque = field(default_factory=deque)
    dropped: int = 0


def matches(pattern, topic):
    parts = pattern.split('.')
    levels = topic.split('.')
    if parts[-1] == '#':
        parts = parts[:-1]
        if len(levels) < len(parts):
            return False
    elif len(parts) != len(levels):
        return False
    return all(part == '*' or part == level for part, level in zip(parts, levels))


class Broker:
    def __init__(self):
        self.clients = {}

    def command(self, line):
        match = next((match for form in FORMS if (match := form.fullmatch(line))), None)
        if match is None:
            return 'ERR bad command'
        args = match.groups()
        kind, name = args[:2]
        if kind in ('SUB', 'UNSUB') and '#' in args[2].split('.')[:-1]:
            return 'ERR bad command'
        if kind == 'PUB':
            delivered = 0
            for client in self.clients.values():
                if any(matches(pattern, name) for pattern in client.subscriptions):
                    if len(client.messages) == 3:
                        client.messages.popleft()
                        client.dropped += 1
                    client.messages.append(f'{name}={args[2]}')
                    delivered += 1
            return f'DELIVERED {delivered}'
        client = self.clients.setdefault(name, Client())
        if kind == 'SUB':
            if args[2] in client.subscriptions:
                return 'ERR already subscribed'
            client.subscriptions.add(args[2])
            return 'OK'
        if kind == 'UNSUB':
            if args[2] not in client.subscriptions:
                return 'ERR not subscribed'
            client.subscriptions.remove(args[2])
            return 'OK'
        if kind == 'STATS':
            return f'subs={len(client.subscriptions)} queued={len(client.messages)} dropped={client.dropped}'
        count = min(int(args[2]), len(client.messages))
        messages = [client.messages.popleft() for _ in range(count)]
        return ' '.join([f'MSGS {count}'] + messages)


def main():
    if len(sys.argv) != 1:
        print('No arguments allowed', file=sys.stderr)
        return 2
    broker = Broker()
    for raw in sys.stdin.buffer:
        line = raw.decode('utf-8', errors='replace').removesuffix('\n').removesuffix('\r')
        print(broker.command(line), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
