import re
import sys

LIMIT = 10**12
CELL = r"[A-Z][1-9][0-9]?"
CELL_RE = re.compile(CELL)
INT_RE = re.compile(r"-?[0-9]{1,9}")
TERM_RE = re.compile(rf"([0-9]{{1,9}})|({CELL})|SUM\(({CELL}):({CELL})\)")
BAD_COMMAND = "ERR bad command"


class Formula:
    """Signed terms; each term is a list of cell names (numbers have none)."""

    def __init__(self, signed_terms):
        # signed_terms: list of (sign, constant, cells)
        self.signed_terms = signed_terms
        self.refs = {c for _, _, cells in signed_terms for c in cells}


def rectangle(a, b):
    cols = sorted((a[0], b[0]))
    rows = sorted((int(a[1:]), int(b[1:])))
    return [f"{chr(c)}{r}"
            for c in range(ord(cols[0]), ord(cols[1]) + 1)
            for r in range(rows[0], rows[1] + 1)]


def parse_formula(text):
    """Parse '=...' into a Formula, or return None if it is not valid."""
    if not text.startswith("="):
        return None
    pos = 1
    sign = 1
    if text.startswith("-", pos):
        sign = -1
        pos += 1
    terms = []
    while True:
        m = TERM_RE.match(text, pos)
        if not m:
            return None
        number, cell, corner1, corner2 = m.groups()
        if number is not None:
            terms.append((sign, int(number), []))
        elif cell is not None:
            terms.append((sign, 0, [cell]))
        else:
            terms.append((sign, 0, rectangle(corner1, corner2)))
        pos = m.end()
        if pos == len(text):
            return Formula(terms)
        if text[pos] not in "+-":
            return None
        sign = 1 if text[pos] == "+" else -1
        pos += 1


class Sheet:
    def __init__(self):
        self.text = {}      # cell -> contents as given
        self.formulas = {}  # cell -> Formula (formula cells only)
        self.literals = {}  # cell -> int (literal cells only)
        self.cache = {}     # cell -> int, or None for overflow

    def depends_on(self, start_cells, target):
        """True if target is reachable from start_cells through stored formulas."""
        seen = set()
        stack = list(start_cells)
        while stack:
            c = stack.pop()
            if c == target:
                return True
            if c in seen:
                continue
            seen.add(c)
            f = self.formulas.get(c)
            if f:
                stack.extend(f.refs)
        return False

    def set(self, cell, contents):
        if INT_RE.fullmatch(contents):
            formula, literal = None, int(contents)
        else:
            formula = parse_formula(contents)
            if formula is None:
                return BAD_COMMAND
            literal = None
            if self.depends_on(formula.refs, cell):
                return "ERR cycle"
        self.clear(cell)
        self.text[cell] = contents
        if formula is not None:
            self.formulas[cell] = formula
        else:
            self.literals[cell] = literal
        return "OK"

    def clear(self, cell):
        self.text.pop(cell, None)
        self.formulas.pop(cell, None)
        self.literals.pop(cell, None)
        self.cache.clear()

    def compute(self, cell):
        f = self.formulas.get(cell)
        if f is None:
            return self.literals.get(cell, 0)
        total = 0
        for sign, constant, cells in f.signed_terms:
            part = constant
            for c in cells:
                v = self.cache[c]
                if v is None:
                    return None
                part += v
            total += sign * part
        # a referenced overflow cell anywhere makes this one overflow
        return None if abs(total) > LIMIT else total

    def value(self, cell):
        """Value of cell, or None on overflow. Iterative to survive long chains."""
        stack = [cell]
        while stack:
            c = stack[-1]
            if c in self.cache:
                stack.pop()
                continue
            f = self.formulas.get(c)
            pending = [r for r in f.refs if r not in self.cache] if f else []
            if pending:
                stack.extend(pending)
                continue
            self.cache[c] = self.compute(c)
            stack.pop()
        return self.cache[cell]

    def execute(self, line):
        tokens = line.split(" ")
        command = tokens[0]
        if command == "SET" and len(tokens) == 3 and CELL_RE.fullmatch(tokens[1]):
            return self.set(tokens[1], tokens[2])
        if len(tokens) == 2 and CELL_RE.fullmatch(tokens[1]):
            cell = tokens[1]
            if command == "CLEAR":
                self.clear(cell)
                return "OK"
            if command == "GET":
                v = self.value(cell)
                return "ERR overflow" if v is None else str(v)
            if command == "SHOW":
                return self.text.get(cell, "EMPTY")
        return BAD_COMMAND


def main():
    if len(sys.argv) > 1:
        print("sheet: takes no arguments", file=sys.stderr)
        return 2
    sheet = Sheet()
    stdin, stdout = sys.stdin.buffer, sys.stdout.buffer
    while True:
        raw = stdin.readline()
        if not raw:
            break
        line = raw.decode("latin-1")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        stdout.write((sheet.execute(line) + "\n").encode("latin-1"))
        stdout.flush()
    return 0


sys.exit(main())
