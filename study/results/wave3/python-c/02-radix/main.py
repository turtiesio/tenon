"""radix: integer base converter."""
import re
import string
import sys

DIGITS = string.digits + string.ascii_lowercase
DIGIT_VALUE = {c: i for i, c in enumerate(DIGITS)}
MAX_ABS = 2**63 - 1
OPTION_VALUE = re.compile(r"[0-9]{1,2}")
# option -> (name, minimum, maximum)
VALUE_OPTIONS = {
    "-f": ("FROM", 2, 36),
    "-t": ("TO", 2, 36),
    "-w": ("WIDTH", 1, 64),
    "-g": ("GROUP", 1, 64),
}


class UsageError(Exception):
    pass


def parse_args(argv):
    opts = {"-f": 10, "-t": 10, "-w": None, "-g": None}
    upper = False
    values = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in VALUE_OPTIONS:
            name, low, high = VALUE_OPTIONS[arg]
            if i + 1 >= len(argv):
                raise UsageError(f"option {arg} needs a value")
            text = argv[i + 1]
            if not OPTION_VALUE.fullmatch(text) or not low <= int(text) <= high:
                raise UsageError(f"bad {name}: {text!r}")
            opts[arg] = int(text)
            i += 2
        elif arg == "-u":
            upper = True
            i += 1
        else:
            values.append(arg)
            i += 1
    if not values:
        raise UsageError("no VALUE given")
    return opts, upper, values


def parse_value(text, base):
    negative = text.startswith("-")
    digits = text[1:] if negative else text
    if not digits:
        raise ValueError("no digits")
    n = 0
    for ch in digits.lower():
        d = DIGIT_VALUE.get(ch)
        if d is None or d >= base:
            raise ValueError(f"invalid digit {ch!r} for base {base}")
        n = n * base + d
        if n > MAX_ABS:
            raise ValueError("out of range")
    return -n if negative else n


def to_base(n, base):
    if n == 0:
        return "0"
    out = []
    while n:
        n, d = divmod(n, base)
        out.append(DIGITS[d])
    return "".join(reversed(out))


def group(digits, size):
    head = len(digits) % size or size
    parts = [digits[:head]]
    parts += [digits[k:k + size] for k in range(head, len(digits), size)]
    return "_".join(parts)


def format_value(n, opts, upper):
    digits = to_base(abs(n), opts["-t"])
    if upper:
        digits = digits.upper()
    if opts["-w"] is not None:
        digits = digits.rjust(opts["-w"], "0")
    if opts["-g"] is not None:
        digits = group(digits, opts["-g"])
    return ("-" if n < 0 else "") + digits


def main():
    try:
        opts, upper, values = parse_args(sys.argv[1:])
    except UsageError as e:
        print(f"radix: {e}", file=sys.stderr)
        return 2
    status = 0
    for text in values:
        try:
            n = parse_value(text, opts["-f"])
        except ValueError as e:
            print(f"radix: {text!r}: {e}", file=sys.stderr)
            status = 1
            continue
        print(format_value(n, opts, upper))
    return status


if __name__ == "__main__":
    sys.exit(main())
