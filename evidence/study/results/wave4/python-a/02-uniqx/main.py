import re
import sys

COUNT_RE = re.compile(r"[0-9]{1,4}")
BLANKS = " \t"
LOWER = {c: c + 32 for c in range(ord("A"), ord("Z") + 1)}


def usage(msg):
    print(f"uniqx: {msg}", file=sys.stderr)
    sys.exit(2)


def parse_args(argv):
    opts = {"c": False, "d": False, "u": False, "i": False, "f": 0, "s": 0}
    i = 0
    while i < len(argv):
        arg = argv[i]
        i += 1
        if arg in ("-c", "-d", "-u", "-i"):
            opts[arg[1]] = True
        elif arg in ("-f", "-s"):
            if i >= len(argv):
                usage(f"option {arg} needs a value")
            value = argv[i]
            i += 1
            if not COUNT_RE.fullmatch(value):
                usage(f"bad value for {arg}: {value!r}")
            opts[arg[1]] = int(value)
        else:
            usage(f"unexpected argument: {arg}")
    return opts


def read_lines(text):
    if not text:
        return []
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def make_key(line, fields, chars, ignore_case):
    pos = 0
    n = len(line)
    for _ in range(fields):
        while pos < n and line[pos] in BLANKS:
            pos += 1
        while pos < n and line[pos] not in BLANKS:
            pos += 1
    key = line[pos:][chars:]
    if ignore_case:
        key = key.translate(LOWER)
    return key


def group_lines(lines, opts):
    groups = []  # [representative line, key, size]
    for line in lines:
        key = make_key(line, opts["f"], opts["s"], opts["i"])
        if groups and groups[-1][1] == key:
            groups[-1][2] += 1
        else:
            groups.append([line, key, 1])
    return groups


def main():
    opts = parse_args(sys.argv[1:])
    text = sys.stdin.buffer.read().decode("latin-1")
    out = []
    for line, _, size in group_lines(read_lines(text), opts):
        if opts["d"] and size < 2:
            continue
        if opts["u"] and size != 1:
            continue
        prefix = f"{size:7d} " if opts["c"] else ""
        out.append(prefix + line + "\n")
    sys.stdout.write("".join(out))


if __name__ == "__main__":
    main()
