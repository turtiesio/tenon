import re
import sys

NUM = r"([0-9]{1,9})"
COMMAND_FORMS = [
    ("APPEND", re.compile(r"APPEND (.*)")),
    ("INSERT", re.compile(rf"INSERT {NUM} (.*)")),
    ("DELETE", re.compile(rf"DELETE {NUM}(?: {NUM})?")),
    ("REPLACE", re.compile(rf"REPLACE {NUM} (.*)")),
    ("PRINT", re.compile(rf"PRINT {NUM}")),
    ("FIND", re.compile(r"FIND (.+)")),
    ("COUNT", re.compile(r"COUNT")),
    ("UNDO", re.compile(r"UNDO")),
    ("REDO", re.compile(r"REDO")),
]
BAD_COMMAND = "ERR bad command"
BAD_LINE = "ERR bad line"


class Change:
    """Replacing lines[start:start+len(removed)] by `added`; reversible."""

    def __init__(self, start, removed, added):
        self.start = start
        self.removed = removed
        self.added = added

    def apply(self, lines):
        lines[self.start:self.start + len(self.removed)] = self.added

    def revert(self, lines):
        lines[self.start:self.start + len(self.added)] = self.removed


class Buffer:
    def __init__(self):
        self.lines = []
        self.undo = []
        self.redo = []

    def commit(self, change):
        change.apply(self.lines)
        self.undo.append(change)
        self.redo.clear()
        return f"OK {len(self.lines)}"

    def execute(self, line):
        for name, form in COMMAND_FORMS:
            match = form.fullmatch(line)
            if match:
                return getattr(self, "do_" + name.lower())(*match.groups())
        return BAD_COMMAND

    def do_append(self, text):
        return self.commit(Change(len(self.lines), [], [text]))

    def do_insert(self, n, text):
        n = int(n)
        if not 1 <= n <= len(self.lines) + 1:
            return BAD_LINE
        return self.commit(Change(n - 1, [], [text]))

    def do_delete(self, a, b):
        a = int(a)
        b = a if b is None else int(b)
        if not 1 <= a <= b <= len(self.lines):
            return BAD_LINE
        return self.commit(Change(a - 1, self.lines[a - 1:b], []))

    def do_replace(self, n, text):
        n = int(n)
        if not 1 <= n <= len(self.lines):
            return BAD_LINE
        return self.commit(Change(n - 1, [self.lines[n - 1]], [text]))

    def do_print(self, n):
        n = int(n)
        if not 1 <= n <= len(self.lines):
            return BAD_LINE
        return f"{n}|{self.lines[n - 1]}"

    def do_find(self, text):
        found = [str(i) for i, l in enumerate(self.lines, 1) if text in l]
        return " ".join(found) if found else "NONE"

    def do_count(self):
        return str(len(self.lines))

    def do_undo(self):
        if not self.undo:
            return "ERR nothing to undo"
        change = self.undo.pop()
        change.revert(self.lines)
        self.redo.append(change)
        return f"OK {len(self.lines)}"

    def do_redo(self):
        if not self.redo:
            return "ERR nothing to redo"
        change = self.redo.pop()
        change.apply(self.lines)
        self.undo.append(change)
        return f"OK {len(self.lines)}"


def main():
    if len(sys.argv) > 1:
        print("linebuf: takes no arguments", file=sys.stderr)
        return 2
    buffer = Buffer()
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
        stdout.write((buffer.execute(line) + "\n").encode("latin-1"))
        stdout.flush()
    return 0


sys.exit(main())
