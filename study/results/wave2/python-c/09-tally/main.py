"""tally: persistent named counters backed by a write-ahead log."""
import os
import re
import sys

NAME = r"[a-z][a-z0-9_]{0,31}"
INT = r"-?[0-9]{1,15}"
NAME_RE = re.compile(NAME)
INT_RE = re.compile(INT)
# Log values may legitimately exceed 15 digits after ADDs (values reach
# +-10^17), and COMPACT writes them back as S records, so replay accepts more.
RECORD_RE = re.compile(rf"(?:([SA]) ({NAME}) (-?[0-9]{{1,18}})|(D) ({NAME}))\n")
LOG_NAME = "tally.log"
TMP_NAME = "tally.log.tmp"


class BadCommand(Exception):
    pass


class Store:
    def __init__(self, directory):
        self.log_path = os.path.join(directory, LOG_NAME)
        self.tmp_path = os.path.join(directory, TMP_NAME)
        self.counters = {}
        self.records = 0
        self.log_fd = None

    def recover(self):
        try:
            os.remove(self.tmp_path)
        except FileNotFoundError:
            pass
        try:
            with open(self.log_path, "rb") as f:
                data = f.read().decode("latin-1")
        except FileNotFoundError:
            data = ""

        pos = 0
        while True:
            m = RECORD_RE.match(data, pos)
            if not m:
                break
            if m.group(4):
                self.counters.pop(m.group(5), None)
            else:
                op, name, value = m.group(1), m.group(2), int(m.group(3))
                if op == "S":
                    self.counters[name] = value
                else:
                    self.counters[name] = self.counters.get(name, 0) + value
            self.records += 1
            pos = m.end()

        # Drop anything after the valid prefix before appending to the log.
        self.log_fd = os.open(self.log_path, os.O_WRONLY | os.O_CREAT, 0o644)
        os.ftruncate(self.log_fd, len(data[:pos].encode("latin-1")))
        os.lseek(self.log_fd, 0, os.SEEK_END)

    def append(self, record):
        data = (record + "\n").encode("latin-1")
        while data:
            written = os.write(self.log_fd, data)
            data = data[written:]
        self.records += 1

    def compact(self):
        names = sorted(self.counters)
        with open(self.tmp_path, "wb") as f:
            f.write("".join(f"S {n} {self.counters[n]}\n" for n in names).encode("latin-1"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(self.tmp_path, self.log_path)
        os.close(self.log_fd)
        self.log_fd = os.open(self.log_path, os.O_WRONLY | os.O_APPEND)
        self.records = len(names)
        return f"OK {self.records}"

    def handle(self, line):
        try:
            return self.dispatch(line.split(" "))
        except BadCommand:
            return "ERR bad command"

    def dispatch(self, tokens):
        command, args = tokens[0], tokens[1:]
        if command in ("SET", "ADD") and len(args) == 2:
            name, value = parse_name(args[0]), parse_int(args[1])
            if command == "SET":
                self.append(f"S {name} {value}")
                self.counters[name] = value
                return "OK"
            self.append(f"A {name} {value}")
            self.counters[name] = self.counters.get(name, 0) + value
            return str(self.counters[name])
        if command == "GET" and len(args) == 1:
            value = self.counters.get(parse_name(args[0]))
            return "NONE" if value is None else str(value)
        if command == "DEL" and len(args) == 1:
            name = parse_name(args[0])
            if name not in self.counters:
                return "NONE"
            self.append(f"D {name}")
            del self.counters[name]
            return "OK"
        if command == "LIST" and not args:
            items = "".join(f" {n}={self.counters[n]}" for n in sorted(self.counters))
            return f"{len(self.counters)}{items}"
        if command == "INFO" and not args:
            return f"counters={len(self.counters)} log_records={self.records}"
        if command == "COMPACT" and not args:
            return self.compact()
        raise BadCommand


def parse_name(tok):
    if not NAME_RE.fullmatch(tok):
        raise BadCommand
    return tok


def parse_int(tok):
    if not INT_RE.fullmatch(tok):
        raise BadCommand
    return int(tok)


def main(argv):
    if len(argv) != 1:
        print("usage: tally DIR", file=sys.stderr)
        return 2
    directory = argv[0]
    try:
        os.mkdir(directory)
    except FileExistsError:
        pass
    except OSError as e:
        print(f"tally: cannot create {directory}: {e}", file=sys.stderr)
        return 1
    if not os.path.isdir(directory):
        print(f"tally: {directory} is not a directory", file=sys.stderr)
        return 1

    store = Store(directory)
    try:
        store.recover()
    except OSError as e:
        print(f"tally: cannot open log: {e}", file=sys.stderr)
        return 1

    stdin, stdout = sys.stdin.buffer, sys.stdout
    while True:
        raw = stdin.readline()
        if not raw:
            break
        line = raw.decode("latin-1")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        stdout.write(store.handle(line) + "\n")
        stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
