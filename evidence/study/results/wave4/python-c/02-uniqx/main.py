"""uniqx: collapse runs of adjacent repeated lines, in the style of uniq."""
import re
import sys
from dataclasses import dataclass

USAGE = "usage: uniqx [-c] [-d] [-u] [-i] [-f N] [-s N]"
BLANKS = " \t"


class UsageError(Exception):
    pass


@dataclass
class Options:
    count: bool = False
    repeated: bool = False
    unique: bool = False
    ignore_case: bool = False
    fields: int = 0
    chars: int = 0


FLAGS = {"-c": "count", "-d": "repeated", "-u": "unique", "-i": "ignore_case"}
VALUED = {"-f": "fields", "-s": "chars"}


def parse_args(argv):
    opts = Options()
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in FLAGS:
            setattr(opts, FLAGS[arg], True)
            i += 1
        elif arg in VALUED:
            if i + 1 >= len(argv):
                raise UsageError(f"option {arg} requires a value")
            value = argv[i + 1]
            if not re.fullmatch(r"[0-9]{1,4}", value):
                raise UsageError(f"invalid value for {arg}: {value!r}")
            setattr(opts, VALUED[arg], int(value))
            i += 2
        else:
            raise UsageError(f"unexpected argument: {arg!r}")
    return opts


def comparison_key(line, opts):
    pos = 0
    for _ in range(opts.fields):
        while pos < len(line) and line[pos] in BLANKS:
            pos += 1
        while pos < len(line) and line[pos] not in BLANKS:
            pos += 1
    key = line[pos:][opts.chars:]
    if opts.ignore_case:
        key = key.translate(ASCII_LOWER)
    return key


ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def read_lines(data):
    text = data.decode("latin-1")
    if not text:
        return []
    lines = text.split("\n")
    if text.endswith("\n"):
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def groups(lines, opts):
    """Yield (first_line, size) for each maximal run of equal keys."""
    first, first_key, size = None, None, 0
    for line in lines:
        key = comparison_key(line, opts)
        if size and key == first_key:
            size += 1
            continue
        if size:
            yield first, size
        first, first_key, size = line, key, 1
    if size:
        yield first, size


def main(argv):
    try:
        opts = parse_args(argv)
    except UsageError as e:
        print(f"uniqx: {e}\n{USAGE}", file=sys.stderr)
        return 2

    out = []
    for line, size in groups(read_lines(sys.stdin.buffer.read()), opts):
        if opts.repeated and size < 2:
            continue
        if opts.unique and size != 1:
            continue
        out.append(f"{size:>7} {line}\n" if opts.count else f"{line}\n")
    sys.stdout.buffer.write("".join(out).encode("latin-1"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
