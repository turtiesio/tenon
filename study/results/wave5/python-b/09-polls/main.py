import re
import sys
from pathlib import Path

NAME = re.compile(r'[a-z0-9]{1,12}')
CHANGES = {'OK', 'VOTED', 'CHANGED'}


class Polls:
    def __init__(self):
        self.polls = {}

    def respond(self, line):
        parts = line.split(' ')
        command = parts[0]
        valid = False
        if command == 'CREATE':
            valid = 4 <= len(parts) <= 11 and len(set(parts[2:])) == len(parts[2:])
        elif command == 'VOTE':
            valid = len(parts) == 4
        elif command in ('CLOSE', 'RESULT'):
            valid = len(parts) == 2
        if not valid or any(not NAME.fullmatch(token) for token in parts[1:]):
            return 'ERR bad command'
        name = parts[1]
        if command == 'CREATE':
            if name in self.polls:
                return 'ERR poll exists'
            self.polls[name] = {'options': parts[2:], 'votes': {}, 'closed': False}
            return 'OK'
        if name not in self.polls:
            return 'ERR no such poll'
        poll = self.polls[name]
        if command == 'RESULT':
            counts = dict.fromkeys(poll['options'], 0)
            for option in poll['votes'].values():
                counts[option] += 1
            state = 'closed' if poll['closed'] else 'open'
            return ' '.join([name, state, *(f'{option}={count}' for option, count in counts.items())])
        if poll['closed']:
            return 'ERR poll closed'
        if command == 'CLOSE':
            poll['closed'] = True
            return 'OK'
        voter, option = parts[2:]
        if option not in poll['options']:
            return 'ERR no such option'
        previous = poll['votes'].get(voter)
        if previous == option:
            return 'UNCHANGED'
        poll['votes'][voter] = option
        return 'VOTED' if previous is None else 'CHANGED'


def run(directory):
    directory = Path(directory)
    if not directory.exists():
        directory.mkdir()
    if not directory.is_dir():
        raise ValueError('data path is not a directory')
    journal = directory / 'polls.log'
    state = Polls()
    try:
        data = journal.read_bytes()
    except FileNotFoundError:
        data = b''
    end = data.rfind(b'\n') + 1
    complete = data[:end]
    for raw in complete.split(b'\n')[:-1]:
        line = raw.decode('utf-8')
        if line.split(' ')[0] not in ('CREATE', 'VOTE', 'CLOSE') or state.respond(line) not in CHANGES:
            raise ValueError('invalid journal')
    if end != len(data):
        with journal.open('r+b') as stream:
            stream.truncate(end)
    stream = None
    try:
        for raw in sys.stdin.buffer:
            line = raw.decode('utf-8').removesuffix('\n').removesuffix('\r')
            response = state.respond(line)
            if response in CHANGES:
                if stream is None:
                    stream = journal.open('ab')
                stream.write((line + '\n').encode('utf-8'))
                stream.flush()
            print(response, flush=True)
    finally:
        if stream is not None:
            stream.close()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('expected data directory', file=sys.stderr)
        sys.exit(2)
    try:
        run(sys.argv[1])
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
