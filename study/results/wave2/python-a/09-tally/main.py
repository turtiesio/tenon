#!/usr/bin/env python3
"""tally: persistent named counters backed by a write-ahead log."""

import os
import re
import sys

NAME = r"[a-z][a-z0-9_]{0,31}"
INT = r"-?[0-9]{1,15}"
NAME_RE = re.compile(NAME)
INT_RE = re.compile(INT)
RECORD_RE = re.compile(rf"(?:([SA]) ({NAME}) ({INT})|(D) ({NAME}))")

LOG_NAME = "tally.log"
TMP_NAME = "tally.log.tmp"

BAD_COMMAND = "ERR bad command"


def apply_record(counters, record):
    """Apply one parsed log record (a RECORD_RE match) to the counters."""
    if record[1] == "S":
        counters[record[2]] = int(record[3])
    elif record[1] == "A":
        counters[record[2]] = counters.get(record[2], 0) + int(record[3])
    else:
        counters.pop(record[5], None)


def replay(data):
    """Replay the valid prefix of a log.

    Return (counters, record count, length in bytes of the valid prefix).
    """
    counters = {}
    records = 0
    valid_length = 0
    pos = 0
    while True:
        end = data.find(b"\n", pos)
        if end < 0:  # incomplete (or no) final line
            break
        record = RECORD_RE.fullmatch(data[pos:end].decode("latin-1"))
        if record is None:
            break
        apply_record(counters, record)
        records += 1
        pos = valid_length = end + 1
    return counters, records, valid_length


def write_all(fd, data):
    while data:
        data = data[os.write(fd, data):]


class Store:
    def __init__(self, directory):
        self.log_path = os.path.join(directory, LOG_NAME)
        self.tmp_path = os.path.join(directory, TMP_NAME)

        try:
            os.remove(self.tmp_path)
        except FileNotFoundError:
            pass

        try:
            with open(self.log_path, "rb") as f:
                data = f.read()
        except FileNotFoundError:
            data = b""
        self.counters, self.records, valid_length = replay(data)

        self.fd = self.open_log()
        if valid_length < len(data):
            os.ftruncate(self.fd, valid_length)

    def open_log(self):
        return os.open(self.log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)

    def append(self, record):
        """Write one record to the log before the caller acknowledges it."""
        write_all(self.fd, (record + "\n").encode("ascii"))
        os.fsync(self.fd)
        self.records += 1

    def execute(self, line):
        parts = line.split(" ")
        command, args = parts[0], parts[1:]
        if command in ("SET", "ADD"):
            if len(args) != 2 or not NAME_RE.fullmatch(args[0]) or not INT_RE.fullmatch(args[1]):
                return BAD_COMMAND
            name, number = args[0], int(args[1])
            if command == "SET":
                self.append(f"S {name} {number}")
                self.counters[name] = number
                return "OK"
            self.append(f"A {name} {number}")
            self.counters[name] = self.counters.get(name, 0) + number
            return str(self.counters[name])
        if command in ("GET", "DEL"):
            if len(args) != 1 or not NAME_RE.fullmatch(args[0]):
                return BAD_COMMAND
            name = args[0]
            if command == "GET":
                return str(self.counters[name]) if name in self.counters else "NONE"
            if name not in self.counters:
                return "NONE"
            self.append(f"D {name}")
            del self.counters[name]
            return "OK"
        if args:
            return BAD_COMMAND
        if command == "LIST":
            items = "".join(f" {n}={v}" for n, v in sorted(self.counters.items()))
            return f"{len(self.counters)}{items}"
        if command == "INFO":
            return f"counters={len(self.counters)} log_records={self.records}"
        if command == "COMPACT":
            return f"OK {self.compact()}"
        return BAD_COMMAND

    def compact(self):
        """Rewrite the log as a snapshot via a temporary file and an atomic rename."""
        snapshot = "".join(f"S {n} {v}\n" for n, v in sorted(self.counters.items()))
        fd = os.open(self.tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        try:
            write_all(fd, snapshot.encode("ascii"))
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(self.tmp_path, self.log_path)
        os.close(self.fd)
        self.fd = self.open_log()
        self.records = len(self.counters)
        return self.records


def prepare_directory(path):
    """Create the data directory if needed; return an error message or None."""
    if os.path.isdir(path):
        return None
    if os.path.lexists(path):
        return f"{path}: not a directory"
    try:
        os.mkdir(path)
    except OSError as e:
        return f"{path}: {e.strerror}"
    return None


def main(argv):
    if len(argv) != 1:
        print("usage: tally DIR", file=sys.stderr)
        return 2
    error = prepare_directory(argv[0])
    if error:
        print(f"tally: {error}", file=sys.stderr)
        return 1
    try:
        store = Store(argv[0])
    except OSError as e:
        print(f"tally: {e}", file=sys.stderr)
        return 1

    for raw in sys.stdin.buffer:
        line = raw.decode("latin-1")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        sys.stdout.write(store.execute(line) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
