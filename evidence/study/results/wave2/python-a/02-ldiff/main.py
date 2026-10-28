#!/usr/bin/env python3
"""ldiff: line diff driven by a fixed LCS walk."""

import sys

EXIT_SAME, EXIT_DIFF, EXIT_USAGE = 0, 1, 2


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
        line = line.lower()  # bytes.lower() only touches ASCII
    return line


def lcs_table(a, b):
    """L[i][j] = LCS length of a[i:] and b[j:]."""
    n, m = len(a), len(b)
    table = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        row, below = table[i], table[i + 1]
        for j in range(m - 1, -1, -1):
            if a[i] == b[j]:
                row[j] = below[j + 1] + 1
            else:
                row[j] = max(below[j], row[j + 1])
    return table


def walk(keys_a, keys_b):
    """Yield (op, i, j) steps, op being one of ' ', '-', '+'."""
    n, m = len(keys_a), len(keys_b)
    table = lcs_table(keys_a, keys_b)
    i = j = 0
    while i < n or j < m:
        if i == n:
            yield "+", i, j
            j += 1
        elif j == m:
            yield "-", i, j
            i += 1
        elif keys_a[i] == keys_b[j]:
            yield " ", i, j
            i += 1
            j += 1
        elif table[i + 1][j] >= table[i][j + 1]:
            yield "-", i, j
            i += 1
        else:
            yield "+", i, j
            j += 1


def main(argv):
    flags = set()
    paths = []
    for arg in argv:
        if arg in ("-i", "-b", "-q", "-s"):
            flags.add(arg)
        elif arg.startswith("-"):
            print(f"ldiff: unknown option {arg}", file=sys.stderr)
            return EXIT_USAGE
        else:
            paths.append(arg)
    if len(paths) != 2 or {"-q", "-s"} <= flags:
        print("usage: ldiff [-i] [-b] [-q | -s] FILE1 FILE2", file=sys.stderr)
        return EXIT_USAGE

    try:
        lines_a = read_lines(paths[0])
        lines_b = read_lines(paths[1])
    except OSError as e:
        print(f"ldiff: {e}", file=sys.stderr)
        return EXIT_USAGE

    keys_a = [make_key(l, "-i" in flags, "-b" in flags) for l in lines_a]
    keys_b = [make_key(l, "-i" in flags, "-b" in flags) for l in lines_b]

    counts = {"+": 0, "-": 0, " ": 0}
    out = []
    for op, i, j in walk(keys_a, keys_b):
        counts[op] += 1
        if op == " ":
            out.append(b"  " + lines_a[i] + b"\n")
        elif op == "-":
            out.append(b"- " + lines_a[i] + b"\n")
        else:
            out.append(b"+ " + lines_b[j] + b"\n")

    if "-s" in flags:
        sys.stdout.write(f"+{counts['+']} -{counts['-']} ={counts[' ']}\n")
    elif "-q" not in flags:
        sys.stdout.buffer.write(b"".join(out))
        sys.stdout.buffer.flush()

    return EXIT_DIFF if counts["+"] + counts["-"] else EXIT_SAME


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
