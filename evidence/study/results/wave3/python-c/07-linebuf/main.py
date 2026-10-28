"""linebuf: line-editor service with undo and redo."""
import re
import sys

NUM = r"([0-9]{1,9})"
COMMANDS = [
    ("APPEND", re.compile(r"APPEND (.*)", re.DOTALL)),
    ("INSERT", re.compile(rf"INSERT {NUM} (.*)", re.DOTALL)),
    ("DELETE", re.compile(rf"DELETE {NUM}(?: {NUM})?")),
    ("REPLACE", re.compile(rf"REPLACE {NUM} (.*)", re.DOTALL)),
    ("PRINT", re.compile(rf"PRINT {NUM}")),
    ("FIND", re.compile(r"FIND (.+)", re.DOTALL)),
    ("COUNT", re.compile(r"COUNT")),
    ("UNDO", re.compile(r"UNDO")),
    ("REDO", re.compile(r"REDO")),
]


class CommandError(Exception):
    """Raised with the exact error response text."""


class Buffer:
    def __init__(self):
        self.lines = []
        # A change is a splice (start, removed lines, inserted lines).
        self.undo_stack = []
        self.redo_stack = []

    def _splice(self, start, removed, inserted):
        self.lines[start:start + len(removed)] = inserted

    def change(self, start, end, inserted):
        """Replace lines[start:end] with `inserted` as one undoable change."""
        removed = self.lines[start:end]
        self._splice(start, removed, inserted)
        self.undo_stack.append((start, removed, inserted))
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            raise CommandError("ERR nothing to undo")
        start, removed, inserted = self.undo_stack.pop()
        self._splice(start, inserted, removed)
        self.redo_stack.append((start, removed, inserted))

    def redo(self):
        if not self.redo_stack:
            raise CommandError("ERR nothing to redo")
        start, removed, inserted = self.redo_stack.pop()
        self._splice(start, removed, inserted)
        self.undo_stack.append((start, removed, inserted))

    def check(self, n, high):
        if not 1 <= n <= high:
            raise CommandError("ERR bad line")


def execute(buf, line):
    for name, pattern in COMMANDS:
        m = pattern.fullmatch(line)
        if m:
            break
    else:
        raise CommandError("ERR bad command")
    args = m.groups()
    count = len(buf.lines)

    if name == "APPEND":
        buf.change(count, count, [args[0]])
    elif name == "INSERT":
        n = int(args[0])
        buf.check(n, count + 1)
        buf.change(n - 1, n - 1, [args[1]])
    elif name == "DELETE":
        a = int(args[0])
        b = int(args[1]) if args[1] is not None else a
        buf.check(a, count)
        buf.check(b, count)
        if a > b:
            raise CommandError("ERR bad line")
        buf.change(a - 1, b, [])
    elif name == "REPLACE":
        n = int(args[0])
        buf.check(n, count)
        buf.change(n - 1, n, [args[1]])
    elif name == "PRINT":
        n = int(args[0])
        buf.check(n, count)
        return f"{n}|{buf.lines[n - 1]}"
    elif name == "FIND":
        found = [str(k) for k, text in enumerate(buf.lines, start=1) if args[0] in text]
        return " ".join(found) if found else "NONE"
    elif name == "COUNT":
        return str(count)
    elif name == "UNDO":
        buf.undo()
    elif name == "REDO":
        buf.redo()
    return f"OK {len(buf.lines)}"


def main():
    if len(sys.argv) > 1:
        print("linebuf: no arguments expected", file=sys.stderr)
        return 2
    buf = Buffer()
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
            response = execute(buf, line)
        except CommandError as e:
            response = str(e)
        sys.stdout.write(response + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
