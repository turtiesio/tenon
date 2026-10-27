import sys

ESCAPES = {"n": "\n", "t": "\t", "\\": "\\", "-": "-"}


class UsageError(Exception):
    pass


def tokenize(arg):
    """Return a list of (char, escaped) tokens."""
    tokens = []
    i = 0
    while i < len(arg):
        ch = arg[i]
        if ch == "\\":
            if i + 1 >= len(arg) or arg[i + 1] not in ESCAPES:
                raise UsageError(f"malformed set: {arg!r}")
            tokens.append((ESCAPES[arg[i + 1]], True))
            i += 2
        else:
            tokens.append((ch, False))
            i += 1
    return tokens


def parse_set(arg):
    tokens = tokenize(arg)
    chars = []
    i = 0
    while i < len(tokens):
        if i + 2 < len(tokens) and tokens[i + 1] == ("-", False):
            lo, hi = tokens[i][0], tokens[i + 2][0]
            if ord(lo) > ord(hi):
                raise UsageError(f"reversed range {lo}-{hi} in set {arg!r}")
            chars.extend(chr(c) for c in range(ord(lo), ord(hi) + 1))
            i += 3
        else:
            chars.append(tokens[i][0])
            i += 1
    return chars


def parse_args(argv):
    delete = squeeze = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "-d":
            delete = True
        elif arg == "-s":
            squeeze = True
        elif arg == "--":
            i += 1
            break
        elif arg.startswith("-") and len(arg) >= 2:
            raise UsageError(f"unknown option: {arg}")
        else:
            break
        i += 1
    sets = [parse_set(a) for a in argv[i:]]

    allowed = {
        (False, False): {2},
        (True, False): {1},
        (False, True): {1, 2},
        (True, True): {2},
    }[(delete, squeeze)]
    if len(sets) not in allowed:
        raise UsageError("wrong number of sets")
    translating = not delete and len(sets) == 2
    if translating and not sets[1]:
        raise UsageError("SET2 must not be empty when translating")
    return delete, squeeze, sets


def squeeze_runs(text, squeeze_set):
    out = []
    prev = None
    for ch in text:
        if ch == prev and ch in squeeze_set:
            continue
        out.append(ch)
        prev = ch
    return "".join(out)


def main():
    try:
        delete, squeeze, sets = parse_args(sys.argv[1:])
    except UsageError as e:
        print(f"trx: {e}", file=sys.stderr)
        print("usage: trx [-d] [-s] [--] SET1 [SET2]", file=sys.stderr)
        sys.exit(2)

    text = sys.stdin.buffer.read().decode("latin-1")
    if delete:
        text = text.translate({ord(c): None for c in sets[0]})
        squeeze_set = set(sets[1]) if squeeze else set()
    elif len(sets) == 2:
        set1, set2 = sets
        mapping = {}
        for i, c in enumerate(set1):
            mapping[ord(c)] = set2[min(i, len(set2) - 1)]
        text = text.translate(mapping)
        squeeze_set = set(set2)
    else:
        squeeze_set = set(sets[0])
    if squeeze:
        text = squeeze_runs(text, squeeze_set)
    sys.stdout.buffer.write(text.encode("latin-1"))


if __name__ == "__main__":
    main()
