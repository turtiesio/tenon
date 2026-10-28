import re
import sys


class Buffer:
    def __init__(self):
        self.lines = []
        self.undo = []
        self.redo = []

    def change(self, start, stop, replacement):
        old = self.lines[start:stop]
        self.lines[start:stop] = replacement
        self.undo.append((start, old, replacement))
        self.redo.clear()
        return f'OK {len(self.lines)}'

    def command(self, line):
        if line == 'COUNT':
            return str(len(self.lines))
        if line in ('UNDO', 'REDO'):
            source, destination = (self.undo, self.redo) if line == 'UNDO' else (self.redo, self.undo)
            if not source:
                return 'ERR nothing to ' + line.lower()
            start, old, new = source.pop()
            before, after = (new, old) if line == 'UNDO' else (old, new)
            self.lines[start:start + len(before)] = after
            destination.append((start, old, new))
            return f'OK {len(self.lines)}'
        if line.startswith('APPEND '):
            return self.change(len(self.lines), len(self.lines), [line[7:]])
        if line.startswith('FIND ') and line[5:]:
            found = [str(i) for i, text in enumerate(self.lines, 1) if line[5:] in text]
            return ' '.join(found) or 'NONE'
        match = re.fullmatch(r'(INSERT|REPLACE) ([0-9]{1,9}) (.*)', line)
        if match:
            command, number, text = match.groups()
            number = int(number)
            if not 1 <= number <= len(self.lines) + (command == 'INSERT'):
                return 'ERR bad line'
            start = number - 1
            return self.change(start, start if command == 'INSERT' else number, [text])
        match = re.fullmatch(r'DELETE ([0-9]{1,9})(?: ([0-9]{1,9}))?', line)
        if match:
            start = int(match[1])
            stop = int(match[2]) if match[2] is not None else start
            if not 1 <= start <= stop <= len(self.lines):
                return 'ERR bad line'
            return self.change(start - 1, stop, [])
        match = re.fullmatch(r'PRINT ([0-9]{1,9})', line)
        if match:
            number = int(match[1])
            if not 1 <= number <= len(self.lines):
                return 'ERR bad line'
            return f'{number}|{self.lines[number - 1]}'
        return 'ERR bad command'


def main():
    if len(sys.argv) != 1:
        print('invalid arguments', file=sys.stderr)
        return 2
    buffer = Buffer()
    for raw in sys.stdin.buffer:
        line = raw.removesuffix(b'\n').removesuffix(b'\r').decode('ascii')
        print(buffer.command(line), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
