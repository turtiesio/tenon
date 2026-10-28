from collections import deque
import re
import sys

NAME = r'[a-z0-9]{1,12}'
COMMAND = re.compile(f'(?:LOCK ({NAME}) ({NAME}) ([SX])|(UNLOCK) ({NAME}) ({NAME})|(DROP|STATUS|HELD) ({NAME}))')


class Resource:
    def __init__(self):
        self.holders = {}
        self.queue = deque()

    def compatible(self, mode):
        return not self.holders or (mode == 'S' and all(value == 'S' for value in self.holders.values()))

    def pump(self, name):
        grants = []
        while self.queue and self.compatible(self.queue[0][1]):
            client, mode = self.queue.popleft()
            self.holders[client] = mode
            grants.append(f'{client}:{name}:{mode}')
        return grants


class Service:
    def __init__(self):
        self.resources = {}

    def command(self, line):
        if not COMMAND.fullmatch(line):
            return 'ERR bad command'
        command, *args = line.split(' ')
        if command in ('LOCK', 'UNLOCK', 'STATUS'):
            name = args[0] if command == 'STATUS' else args[1]
            resource = self.resources.setdefault(name, Resource())
        if command == 'LOCK':
            client, _, mode = args
            if client in resource.holders:
                return 'ERR already held'
            if any(waiter == client for waiter, _ in resource.queue):
                return 'ERR already waiting'
            if not resource.queue and resource.compatible(mode):
                resource.holders[client] = mode
                return 'GRANTED'
            resource.queue.append((client, mode))
            return 'WAITING'
        if command == 'UNLOCK':
            client = args[0]
            if client not in resource.holders:
                return 'ERR not held'
            del resource.holders[client]
            return ' '.join(['OK'] + resource.pump(name))
        if command == 'STATUS':
            holders = ','.join(f'{client}:{mode}' for client, mode in sorted(resource.holders.items())) or '-'
            queue = ','.join(f'{client}:{mode}' for client, mode in resource.queue) or '-'
            return f'{name} holders={holders} queue={queue}'
        client = args[0]
        if command == 'HELD':
            return ','.join(f'{name}:{resource.holders[client]}' for name, resource in sorted(self.resources.items()) if client in resource.holders) or '-'
        released = cancelled = 0
        affected = []
        for name, resource in sorted(self.resources.items()):
            count = len(resource.queue)
            resource.queue = deque((waiter, mode) for waiter, mode in resource.queue if waiter != client)
            removed = count - len(resource.queue)
            held = client in resource.holders
            if held:
                del resource.holders[client]
            released += held
            cancelled += removed
            if held or removed:
                affected.append((name, resource))
        grants = []
        for name, resource in affected:
            grants.extend(resource.pump(name))
        return ' '.join([f'OK released={released} cancelled={cancelled}'] + grants)


def main():
    if len(sys.argv) != 1:
        print('no arguments allowed', file=sys.stderr)
        return 2
    service = Service()
    for raw in sys.stdin.buffer:
        line = raw.removesuffix(b'\n').removesuffix(b'\r').decode('ascii')
        print(service.command(line), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
