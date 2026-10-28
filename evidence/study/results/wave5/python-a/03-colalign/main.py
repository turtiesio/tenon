import re
import sys

LIST_RE = re.compile(r"[1-9][0-9]{0,2}(,[1-9][0-9]{0,2})*")
WHITESPACE_RE = re.compile(r"[^ \t]+")


class UsageError(Exception):
    pass


def parse_args(args):
    sep = None
    outsep = "  "
    right = set()
    i = 0
    while i < len(args):
        opt = args[i]
        if opt not in ("-s", "-o", "-r"):
            raise UsageError("unexpected argument: " + opt)
        if i + 1 >= len(args):
            raise UsageError(opt + " needs a value")
        value = args[i + 1]
        if opt == "-s":
            if len(value) != 1:
                raise UsageError("-s needs exactly one character")
            sep = value
        elif opt == "-o":
            outsep = value
        else:
            if not LIST_RE.fullmatch(value):
                raise UsageError("malformed column list: " + value)
            right = {int(n) for n in value.split(",")}
        i += 2
    return sep, outsep, right


def split_fields(line, sep):
    if sep is None:
        return WHITESPACE_RE.findall(line)
    if not line:
        return []
    return line.split(sep)


def main():
    try:
        sep, outsep, right = parse_args(sys.argv[1:])
    except UsageError as e:
        print("colalign: " + str(e), file=sys.stderr)
        return 2

    text = sys.stdin.buffer.read().decode("utf-8", errors="surrogateescape")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    rows = []
    for line in lines:
        if line.endswith("\r"):
            line = line[:-1]
        rows.append(split_fields(line, sep))

    widths = []
    for row in rows:
        for k, field in enumerate(row):
            if k == len(widths):
                widths.append(len(field))
            else:
                widths[k] = max(widths[k], len(field))

    out = []
    for row in rows:
        cells = []
        for k, field in enumerate(row):
            if (k + 1) in right:
                cells.append(field.rjust(widths[k]))
            elif k == len(row) - 1:
                cells.append(field)
            else:
                cells.append(field.ljust(widths[k]))
        out.append(outsep.join(cells) + "\n")

    sys.stdout.buffer.write("".join(out).encode("utf-8", errors="surrogateescape"))
    return 0


sys.exit(main())
