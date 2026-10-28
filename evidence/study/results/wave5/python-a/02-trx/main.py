import sys

ESCAPES = {"n": "\n", "t": "\t", "\\": "\\", "-": "-"}


class UsageError(Exception):
    pass


def tokenize(spec):
    """Return a list of (char, escaped) tokens."""
    tokens = []
    i = 0
    while i < len(spec):
        c = spec[i]
        if c == "\\":
            if i + 1 >= len(spec) or spec[i + 1] not in ESCAPES:
                raise UsageError("bad escape in set: " + spec)
            tokens.append((ESCAPES[spec[i + 1]], True))
            i += 2
        else:
            tokens.append((c, False))
            i += 1
    return tokens


def parse_set(spec):
    tokens = tokenize(spec)
    result = []
    i = 0
    while i < len(tokens):
        if i + 2 < len(tokens) and tokens[i + 1] == ("-", False):
            lo, hi = tokens[i][0], tokens[i + 2][0]
            if lo > hi:
                raise UsageError("reversed range in set: " + spec)
            result.extend(chr(code) for code in range(ord(lo), ord(hi) + 1))
            i += 3
        else:
            result.append(tokens[i][0])
            i += 1
    return result


def parse_args(args):
    delete = squeeze = False
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "-d":
            delete = True
        elif arg == "-s":
            squeeze = True
        elif arg == "--":
            i += 1
            break
        elif arg.startswith("-") and len(arg) >= 2:
            raise UsageError("unknown option: " + arg)
        else:
            break
        i += 1
    sets = args[i:]

    if delete:
        allowed = (2,) if squeeze else (1,)
    elif squeeze:
        allowed = (1, 2)
    else:
        allowed = (2,)
    if len(sets) not in allowed:
        raise UsageError("wrong number of sets")

    parsed = [parse_set(s) for s in sets]
    translating = not delete and len(parsed) == 2
    if translating and not parsed[1]:
        raise UsageError("empty SET2")
    return delete, squeeze, parsed, translating


def build_mapping(set1, set2):
    mapping = {}
    for i, c in enumerate(set1):
        mapping[c] = set2[min(i, len(set2) - 1)]
    return mapping


def main():
    try:
        delete, squeeze, sets, translating = parse_args(sys.argv[1:])
    except UsageError as e:
        print("trx: " + str(e), file=sys.stderr)
        return 2

    data = sys.stdin.buffer.read().decode("latin-1")
    set1 = sets[0]

    if delete:
        remove = set(set1)
        chars = [c for c in data if c not in remove]
        squeeze_set = set(sets[1]) if squeeze else set()
    elif translating:
        mapping = build_mapping(set1, sets[1])
        chars = [mapping.get(c, c) for c in data]
        squeeze_set = set(sets[1]) if squeeze else set()
    else:
        chars = list(data)
        squeeze_set = set(set1) if squeeze else set()

    if squeeze_set:
        out = []
        prev = None
        for c in chars:
            if c == prev and c in squeeze_set:
                continue
            out.append(c)
            prev = c
        chars = out

    sys.stdout.buffer.write("".join(chars).encode("latin-1"))
    return 0


sys.exit(main())
