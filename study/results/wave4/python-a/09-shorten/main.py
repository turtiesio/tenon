import os
import re
import sys

URL_RE = re.compile(r"[!-~]{1,200}")
CODE_RE = re.compile(r"[0-9a-z]{1,8}")
RECORD_RE = re.compile(r"([1-9][0-9]{0,8}) (?:(P) ([!-~]{1,200})|([HD]) ([0-9a-z]{1,8}))")
DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


def to_code(link_id):
    digits = []
    while link_id:
        link_id, rem = divmod(link_id, 36)
        digits.append(DIGITS[rem])
    return "".join(reversed(digits)) or "0"


class Store:
    """In-memory state: links keyed by code, plus counters for the journal."""

    def __init__(self):
        self.links = {}  # code -> [url, hits]
        self.next_id = 1
        self.records = 0

    def put(self, url):
        code = to_code(self.next_id)
        self.next_id += 1
        self.links[code] = [url, 0]
        self.records += 1
        return code

    def hit(self, code):
        self.links[code][1] += 1
        self.records += 1

    def delete(self, code):
        del self.links[code]
        self.records += 1


def load_journal(path, store):
    """Replay the longest valid prefix of the journal into `store`.

    Returns the byte length of that prefix.
    """
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return 0

    valid_bytes = 0
    # The last piece is either empty or a torn line without "\n"; drop it.
    for raw in data.split(b"\n")[:-1]:
        m = RECORD_RE.fullmatch(raw.decode("latin-1"))
        if not m or int(m.group(1)) != store.records + 1:
            break
        if m.group(2):
            store.put(m.group(3))
        else:
            kind, code = m.group(4), m.group(5)
            if code not in store.links:
                break
            if kind == "H":
                store.hit(code)
            else:
                store.delete(code)
        valid_bytes += len(raw) + 1
    return valid_bytes


def open_data_dir(path):
    try:
        if not os.path.isdir(path):
            if os.path.lexists(path):
                raise NotADirectoryError(path)
            os.mkdir(path)
    except OSError as e:
        print(f"shorten: cannot use data directory {path}: {e}", file=sys.stderr)
        sys.exit(1)


class Shortener:
    def __init__(self, store, journal):
        self.store = store
        self.journal = journal

    def append(self, body):
        self.journal.write(f"{self.store.records + 1} {body}\n".encode("latin-1"))
        self.journal.flush()

    def handle(self, line):
        tokens = line.split(" ")
        cmd, args = tokens[0], tokens[1:]
        if cmd == "PUT" and len(args) == 1 and URL_RE.fullmatch(args[0]):
            self.append(f"P {args[0]}")
            return f"CODE {self.store.put(args[0])}"
        if cmd in ("GET", "HITS", "DEL") and len(args) == 1 and CODE_RE.fullmatch(args[0]):
            return self.by_code(cmd, args[0])
        if cmd == "INFO" and not args:
            s = self.store
            return f"links={len(s.links)} next={to_code(s.next_id)} records={s.records}"
        return "ERR bad command"

    def by_code(self, cmd, code):
        link = self.store.links.get(code)
        if link is None:
            return "ERR not found"
        if cmd == "HITS":
            return f"HITS {link[1]}"
        if cmd == "GET":
            self.append(f"H {code}")
            self.store.hit(code)
            return f"URL {link[0]}"
        self.append(f"D {code}")
        self.store.delete(code)
        return "OK"


def main():
    if len(sys.argv) != 2:
        print("usage: shorten DIR", file=sys.stderr)
        sys.exit(2)
    directory = sys.argv[1]
    open_data_dir(directory)

    journal_path = os.path.join(directory, "journal")
    store = Store()
    try:
        valid_bytes = load_journal(journal_path, store)
        journal = open(journal_path, "ab")
        journal.truncate(valid_bytes)
    except OSError as e:
        print(f"shorten: cannot open journal: {e}", file=sys.stderr)
        sys.exit(1)

    service = Shortener(store, journal)
    with journal:
        for raw in sys.stdin.buffer:
            line = raw.decode("latin-1")
            if line.endswith("\n"):
                line = line[:-1]
            if line.endswith("\r"):
                line = line[:-1]
            sys.stdout.write(service.handle(line) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
