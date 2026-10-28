"""shorten: a persistent URL shortener backed by a numbered journal."""
import os
import re
import sys
from dataclasses import dataclass

URL = r"[!-~]{1,200}"
CODE = r"[0-9a-z]{1,8}"
COMMANDS = {
    "PUT": re.compile(rf"PUT ({URL})"),
    "GET": re.compile(rf"GET ({CODE})"),
    "HITS": re.compile(rf"HITS ({CODE})"),
    "DEL": re.compile(rf"DEL ({CODE})"),
    "INFO": re.compile(r"INFO()"),
}
RECORD_RE = re.compile(rf"([1-9][0-9]{{0,8}}) (?:P ({URL})|([HD]) ({CODE}))\n")
DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


def to_base36(n):
    out = ""
    while True:
        n, r = divmod(n, 36)
        out = DIGITS[r] + out
        if n == 0:
            return out


@dataclass
class Link:
    url: str
    hits: int = 0


class Store:
    def __init__(self):
        self.links = {}  # code -> Link
        self.next_id = 1
        self.records = 0

    # State transitions shared by replay and live commands.
    def apply_put(self, url):
        code = to_base36(self.next_id)
        self.links[code] = Link(url)
        self.next_id += 1
        return code

    def apply_hit(self, code):
        self.links[code].hits += 1

    def apply_del(self, code):
        del self.links[code]


def recover(path, store):
    """Replay the journal's valid prefix into `store`; return its length in bytes."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return 0
    valid_end = 0
    # Only "\n" ends a record; a final piece without it is torn and fails the match.
    for raw in data.split(b"\n"):
        raw += b"\n" if valid_end + len(raw) < len(data) else b""
        m = RECORD_RE.fullmatch(raw.decode("latin-1"))
        if not m or int(m.group(1)) != store.records + 1:
            break
        seq, url, kind, code = m.groups()
        if url is not None:
            store.apply_put(url)
        elif code not in store.links:
            break
        elif kind == "H":
            store.apply_hit(code)
        else:
            store.apply_del(code)
        store.records += 1
        valid_end += len(raw)
    return valid_end


class Service:
    def __init__(self, store, journal_fd):
        self.store = store
        self.fd = journal_fd

    def append(self, kind, arg):
        record = f"{self.store.records + 1} {kind} {arg}\n".encode("latin-1")
        written = 0
        while written < len(record):  # unbuffered: the OS has it once write returns
            written += os.write(self.fd, record[written:])
        self.store.records += 1

    def handle(self, line):
        name = line.partition(" ")[0]
        pattern = COMMANDS.get(name)
        m = pattern.fullmatch(line) if pattern else None
        if not m:
            return "ERR bad command"
        arg = m.group(1)
        links = self.store.links

        if name == "PUT":
            self.append("P", arg)
            return f"CODE {self.store.apply_put(arg)}"
        if name == "INFO":
            return f"links={len(links)} next={to_base36(self.store.next_id)} records={self.store.records}"
        if arg not in links:
            return "ERR not found"
        if name == "GET":
            self.append("H", arg)
            self.store.apply_hit(arg)
            return f"URL {links[arg].url}"
        if name == "HITS":
            return f"HITS {links[arg].hits}"
        # DEL
        self.append("D", arg)
        self.store.apply_del(arg)
        return "OK"


def main(argv):
    if len(argv) != 1:
        print("usage: shorten DIR", file=sys.stderr)
        return 2
    directory = argv[0]
    try:
        if not os.path.exists(directory):
            os.mkdir(directory)
        if not os.path.isdir(directory):
            raise NotADirectoryError(f"{directory} is not a directory")
        path = os.path.join(directory, "journal")
        store = Store()
        valid_end = recover(path, store)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT, 0o644)
        os.ftruncate(fd, valid_end)
        os.lseek(fd, valid_end, os.SEEK_SET)
    except OSError as e:
        print(f"shorten: cannot use {directory}: {e}", file=sys.stderr)
        return 1

    service = Service(store, fd)
    stdin = sys.stdin.buffer
    try:
        while True:
            raw = stdin.readline()
            if not raw:
                break
            line = raw.decode("latin-1").removesuffix("\n").removesuffix("\r")
            sys.stdout.write(service.handle(line) + "\n")
            sys.stdout.flush()
    finally:
        os.close(fd)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
