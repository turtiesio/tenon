import os
import re
import sys

NEXT_LINE = re.compile(r"next ([1-9][0-9]{0,8})")
ITEM_LINE = re.compile(r"([1-9][0-9]{0,8}) ([1-9]) ([od]) ([ -~]+)")
COMMANDS = [
    ("ADD", re.compile(r"ADD ([1-9]) ([ -~]+)")),
    ("DONE", re.compile(r"DONE ([0-9]{1,9})")),
    ("SHOW", re.compile(r"SHOW ([0-9]{1,9})")),
    ("LIST", re.compile(r"LIST")),
    ("NEXT", re.compile(r"NEXT")),
    ("PURGE", re.compile(r"PURGE")),
    ("STATS", re.compile(r"STATS")),
]
BAD_COMMAND = "ERR bad command"
NO_ITEM = "ERR no such item"


class StateError(Exception):
    pass


class Item:
    def __init__(self, ident, prio, done, text):
        self.ident = ident
        self.prio = prio
        self.done = done
        self.text = text

    def describe(self):
        status = "done" if self.done else "open"
        return f"{self.ident} {self.prio} {status} {self.text}"


def parse_state(data):
    """Parse the contents of todo.db into (next_id, {id: Item}); strict."""
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        raise StateError("not ASCII")
    if not text.endswith("\n"):
        raise StateError("missing final newline")
    lines = text[:-1].split("\n")
    if lines[0] != "TODO 1":
        raise StateError("bad header")
    m = NEXT_LINE.fullmatch(lines[1]) if len(lines) > 1 else None
    if not m:
        raise StateError("bad next line")
    next_id = int(m.group(1))
    items = {}
    last = 0
    for line in lines[2:]:
        m = ITEM_LINE.fullmatch(line)
        if not m:
            raise StateError(f"bad item line {line!r}")
        ident = int(m.group(1))
        if ident <= last or ident >= next_id:
            raise StateError(f"bad item id {ident}")
        last = ident
        items[ident] = Item(ident, int(m.group(2)), m.group(3) == "d", m.group(4))
    return next_id, items


class Store:
    def __init__(self, directory):
        self.path = os.path.join(directory, "todo.db")
        self.tmp_path = self.path + ".tmp"
        self.next_id = 1
        self.items = {}

    def load(self):
        try:
            with open(self.path, "rb") as f:
                data = f.read()
        except FileNotFoundError:
            return
        self.next_id, self.items = parse_state(data)

    def save(self):
        lines = ["TODO 1", f"next {self.next_id}"]
        lines += [f"{i.ident} {i.prio} {'d' if i.done else 'o'} {i.text}"
                  for i in self.items.values()]
        with open(self.tmp_path, "w", encoding="ascii", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(self.tmp_path, self.path)

    def open_items(self):
        return sorted((i for i in self.items.values() if not i.done),
                      key=lambda i: (i.prio, i.ident))

    def execute(self, line):
        for name, form in COMMANDS:
            m = form.fullmatch(line)
            if m:
                return getattr(self, "do_" + name.lower())(*m.groups())
        return BAD_COMMAND

    def do_add(self, prio, text):
        ident = self.next_id
        self.items[ident] = Item(ident, int(prio), False, text)
        self.next_id += 1
        self.save()
        return f"ADDED {ident}"

    def do_done(self, ident):
        item = self.items.get(int(ident))
        if item is None:
            return NO_ITEM
        if item.done:
            return "ERR already done"
        item.done = True
        self.save()
        return "OK"

    def do_show(self, ident):
        item = self.items.get(int(ident))
        return NO_ITEM if item is None else item.describe()

    def do_list(self):
        return " ".join(["OPEN"] + [str(i.ident) for i in self.open_items()])

    def do_next(self):
        open_items = self.open_items()
        return open_items[0].describe() if open_items else "NONE"

    def do_purge(self):
        done = [ident for ident, i in self.items.items() if i.done]
        for ident in done:
            del self.items[ident]
        if done:
            self.save()
        return f"PURGED {len(done)}"

    def do_stats(self):
        done = sum(1 for i in self.items.values() if i.done)
        return f"open={len(self.items) - done} done={done} next_id={self.next_id}"


def prepare(directory):
    """Create the data directory, drop a leftover temp file, load the state."""
    if not os.path.exists(directory):
        os.mkdir(directory)
    if not os.path.isdir(directory):
        raise OSError(f"{directory} is not a directory")
    store = Store(directory)
    try:
        os.remove(store.tmp_path)
    except FileNotFoundError:
        pass
    store.load()
    return store


def main():
    if len(sys.argv) != 2:
        print("usage: todo DIR", file=sys.stderr)
        return 2
    try:
        store = prepare(sys.argv[1])
    except (OSError, StateError) as e:
        print(f"todo: {e}", file=sys.stderr)
        return 1

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
        stdout.write((store.execute(line) + "\n").encode("latin-1"))
        stdout.flush()
    return 0


sys.exit(main())
