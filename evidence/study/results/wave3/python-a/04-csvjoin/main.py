import sys


class UsageError(Exception):
    pass


class DataError(Exception):
    pass


def parse_csv(text):
    """Strict CSV parser. Returns a list of records (lists of strings)."""
    records = []
    n = len(text)
    pos = 0

    def at_terminator(p):
        """Length of the record terminator at p (0 if none)."""
        if text.startswith("\r\n", p):
            return 2
        if text.startswith("\n", p):
            return 1
        return 0

    while pos < n:
        skip = at_terminator(pos)
        if skip:
            pos += skip  # empty line
            continue

        fields = []
        while True:
            if pos < n and text[pos] == '"':
                pos += 1
                chunks = []
                while True:
                    end = text.find('"', pos)
                    if end < 0:
                        raise DataError("unterminated quoted field")
                    chunks.append(text[pos:end])
                    if text.startswith('"', end + 1):
                        chunks.append('"')
                        pos = end + 2
                    else:
                        pos = end + 1
                        break
                fields.append("".join(chunks))
                if pos < n and text[pos] != "," and not at_terminator(pos):
                    raise DataError("unexpected character after closing quote")
            else:
                start = pos
                while pos < n and text[pos] not in ',"\r\n':
                    pos += 1
                if pos < n and text[pos] == '"':
                    raise DataError("quote inside unquoted field")
                if pos < n and text[pos] == "\r" and not at_terminator(pos):
                    raise DataError("stray carriage return")
                fields.append(text[start:pos])

            if pos < n and text[pos] == ",":
                pos += 1
                continue
            pos += at_terminator(pos)
            break
        records.append(fields)
    return records


def load_table(path):
    try:
        with open(path, "rb") as f:
            text = f.read().decode("latin-1")
    except OSError as e:
        raise DataError(f"cannot read {path}: {e.strerror}")
    records = parse_csv(text)
    if not records:
        raise DataError(f"{path}: no header row")
    header, rows = records[0], records[1:]
    if len(set(header)) != len(header):
        raise DataError(f"{path}: duplicate column name in header")
    for row in rows:
        if len(row) != len(header):
            raise DataError(f"{path}: record has {len(row)} fields, expected {len(header)}")
    return header, rows


def format_field(field):
    if any(c in field for c in ',"\r\n'):
        return '"' + field.replace('"', '""') + '"'
    return field


def format_record(fields):
    return ",".join(format_field(f) for f in fields) + "\n"


def parse_args(argv):
    left_join = False
    key = "id"
    paths = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "-l":
            left_join = True
        elif arg == "-k":
            if i + 1 >= len(argv):
                raise UsageError("-k needs a name")
            key = argv[i + 1]
            i += 1
        elif arg.startswith("-"):
            raise UsageError(f"unknown option {arg!r}")
        else:
            paths.append(arg)
        i += 1
    if len(paths) != 2:
        raise UsageError("expected exactly two files: LEFT RIGHT")
    if key == "":
        raise UsageError("empty key name")
    return left_join, key, paths[0], paths[1]


def join(left, right, key, left_join):
    (lhead, lrows), (rhead, rrows) = left, right
    for name, head in (("left", lhead), ("right", rhead)):
        if key not in head:
            raise DataError(f"key column {key!r} not in {name} file")
    lkey = lhead.index(key)
    rkey = rhead.index(key)
    right_cols = [i for i in range(len(rhead)) if i != rkey]

    lnames = set(lhead)
    header = lhead + [("r." + rhead[i]) if rhead[i] in lnames else rhead[i]
                      for i in right_cols]

    by_key = {}
    for row in rrows:
        by_key.setdefault(row[rkey], []).append([row[i] for i in right_cols])

    out = [header]
    blank = [""] * len(right_cols)
    for row in lrows:
        matches = by_key.get(row[lkey])
        if matches:
            out.extend(row + extra for extra in matches)
        elif left_join:
            out.append(row + blank)
    return out


def main():
    try:
        left_join, key, left_path, right_path = parse_args(sys.argv[1:])
    except UsageError as e:
        print(f"csvjoin: {e}", file=sys.stderr)
        print("usage: csvjoin [-l] [-k NAME] LEFT RIGHT", file=sys.stderr)
        return 2

    try:
        left = load_table(left_path)
        right = load_table(right_path)
        records = join(left, right, key, left_join)
    except DataError as e:
        print(f"csvjoin: {e}", file=sys.stderr)
        return 1

    out = "".join(format_record(r) for r in records)
    sys.stdout.buffer.write(out.encode("latin-1"))
    sys.stdout.buffer.flush()
    return 0


sys.exit(main())
