"""ldiff: line diff defined by a fixed LCS walk."""
import sys

USAGE = "usage: ldiff [-i] [-b] [-q | -s] FILE1 FILE2"


def read_lines(path):
    with open(path, "rb") as f:
        data = f.read()
    lines = data.split(b"\n")
    if lines[-1] == b"":
        lines.pop()
    return lines


def make_key(line, ignore_case, ignore_trailing):
    if ignore_trailing:
        line = line.rstrip(b" \t")
    if ignore_case:
        line = line.lower()  # bytes.lower() only folds ASCII
    return line


def lcs_table(a, b):
    """L[i][j] = LCS length of a[i:] and b[j:]."""
    n, m = len(a), len(b)
    table = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        row, below = table[i], table[i + 1]
        ai = a[i]
        for j in range(m - 1, -1, -1):
            if ai == b[j]:
                row[j] = below[j + 1] + 1
            else:
                row[j] = below[j] if below[j] >= row[j + 1] else row[j + 1]
    return table


def walk(a_keys, b_keys):
    """Yield ('=', i, j), ('-', i, None) or ('+', None, j) steps."""
    n, m = len(a_keys), len(b_keys)
    table = lcs_table(a_keys, b_keys)
    i = j = 0
    while i < n or j < m:
        if i == n:
            yield "+", None, j
            j += 1
        elif j == m:
            yield "-", i, None
            i += 1
        elif a_keys[i] == b_keys[j]:
            yield "=", i, j
            i += 1
            j += 1
        elif table[i + 1][j] >= table[i][j + 1]:
            yield "-", i, None
            i += 1
        else:
            yield "+", None, j
            j += 1


def main(argv):
    flags = set()
    paths = []
    for arg in argv:
        if arg.startswith("-"):
            if arg not in ("-i", "-b", "-q", "-s"):
                print(f"ldiff: unknown option {arg}\n{USAGE}", file=sys.stderr)
                return 2
            flags.add(arg)
        else:
            paths.append(arg)
    if ("-q" in flags and "-s" in flags) or len(paths) != 2:
        print(USAGE, file=sys.stderr)
        return 2

    try:
        a = read_lines(paths[0])
        b = read_lines(paths[1])
    except OSError as e:
        print(f"ldiff: {e}", file=sys.stderr)
        return 2

    ignore_case, ignore_trailing = "-i" in flags, "-b" in flags
    a_keys = [make_key(line, ignore_case, ignore_trailing) for line in a]
    b_keys = [make_key(line, ignore_case, ignore_trailing) for line in b]

    out = []
    counts = {"+": 0, "-": 0, "=": 0}
    for op, i, j in walk(a_keys, b_keys):
        counts[op] += 1
        if op == "=":
            out.append(b"  " + a[i] + b"\n")
        elif op == "-":
            out.append(b"- " + a[i] + b"\n")
        else:
            out.append(b"+ " + b[j] + b"\n")

    if "-s" in flags:
        summary = f"+{counts['+']} -{counts['-']} ={counts['=']}\n"
        sys.stdout.write(summary)
    elif "-q" not in flags:
        sys.stdout.buffer.write(b"".join(out))
    return 1 if counts["+"] + counts["-"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
