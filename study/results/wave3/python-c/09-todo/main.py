"""todo: persistent to-do list with atomic snapshots."""
import os
import re
import sys
from dataclasses import dataclass

TEXT = r"[\x20-\x7e]+"
ADD = re.compile(rf"ADD ([1-9]) ({TEXT})")
ID_COMMAND = re.compile(r"(DONE|SHOW) ([0-9]{1,9})")
DB_NEXT = re.compile(r"next ([1-9][0-9]{0,8})")
DB_ITEM = re.compile(rf"([1-9][0-9]{{0,8}}) ([1-9]) ([od]) ({TEXT})")


class StateError(Exception):
    pass


class CommandError(Exception):
    """Raised with the exact error response text."""


@dataclass
class Item:
    id: int
    prio: int
    done: bool
    text: str

    def show(self):
        return f"{self.id} {self.prio} {'done' if self.done else 'open'} {self.text}"


class TodoStore:
    def __init__(self, directory):
        self.path = os.path.join(directory, "todo.db")
        self.tmp_path = self.path + ".tmp"
        self.items = {}  # id -> Item, in id order
        self.next_id = 1

    def load(self):
        try:
            os.remove(self.tmp_path)
        except FileNotFoundError:
            pass
        try:
            with open(self.path, "rb") as f:
                data = f.read()
        except FileNotFoundError:
            return
        self._parse(data.decode("latin-1"))

    def _parse(self, text):
        if not text.endswith("\n"):
            raise StateError("state file does not end with a newline")
        lines = text[:-1].split("\n")
        if lines[0] != "TODO 1":
            raise StateError("bad header line")
        if len(lines) < 2 or not (m := DB_NEXT.fullmatch(lines[1])):
            raise StateError("bad 'next' line")
        next_id = int(m.group(1))
        items = {}
        last_id = 0
        for number, line in enumerate(lines[2:], start=3):
            m = DB_ITEM.fullmatch(line)
            if not m:
                raise StateError(f"line {number}: bad item")
            item_id = int(m.group(1))
            if item_id <= last_id or item_id >= next_id:
                raise StateError(f"line {number}: id {item_id} out of order")
            items[item_id] = Item(item_id, int(m.group(2)), m.group(3) == "d", m.group(4))
            last_id = item_id
        self.items = items
        self.next_id = next_id

    def save(self):
        lines = ["TODO 1", f"next {self.next_id}"]
        lines += [
            f"{i.id} {i.prio} {'d' if i.done else 'o'} {i.text}" for i in self.items.values()
        ]
        with open(self.tmp_path, "w", encoding="ascii", newline="\n") as f:
            f.write("".join(line + "\n" for line in lines))
            f.flush()
            os.fsync(f.fileno())
        os.replace(self.tmp_path, self.path)

    def open_items(self):
        return sorted((i for i in self.items.values() if not i.done), key=lambda i: (i.prio, i.id))

    def get(self, item_id):
        item = self.items.get(item_id)
        if item is None:
            raise CommandError("ERR no such item")
        return item


def execute(store, line):
    if m := ADD.fullmatch(line):
        item = Item(store.next_id, int(m.group(1)), False, m.group(2))
        store.items[item.id] = item
        store.next_id += 1
        store.save()
        return f"ADDED {item.id}"
    if m := ID_COMMAND.fullmatch(line):
        item = store.get(int(m.group(2)))
        if m.group(1) == "SHOW":
            return item.show()
        if item.done:
            raise CommandError("ERR already done")
        item.done = True
        store.save()
        return "OK"
    if line == "LIST":
        return " ".join(["OPEN"] + [str(i.id) for i in store.open_items()])
    if line == "NEXT":
        open_items = store.open_items()
        return open_items[0].show() if open_items else "NONE"
    if line == "PURGE":
        done = [i.id for i in store.items.values() if i.done]
        for item_id in done:
            del store.items[item_id]
        if done:
            store.save()
        return f"PURGED {len(done)}"
    if line == "STATS":
        done = sum(1 for i in store.items.values() if i.done)
        return f"open={len(store.items) - done} done={done} next_id={store.next_id}"
    raise CommandError("ERR bad command")


def main():
    if len(sys.argv) != 2:
        print("usage: todo DIR", file=sys.stderr)
        return 2
    directory = sys.argv[1]
    try:
        if not os.path.exists(directory):
            os.mkdir(directory)
        if not os.path.isdir(directory):
            raise OSError(f"{directory} is not a directory")
        store = TodoStore(directory)
        store.load()
    except (OSError, StateError) as e:
        print(f"todo: {e}", file=sys.stderr)
        return 1

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
            response = execute(store, line)
        except CommandError as e:
            response = str(e)
        sys.stdout.write(response + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
