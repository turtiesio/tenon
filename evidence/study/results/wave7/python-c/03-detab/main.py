"""detab: expand tabs to spaces."""
import bisect
import re
import sys

STOPS_RULE = re.compile(r"[1-9][0-9]{0,3}(,[1-9][0-9]{0,3})*")


class UsageError(Exception):
    pass


def parse_stops(value):
    if not STOPS_RULE.fullmatch(value):
        raise UsageError(f"invalid tab stops: {value!r}")
    stops = [int(s) for s in value.split(",")]
    if any(a >= b for a, b in zip(stops, stops[1:])):
        raise UsageError(f"tab stops must be strictly increasing: {value!r}")
    return stops


def parse_args(args):
    stops = [8]
    leading_only = False
    files = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "-t":
            if i + 1 >= len(args):
                raise UsageError("-t needs a value")
            stops = parse_stops(args[i + 1])
            i += 2
            continue
        if arg == "-i":
            leading_only = True
        elif arg.startswith("-"):
            raise UsageError(f"unknown option: {arg}")
        else:
            files.append(arg)
        i += 1
    return stops, leading_only, files


def tab_width(column, stops):
    if len(stops) == 1:
        n = stops[0]
        return n - column % n
    k = bisect.bisect_right(stops, column)
    if k == len(stops):
        return 1
    return stops[k] - column


def expand_line(line, stops, leading_only):
    out = []
    column = 0
    in_indent = True
    for ch in line:
        if ch == "\t" and (in_indent or not leading_only):
            width = tab_width(column, stops)
            out.append(" " * width)
            column += width
            continue
        if ch not in " \t":
            in_indent = False
        out.append(ch)
        column += 1
    return "".join(out)


def main(argv):
    try:
        stops, leading_only, files = parse_args(argv)
    except UsageError as e:
        print(f"detab: {e}", file=sys.stderr)
        print("usage: detab [-t STOPS] [-i] [FILE...]", file=sys.stderr)
        return 2

    status = 0
    if files:
        chunks = []
        for path in files:
            try:
                with open(path, "rb") as f:
                    chunks.append(f.read())
            except OSError as e:
                print(f"detab: {path}: {e.strerror}", file=sys.stderr)
                status = 1
        data = b"".join(chunks)
    else:
        data = sys.stdin.buffer.read()

    text = data.decode("utf-8", "surrogateescape")
    lines = text.split("\n")
    result = "\n".join(expand_line(line, stops, leading_only) for line in lines)
    sys.stdout.buffer.write(result.encode("utf-8", "surrogateescape"))
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
