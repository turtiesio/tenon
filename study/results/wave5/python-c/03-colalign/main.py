import re
import sys

LIST_RE = re.compile(r"[1-9][0-9]{0,2}(,[1-9][0-9]{0,2})*")
FIELD_RE = re.compile(r"[^ \t]+")


class UsageError(Exception):
    pass


def parse_args(argv):
    sep = None
    outsep = "  "
    right = set()
    i = 0
    while i < len(argv):
        opt = argv[i]
        if opt not in ("-s", "-o", "-r"):
            raise UsageError(f"unexpected argument: {opt!r}")
        if i + 1 >= len(argv):
            raise UsageError(f"option {opt} requires a value")
        value = argv[i + 1]
        if opt == "-s":
            if len(value) != 1:
                raise UsageError(f"-s needs exactly one character, got {value!r}")
            sep = value
        elif opt == "-o":
            outsep = value
        else:
            if not LIST_RE.fullmatch(value):
                raise UsageError(f"malformed column list: {value!r}")
            right = {int(n) - 1 for n in value.split(",")}
        i += 2
    return sep, outsep, right


def read_lines():
    text = sys.stdin.buffer.read().decode("utf-8")
    if not text:
        return []
    lines = text.split("\n")
    if text.endswith("\n"):
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def split_fields(line, sep):
    if sep is None:
        return FIELD_RE.findall(line)
    if line == "":
        return []
    return line.split(sep)


def main():
    try:
        sep, outsep, right = parse_args(sys.argv[1:])
    except UsageError as e:
        print(f"colalign: {e}", file=sys.stderr)
        print("usage: colalign [-s CHAR] [-o OUTSEP] [-r LIST]", file=sys.stderr)
        sys.exit(2)

    rows = [split_fields(line, sep) for line in read_lines()]
    widths = []
    for fields in rows:
        for k, field in enumerate(fields):
            if k == len(widths):
                widths.append(0)
            widths[k] = max(widths[k], len(field))

    out = []
    for fields in rows:
        cells = []
        for k, field in enumerate(fields):
            if k in right:
                cells.append(field.rjust(widths[k]))
            elif k == len(fields) - 1:
                cells.append(field)
            else:
                cells.append(field.ljust(widths[k]))
        out.append(outsep.join(cells) + "\n")
    sys.stdout.buffer.write("".join(out).encode("utf-8"))


if __name__ == "__main__":
    main()
