import os
import re
import sys
from pathlib import Path


class Todo:
    def __init__(self, directory):
        self.directory = directory
        self.items = {}
        self.next_id = 1
        directory.mkdir(exist_ok=True)
        if not directory.is_dir():
            raise ValueError('not a directory')
        temporary = directory / 'todo.db.tmp'
        temporary.unlink(missing_ok=True)
        path = directory / 'todo.db'
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            return
        text = data.decode('ascii')
        if not text.endswith('\n'):
            raise ValueError('missing final newline')
        lines = text[:-1].split('\n')
        if len(lines) < 2 or lines[0] != 'TODO 1' or not re.fullmatch(r'next [1-9][0-9]{0,8}', lines[1]):
            raise ValueError('invalid header')
        self.next_id = int(lines[1][5:])
        previous = 0
        for line in lines[2:]:
            match = re.fullmatch(r'([1-9][0-9]{0,8}) ([1-9]) ([od]) ([ -~]+)', line)
            if not match:
                raise ValueError('invalid item')
            number, priority, status, body = match.groups()
            number = int(number)
            if not previous < number < self.next_id:
                raise ValueError('invalid item order')
            previous = number
            self.items[number] = (int(priority), status, body)

    def save(self):
        path = self.directory / 'todo.db.tmp'
        with path.open('w', encoding='ascii', newline='\n') as stream:
            stream.write(f'TODO 1\nnext {self.next_id}\n')
            for number, (priority, status, body) in sorted(self.items.items()):
                stream.write(f'{number} {priority} {status} {body}\n')
        os.replace(path, self.directory / 'todo.db')

    def show(self, number):
        priority, status, body = self.items[number]
        return f'{number} {priority} {"open" if status == "o" else "done"} {body}'

    def command(self, line):
        if any(c < ' ' or c > '~' for c in line):
            return 'ERR bad command'
        match = re.fullmatch(r'ADD ([1-9]) (.+)', line)
        if match:
            number = self.next_id
            self.items[number] = (int(match[1]), 'o', match[2])
            self.next_id += 1
            self.save()
            return f'ADDED {number}'
        match = re.fullmatch(r'(DONE|SHOW) ([0-9]{1,9})', line)
        if match:
            command, raw = match.groups()
            number = int(raw)
            if number not in self.items:
                return 'ERR no such item'
            if command == 'SHOW':
                return self.show(number)
            priority, status, body = self.items[number]
            if status == 'd':
                return 'ERR already done'
            self.items[number] = priority, 'd', body
            self.save()
            return 'OK'
        if line in ('LIST', 'NEXT'):
            opened = sorted((priority, number) for number, (priority, status, _) in self.items.items() if status == 'o')
            if line == 'LIST':
                return 'OPEN' + ''.join(f' {number}' for _, number in opened)
            return self.show(opened[0][1]) if opened else 'NONE'
        if line == 'PURGE':
            done = [number for number, (_, status, _) in self.items.items() if status == 'd']
            for number in done:
                del self.items[number]
            if done:
                self.save()
            return f'PURGED {len(done)}'
        if line == 'STATS':
            opened = sum(status == 'o' for _, status, _ in self.items.values())
            return f'open={opened} done={len(self.items) - opened} next_id={self.next_id}'
        return 'ERR bad command'


def main():
    if len(sys.argv) != 2:
        print('invalid arguments', file=sys.stderr)
        return 2
    try:
        todo = Todo(Path(sys.argv[1]))
        for raw in sys.stdin.buffer:
            line = raw.removesuffix(b'\n').removesuffix(b'\r').decode('latin1')
            print(todo.command(line), flush=True)
    except (OSError, ValueError, UnicodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
