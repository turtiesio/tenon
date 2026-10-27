import re
import sys

MAX_VALUE = 2**63 - 1
DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"
DIGIT_VALUES = {c: i for i, c in enumerate(DIGITS)}
NUMBER = re.compile(r"[0-9]{1,2}")


class UsageError(Exception):
    pass


def option_number(name, text, low, high):
    if not NUMBER.fullmatch(text) or not low <= int(text) <= high:
        raise UsageError(f"{name}: bad value {text!r} (expected {low}..{high})")
    return int(text)


def parse_args(argv):
    opts = {"-f": 10, "-t": 10, "-w": None, "-g": None}
    limits = {"-f": (2, 36), "-t": (2, 36), "-w": (1, 64), "-g": (1, 64)}
    upper = False
    values = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in opts:
            if i + 1 >= len(argv):
                raise UsageError(f"{arg} needs a value")
            opts[arg] = option_number(arg, argv[i + 1], *limits[arg])
            i += 2
        elif arg == "-u":
            upper = True
            i += 1
        else:
            values.append(arg)
            i += 1
    if not values:
        raise UsageError("no VALUE given")
    return opts["-f"], opts["-t"], opts["-w"], opts["-g"], upper, values


def parse_value(text, base):
    """Return the signed integer value of text, or None if invalid."""
    negative = text.startswith("-")
    digits = text[1:] if negative else text
    if not digits:
        return None
    total = 0
    for c in digits.lower():
        d = DIGIT_VALUES.get(c)
        if d is None or d >= base:
            return None
        total = total * base + d
        if total > MAX_VALUE:
            return None
    return -total if negative else total


def to_base(n, base):
    if n == 0:
        return "0"
    out = []
    while n:
        n, r = divmod(n, base)
        out.append(DIGITS[r])
    return "".join(reversed(out))


def group(digits, size):
    first = len(digits) % size or size
    parts = [digits[:first]]
    parts += [digits[i:i + size] for i in range(first, len(digits), size)]
    return "_".join(parts)


def format_value(n, base, width, size, upper):
    digits = to_base(abs(n), base)
    if upper:
        digits = digits.upper()
    if width is not None:
        digits = digits.rjust(width, "0")
    if size is not None:
        digits = group(digits, size)
    return ("-" if n < 0 else "") + digits


def main():
    try:
        from_base, to, width, size, upper, values = parse_args(sys.argv[1:])
    except UsageError as e:
        print(f"radix: {e}", file=sys.stderr)
        print("usage: radix [-f FROM] [-t TO] [-w WIDTH] [-g GROUP] [-u] VALUE...",
              file=sys.stderr)
        return 2

    status = 0
    for text in values:
        n = parse_value(text, from_base)
        if n is None:
            print(f"radix: invalid value {text!r}", file=sys.stderr)
            status = 1
        else:
            print(format_value(n, to, width, size, upper))
    return status


sys.exit(main())
