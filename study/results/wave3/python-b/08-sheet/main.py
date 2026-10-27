import re
import sys

CELL = r'[A-Z][1-9][0-9]?'
TERM = re.compile(r'[0-9]{1,9}|' + CELL + r'|SUM\(' + CELL + ':' + CELL + r'\)')


def parse(contents):
    if re.fullmatch(r'-?[0-9]{1,9}', contents):
        return [(1, int(contents))], set()
    if not contents.startswith('='):
        raise ValueError()
    i = 1
    sign = 1
    if contents[i:i+1] == '-':
        sign, i = -1, i + 1
    terms, deps = [], set()
    while True:
        match = TERM.match(contents, i)
        if not match:
            raise ValueError()
        text = match[0]
        i = match.end()
        if text.isdigit():
            value = int(text)
        elif text.startswith('SUM('):
            a, b = text[4:-1].split(':')
            cols = sorted((ord(a[0]), ord(b[0])))
            rows = sorted((int(a[1:]), int(b[1:])))
            value = [chr(c) + str(r) for c in range(cols[0], cols[1] + 1) for r in range(rows[0], rows[1] + 1)]
            deps.update(value)
        else:
            value = [text]
            deps.add(text)
        terms.append((sign, value))
        if i == len(contents):
            return terms, deps
        if contents[i] not in '+-':
            raise ValueError()
        sign = 1 if contents[i] == '+' else -1
        i += 1


class Sheet:
    def __init__(self):
        self.cells = {}
        self.cache = {}

    def cyclic(self, cell, deps):
        pending = list(deps)
        visited = set()
        while pending:
            current = pending.pop()
            if current == cell:
                return True
            if current not in visited:
                visited.add(current)
                if current in self.cells:
                    pending.extend(self.cells[current][2])
        return False

    def value(self, cell):
        stack = [(cell, False)]
        seen = set()
        while stack:
            current, expanded = stack.pop()
            if current in self.cache:
                continue
            if current not in self.cells:
                self.cache[current] = 0
                continue
            _, terms, deps = self.cells[current]
            if expanded:
                if any(self.cache[d] is None for d in deps):
                    self.cache[current] = None
                    continue
                result = sum(sign * (value if isinstance(value, int) else sum(self.cache[d] for d in value)) for sign, value in terms)
                self.cache[current] = result if abs(result) <= 10**12 else None
            elif current not in seen:
                seen.add(current)
                stack.append((current, True))
                stack.extend((dep, False) for dep in deps if dep not in self.cache)
        return self.cache[cell]

    def command(self, line):
        parts = line.split(' ')
        if len(parts) not in (2, 3) or not re.fullmatch(CELL, parts[1]):
            return 'ERR bad command'
        command, cell = parts[:2]
        if command == 'SET' and len(parts) == 3:
            try:
                terms, deps = parse(parts[2])
            except ValueError:
                return 'ERR bad command'
            if self.cyclic(cell, deps):
                return 'ERR cycle'
            self.cells[cell] = parts[2], terms, deps
            self.cache.clear()
            return 'OK'
        if len(parts) != 2:
            return 'ERR bad command'
        if command == 'CLEAR':
            self.cells.pop(cell, None)
            self.cache.clear()
            return 'OK'
        if command == 'SHOW':
            return self.cells[cell][0] if cell in self.cells else 'EMPTY'
        if command == 'GET':
            value = self.value(cell)
            return str(value) if value is not None else 'ERR overflow'
        return 'ERR bad command'


def main():
    if len(sys.argv) != 1:
        print('invalid arguments', file=sys.stderr)
        return 2
    sheet = Sheet()
    for raw in sys.stdin.buffer:
        line = raw.removesuffix(b'\n').removesuffix(b'\r').decode('ascii')
        print(sheet.command(line), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
