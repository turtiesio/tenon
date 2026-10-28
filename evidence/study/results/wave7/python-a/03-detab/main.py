import re
import sys

STOPS_RE = re.compile(r"[1-9][0-9]{0,3}(,[1-9][0-9]{0,3})*")


class UsageError(Exception):
    pass


def parse_args(argv):
    stops = [8]
    leading_only = False
    files = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "-t":
            if i + 1 >= len(argv):
                raise UsageError("-t needs a value")
            value = argv[i + 1]
            if not STOPS_RE.fullmatch(value):
                raise UsageError(f"bad stops: {value!r}")
            stops = [int(s) for s in value.split(",")]
            if any(a >= b for a, b in zip(stops, stops[1:])):
                raise UsageError("stops must be strictly increasing")
            i += 2
        elif arg == "-i":
            leading_only = True
            i += 1
        elif arg.startswith("-"):
            raise UsageError(f"unknown argument: {arg}")
        else:
            files.append(arg)
            i += 1
    return stops, leading_only, files


def tab_width(column, stops):
    if len(stops) == 1:
        n = stops[0]
        return n - column % n
    for stop in stops:
        if stop > column:
            return stop - column
    return 1


def expand_line(line, stops, leading_only):
    out = []
    column = 0
    leading = True
    for ch in line:
        if ch == "\t":
            if leading or not leading_only:
                width = tab_width(column, stops)
                out.append(" " * width)
                column += width
            else:
                out.append(ch)
                column += 1
        else:
            if ch != " ":
                leading = False
            out.append(ch)
            column += 1
    return "".join(out)


def read_input(files):
    """Return (bytes of the concatenated stream, whether any file failed)."""
    if not files:
        return sys.stdin.buffer.read(), False
    chunks = []
    failed = False
    for path in files:
        try:
            with open(path, "rb") as f:
                chunks.append(f.read())
        except OSError as e:
            print(f"detab: {path}: {e.strerror or e}", file=sys.stderr)
            failed = True
    return b"".join(chunks), failed


def main():
    try:
        stops, leading_only, files = parse_args(sys.argv[1:])
    except UsageError as e:
        print(f"detab: {e}", file=sys.stderr)
        return 2

    data, failed = read_input(files)
    text = data.decode("utf-8", errors="surrogateescape")
    result = "\n".join(expand_line(line, stops, leading_only) for line in text.split("\n"))
    sys.stdout.buffer.write(result.encode("utf-8", errors="surrogateescape"))
    sys.stdout.buffer.flush()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
