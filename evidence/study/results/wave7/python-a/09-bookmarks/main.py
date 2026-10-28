import os
import re
import sys

NAME_RE = re.compile(r"[a-z0-9-]{1,20}")
URL_RE = re.compile(r"[!-~]{1,200}")
TAG_RE = re.compile(r"[a-z0-9]{1,12}")
NUMBER_RE = re.compile(r"0|[1-9][0-9]*")
SEQ_RE = re.compile(r"[1-9][0-9]*")

BAD = "ERR bad command"
NO_SUCH = "ERR no such bookmark"
MUTATING = ("ADD", "DEL", "TAG", "UNTAG")


class DataError(Exception):
    """The data directory holds invalid data."""


def parse_command(line):
    """Return (command, args) if `line` is a well-formed command, else None."""
    tokens = line.split(" ")
    command, args = tokens[0], tokens[1:]
    shapes = {
        "ADD": (NAME_RE, URL_RE),
        "DEL": (NAME_RE,),
        "TAG": (NAME_RE, TAG_RE),
        "UNTAG": (NAME_RE, TAG_RE),
        "GET": (NAME_RE,),
        "FIND": (TAG_RE,),
        "COMPACT": (),
    }
    shape = shapes.get(command)
    if shape is None or len(args) != len(shape):
        return None
    if not all(rx.fullmatch(arg) for rx, arg in zip(shape, args)):
        return None
    return command, args


def format_tags(tags):
    return ",".join(sorted(tags)) if tags else "-"


class Store:
    def __init__(self):
        self.bookmarks = {}  # name -> [url, set of tags]

    def apply(self, command, args):
        """Run a non-COMPACT command and return its response."""
        bm = self.bookmarks
        if command == "ADD":
            name, url = args
            if name in bm:
                return "ERR exists"
            bm[name] = [url, set()]
            return "OK"
        if command == "FIND":
            names = sorted(n for n, (_, tags) in bm.items() if args[0] in tags)
            return " ".join(names) if names else "-"
        name = args[0]
        if name not in bm:
            return NO_SUCH
        url, tags = bm[name]
        if command == "DEL":
            del bm[name]
            return "OK"
        if command == "GET":
            return f"{name} {url} {format_tags(tags)}"
        tag = args[1]
        if command == "TAG":
            if tag in tags:
                return "UNCHANGED"
            tags.add(tag)
            return "OK"
        # UNTAG
        if tag not in tags:
            return "UNCHANGED"
        tags.remove(tag)
        return "OK"

    def snapshot_text(self, seq):
        lines = [f"bookmarks {seq}"]
        for name in sorted(self.bookmarks):
            url, tags = self.bookmarks[name]
            lines.append(f"{name} {url} {format_tags(tags)}")
        return "".join(line + "\n" for line in lines)


def decode_ascii(data, what):
    try:
        return data.decode("ascii")
    except UnicodeDecodeError:
        raise DataError(f"{what} is not ASCII") from None


def load_snapshot(path, store):
    """Load the snapshot into `store`; return its sequence number S."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return 0
    text = decode_ascii(data, "snapshot")
    if not text.endswith("\n"):
        raise DataError("snapshot does not end with a newline")
    lines = text[:-1].split("\n")
    header = lines[0].split(" ")
    if len(header) != 2 or header[0] != "bookmarks" or not NUMBER_RE.fullmatch(header[1]):
        raise DataError("bad snapshot header")

    previous = None
    for line in lines[1:]:
        parts = line.split(" ")
        if len(parts) != 3:
            raise DataError(f"bad snapshot line: {line!r}")
        name, url, tag_text = parts
        if not NAME_RE.fullmatch(name) or not URL_RE.fullmatch(url):
            raise DataError(f"bad snapshot line: {line!r}")
        if previous is not None and name <= previous:
            raise DataError("snapshot names are not strictly increasing")
        previous = name
        tags = set()
        if tag_text != "-":
            tag_list = tag_text.split(",")
            if not all(TAG_RE.fullmatch(t) for t in tag_list):
                raise DataError(f"bad tags in snapshot: {tag_text!r}")
            if any(a >= b for a, b in zip(tag_list, tag_list[1:])):
                raise DataError("snapshot tags are not strictly increasing")
            tags = set(tag_list)
        store.bookmarks[name] = [url, tags]
    return int(header[1])


def load_journal(path, store, snapshot_seq):
    """Replay the journal; return (last sequence number L, valid byte length)."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return snapshot_seq, 0
    valid_length = data.rfind(b"\n") + 1  # drops a torn last record
    text = decode_ascii(data[:valid_length], "journal")
    lines = text[:-1].split("\n") if text else []

    records = []
    for line in lines:
        seq_text, sep, command_line = line.partition(" ")
        parsed = parse_command(command_line) if sep else None
        if not SEQ_RE.fullmatch(seq_text) or parsed is None or parsed[0] not in MUTATING:
            raise DataError(f"bad journal record: {line!r}")
        records.append((int(seq_text), parsed))

    for (a, _), (b, _) in zip(records, records[1:]):
        if b != a + 1:
            raise DataError("journal sequence numbers are not consecutive")
    if records and (records[0][0] > snapshot_seq + 1 or records[-1][0] < snapshot_seq):
        raise DataError("journal does not continue the snapshot")

    for seq, (command, args) in records:
        if seq > snapshot_seq and store.apply(command, args) != "OK":
            raise DataError(f"journal record {seq} does not apply")

    last = records[-1][0] if records else snapshot_seq
    return max(snapshot_seq, last), valid_length


class Journal:
    def __init__(self, path, last_seq):
        self.path = path
        self.last_seq = last_seq
        self.fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)

    def append(self, command_line):
        record = f"{self.last_seq + 1} {command_line}\n".encode("ascii")
        os.write(self.fd, record)
        self.last_seq += 1

    def empty(self):
        os.ftruncate(self.fd, 0)


def compact(directory, store, journal):
    tmp = os.path.join(directory, "snapshot.tmp")
    with open(tmp, "wb") as f:
        f.write(store.snapshot_text(journal.last_seq).encode("ascii"))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, os.path.join(directory, "snapshot"))
    journal.empty()
    return f"OK {journal.last_seq}"


def prepare_directory(directory):
    if not os.path.exists(directory):
        os.mkdir(directory)
    elif not os.path.isdir(directory):
        raise OSError(f"{directory} is not a directory")


def main():
    if len(sys.argv) != 2:
        print("usage: bookmarks DIR", file=sys.stderr)
        return 2
    directory = sys.argv[1]

    try:
        prepare_directory(directory)
        store = Store()
        snapshot_seq = load_snapshot(os.path.join(directory, "snapshot"), store)
        journal_path = os.path.join(directory, "journal")
        last_seq, valid_length = load_journal(journal_path, store, snapshot_seq)
        if os.path.exists(journal_path) and os.path.getsize(journal_path) != valid_length:
            os.truncate(journal_path, valid_length)
        tmp = os.path.join(directory, "snapshot.tmp")
        if os.path.exists(tmp):
            os.remove(tmp)
        journal = Journal(journal_path, last_seq)
    except (OSError, DataError) as e:
        print(f"bookmarks: {e}", file=sys.stderr)
        return 1

    for raw in sys.stdin.buffer:
        line = raw.decode("ascii", errors="replace")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        parsed = parse_command(line)
        if parsed is None:
            response = BAD
        elif parsed[0] == "COMPACT":
            response = compact(directory, store, journal)
        else:
            response = store.apply(*parsed)
            if parsed[0] in MUTATING and response == "OK":
                journal.append(line)
        sys.stdout.write(response + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
