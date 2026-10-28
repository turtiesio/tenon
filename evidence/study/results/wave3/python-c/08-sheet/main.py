"""sheet: spreadsheet cell service with formulas."""
import re
import sys
from collections import defaultdict

CELL = r"[A-Z][1-9][0-9]?"
CELL_NAME = re.compile(CELL)
LITERAL = re.compile(r"-?[0-9]{1,9}")
TERM = re.compile(rf"([0-9]{{1,9}})|({CELL})|SUM\(({CELL}):({CELL})\)")
LIMIT = 10**12


class CommandError(Exception):
    """Raised with the exact error response text."""


def cell_range(a, b):
    col_a, row_a = ord(a[0]), int(a[1:])
    col_b, row_b = ord(b[0]), int(b[1:])
    return [
        f"{chr(col)}{row}"
        for col in range(min(col_a, col_b), max(col_a, col_b) + 1)
        for row in range(min(row_a, row_b), max(row_a, row_b) + 1)
    ]


def parse_contents(text):
    """Parse cell contents into a list of (sign, kind, payload) terms.

    kind is "num" (payload: int), "cell" (payload: name) or "sum"
    (payload: list of names)."""
    if LITERAL.fullmatch(text):
        return [(1, "num", int(text))]
    if not text.startswith("="):
        raise CommandError("ERR bad command")
    terms = []
    pos = 1
    sign = 1
    if text.startswith("-", pos):
        sign = -1
        pos += 1
    while True:
        m = TERM.match(text, pos)
        if not m:
            raise CommandError("ERR bad command")
        number, cell, first, last = m.groups()
        if number is not None:
            terms.append((sign, "num", int(number)))
        elif cell is not None:
            terms.append((sign, "cell", cell))
        else:
            terms.append((sign, "sum", cell_range(first, last)))
        pos = m.end()
        if pos == len(text):
            return terms
        if text[pos] not in "+-":
            raise CommandError("ERR bad command")
        sign = 1 if text[pos] == "+" else -1
        pos += 1


def references(terms):
    refs = set()
    for _, kind, payload in terms:
        if kind == "cell":
            refs.add(payload)
        elif kind == "sum":
            refs.update(payload)
    return refs


class Sheet:
    def __init__(self):
        self.contents = {}  # cell -> text as given
        self.terms = {}  # cell -> parsed terms
        self.refs = {}  # cell -> set of referenced cells
        self.dependents = defaultdict(set)  # cell -> cells referencing it
        self.cache = {}  # cell -> value, or None for overflow

    def dependents_closure(self, cell):
        """The cell plus every cell that depends on it, directly or not."""
        seen = {cell}
        stack = [cell]
        while stack:
            for dep in self.dependents[stack.pop()]:
                if dep not in seen:
                    seen.add(dep)
                    stack.append(dep)
        return seen

    def _store(self, cell, text, terms, affected=None):
        for ref in self.refs.pop(cell, ()):
            self.dependents[ref].discard(cell)
        if affected is None:
            affected = self.dependents_closure(cell)
        for stale in affected:
            self.cache.pop(stale, None)
        if text is None:
            self.contents.pop(cell, None)
            self.terms.pop(cell, None)
            return
        refs = references(terms)
        self.contents[cell] = text
        self.terms[cell] = terms
        self.refs[cell] = refs
        for ref in refs:
            self.dependents[ref].add(cell)

    def set(self, cell, text):
        terms = parse_contents(text)
        refs = references(terms)
        affected = self.dependents_closure(cell)
        if not refs.isdisjoint(affected):
            raise CommandError("ERR cycle")
        self._store(cell, text, terms, affected)

    def clear(self, cell):
        self._store(cell, None, None)

    def value(self, cell):
        """The cell's value, or None if it is overflow."""
        if cell in self.cache:
            return self.cache[cell]
        # Evaluate dependencies first, without deep recursion.
        stack = [cell]
        expanded = set()
        while stack:
            current = stack[-1]
            if current in self.cache:
                stack.pop()
            elif current in expanded:
                # All its references were evaluated above it on the stack.
                stack.pop()
                self.cache[current] = self._compute(current)
            else:
                expanded.add(current)
                stack.extend(r for r in self.refs.get(current, ()) if r not in self.cache)
        return self.cache[cell]

    def _compute(self, cell):
        total = 0
        for sign, kind, payload in self.terms.get(cell, ()):
            if kind == "num":
                term = payload
            else:
                cells = [payload] if kind == "cell" else payload
                values = [self.cache[c] for c in cells]
                if None in values:
                    return None
                term = sum(values)
            total += sign * term
        return None if abs(total) > LIMIT else total


def execute(sheet, line):
    tokens = line.split(" ")
    command, args = tokens[0], tokens[1:]
    arity = {"SET": 2, "CLEAR": 1, "GET": 1, "SHOW": 1}
    if arity.get(command) != len(args) or not CELL_NAME.fullmatch(args[0]):
        raise CommandError("ERR bad command")
    cell = args[0]
    if command == "SET":
        sheet.set(cell, args[1])
        return "OK"
    if command == "CLEAR":
        sheet.clear(cell)
        return "OK"
    if command == "GET":
        value = sheet.value(cell)
        if value is None:
            raise CommandError("ERR overflow")
        return str(value)
    return sheet.contents.get(cell, "EMPTY")


def main():
    if len(sys.argv) > 1:
        print("sheet: no arguments expected", file=sys.stderr)
        return 2
    sheet = Sheet()
    stdin = sys.stdin.buffer
    while True:
        raw = stdin.readline()
        if not raw:
            break
        line = raw.decode("latin-1")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        try:
            response = execute(sheet, line)
        except CommandError as e:
            response = str(e)
        sys.stdout.write(response + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
