"""csvjoin: join two CSV files on a key column."""
import sys
from collections import defaultdict


class UsageError(Exception):
    pass


class DataError(Exception):
    pass


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
                raise UsageError("-k needs a NAME")
            key = argv[i + 1]
            i += 1
        elif arg.startswith("-"):
            raise UsageError(f"unknown option {arg!r}")
        else:
            paths.append(arg)
        i += 1
    if not key:
        raise UsageError("empty key NAME")
    if len(paths) != 2:
        raise UsageError("expected exactly two files: LEFT RIGHT")
    return left_join, key, paths


def parse_csv(text):
    """Parse CSV text into a list of records (lists of strings)."""
    records = []
    n = len(text)
    i = 0
    while i < n:
        # Skip empty lines.
        if text[i] == "\n":
            i += 1
            continue
        if text.startswith("\r\n", i):
            i += 2
            continue
        record = []
        while True:
            if i < n and text[i] == '"':
                i += 1
                parts = []
                while True:
                    end = text.find('"', i)
                    if end < 0:
                        raise DataError("quoted field has no closing quote")
                    parts.append(text[i:end])
                    i = end + 1
                    if i < n and text[i] == '"':
                        parts.append('"')
                        i += 1
                    else:
                        break
                field = "".join(parts)
            else:
                start = i
                while i < n and text[i] not in ',"\r\n':
                    i += 1
                field = text[start:i]
                if i < n and text[i] == '"':
                    raise DataError("quote inside an unquoted field")
            record.append(field)
            # After a field: ',', a record terminator, or the end of the file.
            if i >= n:
                break
            if text[i] == ",":
                i += 1
                continue
            if text[i] == "\n":
                i += 1
                break
            if text.startswith("\r\n", i):
                i += 2
                break
            raise DataError(f"unexpected character {text[i]!r} after field")
        records.append(record)
    return records


def load_table(path, key):
    try:
        with open(path, "rb") as f:
            text = f.read().decode("latin-1")
    except OSError as e:
        raise DataError(f"cannot read {path}: {e.strerror}") from None
    try:
        records = parse_csv(text)
    except DataError as e:
        raise DataError(f"{path}: {e}") from None
    if not records:
        raise DataError(f"{path}: no header row")
    header, rows = records[0], records[1:]
    if len(set(header)) != len(header):
        raise DataError(f"{path}: duplicate column name in header")
    for number, row in enumerate(rows, start=2):
        if len(row) != len(header):
            raise DataError(
                f"{path}: record {number} has {len(row)} fields, expected {len(header)}"
            )
    if key not in header:
        raise DataError(f"{path}: no column named {key!r}")
    return header, rows


def format_field(field):
    if any(c in field for c in ',"\r\n'):
        return '"' + field.replace('"', '""') + '"'
    return field


def format_record(fields):
    return ",".join(format_field(f) for f in fields) + "\n"


def join(left, right, key, left_join):
    left_header, left_rows = left
    right_header, right_rows = right
    left_key = left_header.index(key)
    right_key = right_header.index(key)
    right_columns = [k for k in range(len(right_header)) if k != right_key]

    left_names = set(left_header)
    header = list(left_header)
    for k in right_columns:
        name = right_header[k]
        header.append("r." + name if name in left_names else name)
    yield header

    by_key = defaultdict(list)
    for row in right_rows:
        by_key[row[right_key]].append([row[k] for k in right_columns])

    for row in left_rows:
        matches = by_key.get(row[left_key], [])
        for extra in matches:
            yield row + extra
        if not matches and left_join:
            yield row + [""] * len(right_columns)


def main():
    try:
        left_join, key, (left_path, right_path) = parse_args(sys.argv[1:])
    except UsageError as e:
        print(f"csvjoin: {e}", file=sys.stderr)
        return 2
    try:
        left = load_table(left_path, key)
        right = load_table(right_path, key)
    except DataError as e:
        print(f"csvjoin: {e}", file=sys.stderr)
        return 1
    sys.stdout.write("".join(format_record(r) for r in join(left, right, key, left_join)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
