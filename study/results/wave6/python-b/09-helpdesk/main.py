from pathlib import Path
import re
import sys

NAME = r'[a-z0-9]{1,12}'
TICKET = r'T[1-9][0-9]{0,8}'
TITLE = r'[!-~](?:[ -~]{0,58}[!-~])?'
OPEN = re.compile(f'OPEN ({NAME}) ({TITLE})')
OTHER = re.compile(f'(?:ASSIGN ({TICKET}) ({NAME})|(CLOSE|REOPEN|SHOW) ({TICKET})|QUEUE ({NAME}|-))')
RECORD_OPEN = re.compile(f'OPEN ({TICKET}) ({NAME}) ({TITLE})')


class Desk:
    def __init__(self):
        self.tickets = {}
        self.next_id = 1

    def command(self, line):
        match = OPEN.fullmatch(line)
        if match:
            customer, title = match.groups()
            number = self.next_id
            self.next_id += 1
            self.tickets[number] = [customer, title, 'open', '-']
            return f'T{number}', f'OPEN T{number} {customer} {title}'
        if not OTHER.fullmatch(line):
            return 'ERR bad command', None
        command, *args = line.split(' ')
        if command == 'QUEUE':
            return ' '.join(f'T{number}' for number, ticket in self.tickets.items() if ticket[2] == 'open' and ticket[3] == args[0]) or '-', None
        number = int(args[0][1:])
        if number not in self.tickets:
            return 'ERR no such ticket', None
        ticket = self.tickets[number]
        customer, title, state, agent = ticket
        if command == 'SHOW':
            return f'T{number} {state} {customer} {agent} {title}', None
        if command in ('ASSIGN', 'CLOSE') and state == 'closed':
            return 'ERR closed', None
        if command == 'REOPEN' and state == 'open':
            return 'ERR not closed', None
        if command == 'ASSIGN':
            if agent == args[1]:
                return 'UNCHANGED', None
            ticket[3] = args[1]
        else:
            ticket[2] = 'closed' if command == 'CLOSE' else 'open'
        return 'OK', line

    def replay(self, data):
        for raw in data.splitlines(keepends=True):
            if not raw.endswith(b'\n'):
                raise ValueError('incomplete record')
            line = raw[:-1].decode('ascii')
            match = RECORD_OPEN.fullmatch(line)
            if match:
                tid, customer, title = match.groups()
                if tid != f'T{self.next_id}':
                    raise ValueError('incorrect ticket sequence')
                self.command(f'OPEN {customer} {title}')
            else:
                if not line.startswith(('ASSIGN ', 'CLOSE ', 'REOPEN ')):
                    raise ValueError('invalid journal record')
                response, record = self.command(line)
                if response != 'OK' or record is None:
                    raise ValueError('invalid journal transition')


def main():
    if len(sys.argv) != 2:
        print('expected DIR', file=sys.stderr)
        return 2
    try:
        directory = Path(sys.argv[1])
        directory.mkdir(exist_ok=True)
        journal = directory / 'tickets.log'
        try:
            data = journal.read_bytes()
        except FileNotFoundError:
            data = b''
        complete_length = data.rfind(b'\n') + 1
        desk = Desk()
        desk.replay(data[:complete_length])
        if complete_length != len(data):
            with journal.open('r+b') as handle:
                handle.truncate(complete_length)
        for raw in sys.stdin.buffer:
            line = raw.removesuffix(b'\n').removesuffix(b'\r').decode('ascii')
            response, record = desk.command(line)
            if record is not None:
                with journal.open('ab') as handle:
                    handle.write(record.encode('ascii') + b'\n')
                    handle.flush()
            print(response, flush=True)
    except (OSError, ValueError, UnicodeError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
