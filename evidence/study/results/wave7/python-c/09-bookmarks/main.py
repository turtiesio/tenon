"""bookmarks: persistent tagged bookmarks with a journal and snapshots."""
import os
import re
import sys

NAME = re.compile(r"[a-z0-9-]{1,20}")
URL = re.compile(r"[!-~]{1,200}")
TAG = re.compile(r"[a-z0-9]{1,12}")
NUMBER = r"(0|[1-9][0-9]*)"
SNAPSHOT_HEADER = re.compile(rf"bookmarks {NUMBER}")
RECORD = re.compile(r"([1-9][0-9]*) (.*)")

# command -> validators for its arguments
COMMANDS = {
    "ADD": (NAME, URL),
    "DEL": (NAME,),
    "TAG": (NAME, TAG),
    "UNTAG": (NAME, TAG),
    "GET": (NAME,),
    "FIND": (TAG,),
    "COMPACT": (),
}
MUTATING = {"ADD", "DEL", "TAG", "UNTAG"}


class DataError(Exception):
    pass


def parse_command(line):
    """Return (command, args) for a well-formed line, else None."""
    tokens = line.split(" ")
    validators = COMMANDS.get(tokens[0])
    if validators is None or len(tokens) - 1 != len(validators):
        return None
    args = tokens[1:]
    if not all(v.fullmatch(a) for v, a in zip(validators, args)):
        return None
    return tokens[0], args


def format_tags(tags):
    return ",".join(sorted(tags)) if tags else "-"


class Bookmarks:
    """The in-memory state: name -> (url, set of tags)."""

    def __init__(self):
        self.items = {}

    def apply(self, command, args):
        """Apply a mutating command; return its response. Only 'OK' changes state."""
        name = args[0]
        if command == "ADD":
            if name in self.items:
                return "ERR exists"
            self.items[name] = (args[1], set())
            return "OK"
        if name not in self.items:
            return "ERR no such bookmark"
        tags = self.items[name][1]
        if command == "DEL":
            del self.items[name]
            return "OK"
        tag = args[1]
        if command == "TAG":
            if tag in tags:
                return "UNCHANGED"
            tags.add(tag)
            return "OK"
        if tag not in tags:
            return "UNCHANGED"
        tags.remove(tag)
        return "OK"

    def get(self, name):
        if name not in self.items:
            return "ERR no such bookmark"
        url, tags = self.items[name]
        return f"{name} {url} {format_tags(tags)}"

    def find(self, tag):
        names = sorted(n for n, (_, tags) in self.items.items() if tag in tags)
        return " ".join(names) if names else "-"

    def snapshot_text(self, seq):
        lines = [f"bookmarks {seq}"]
        for name in sorted(self.items):
            url, tags = self.items[name]
            lines.append(f"{name} {url} {format_tags(tags)}")
        return "".join(line + "\n" for line in lines)


def read_bytes(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None


def load_snapshot(path, state):
    """Load the snapshot into state and return S (0 if there is none)."""
    data = read_bytes(path)
    if data is None:
        return 0
    text = data.decode("latin-1")
    if not text.endswith("\n"):
        raise DataError("snapshot does not end with a newline")
    lines = text[:-1].split("\n")
    header = SNAPSHOT_HEADER.fullmatch(lines[0])
    if not header:
        raise DataError("bad snapshot header")
    previous = None
    for line in lines[1:]:
        parts = line.split(" ")
        if len(parts) != 3 or not NAME.fullmatch(parts[0]) or not URL.fullmatch(parts[1]):
            raise DataError(f"bad snapshot line: {line!r}")
        name, url, tag_field = parts
        if previous is not None and name.encode() <= previous.encode():
            raise DataError("snapshot names are not strictly increasing")
        previous = name
        tags = [] if tag_field == "-" else tag_field.split(",")
        if not all(TAG.fullmatch(t) for t in tags):
            raise DataError(f"bad tags in snapshot: {line!r}")
        if any(a >= b for a, b in zip(tags, tags[1:])):
            raise DataError("snapshot tags are not strictly increasing")
        state.items[name] = (url, set(tags))
    return int(header.group(1))


def load_journal(path, state, snapshot_seq):
    """Replay the journal. Return (L, length of the complete part in bytes)."""
    data = read_bytes(path) or b""
    complete_length = data.rfind(b"\n") + 1
    text = data[:complete_length].decode("latin-1")
    records = []
    for line in text.split("\n")[:-1]:
        m = RECORD.fullmatch(line)
        parsed = parse_command(m.group(2)) if m else None
        if parsed is None or parsed[0] not in MUTATING:
            raise DataError(f"bad journal record: {line!r}")
        records.append((int(m.group(1)), parsed))
    if not records:
        return snapshot_seq, complete_length
    seqs = [seq for seq, _ in records]
    if any(b != a + 1 for a, b in zip(seqs, seqs[1:])):
        raise DataError("journal sequence numbers are not consecutive")
    if seqs[0] > snapshot_seq + 1 or seqs[-1] < snapshot_seq:
        raise DataError("journal does not continue the snapshot")
    for seq, (command, args) in records:
        if seq <= snapshot_seq:
            continue
        if state.apply(command, args) != "OK":
            raise DataError(f"journal record {seq} does not apply")
    return max(snapshot_seq, seqs[-1]), complete_length


class Store:
    def __init__(self, directory):
        self.snapshot_path = os.path.join(directory, "snapshot")
        self.tmp_path = os.path.join(directory, "snapshot.tmp")
        self.journal_path = os.path.join(directory, "journal")
        self.state = Bookmarks()
        snapshot_seq = load_snapshot(self.snapshot_path, self.state)
        self.last_seq, complete_length = load_journal(self.journal_path, self.state, snapshot_seq)
        # Startup succeeded: now it is safe to touch the files.
        if os.path.exists(self.tmp_path):
            os.remove(self.tmp_path)
        self.journal = open(self.journal_path, "ab")
        self.journal.truncate(complete_length)

    def record(self, line):
        self.journal.write(f"{self.last_seq + 1} {line}\n".encode("latin-1"))
        self.journal.flush()
        self.last_seq += 1

    def compact(self):
        with open(self.tmp_path, "wb") as f:
            f.write(self.state.snapshot_text(self.last_seq).encode("latin-1"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(self.tmp_path, self.snapshot_path)
        self.journal.truncate(0)
        return f"OK {self.last_seq}"

    def handle(self, line):
        parsed = parse_command(line)
        if parsed is None:
            return "ERR bad command"
        command, args = parsed
        if command == "GET":
            return self.state.get(args[0])
        if command == "FIND":
            return self.state.find(args[0])
        if command == "COMPACT":
            return self.compact()
        response = self.state.apply(command, args)
        if response == "OK":
            self.record(line)
        return response


def open_directory(directory):
    if not os.path.exists(directory):
        os.mkdir(directory)
    if not os.path.isdir(directory):
        raise DataError(f"{directory} is not a directory")


def main(argv):
    if len(argv) != 1:
        print("usage: bookmarks DIR", file=sys.stderr)
        return 2
    try:
        open_directory(argv[0])
        store = Store(argv[0])
    except (DataError, OSError) as e:
        print(f"bookmarks: {e}", file=sys.stderr)
        return 1

    for raw in sys.stdin.buffer:
        line = raw.decode("latin-1")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        sys.stdout.write(store.handle(line) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
