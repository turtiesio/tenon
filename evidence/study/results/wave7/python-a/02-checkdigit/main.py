import re
import sys

SCHEMES = ("luhn", "isbn10", "isbn13")
MODES = ("check", "make")
VALUE_RE = re.compile(r"[0-9X]+(-[0-9X]+)*")

# (min, max) digit counts per (scheme, mode)
LENGTHS = {
    ("luhn", "check"): (2, 19),
    ("luhn", "make"): (1, 18),
    ("isbn10", "check"): (10, 10),
    ("isbn10", "make"): (9, 9),
    ("isbn13", "check"): (13, 13),
    ("isbn13", "make"): (12, 12),
}


def parse_digits(value, scheme, mode):
    """Return the list of digit values, or None if the value is not well formed."""
    if not VALUE_RE.fullmatch(value):
        return None
    chars = value.replace("-", "")
    if "X" in chars:
        if not (scheme == "isbn10" and mode == "check" and chars.index("X") == len(chars) - 1):
            return None
    lo, hi = LENGTHS[(scheme, mode)]
    if not lo <= len(chars) <= hi:
        return None
    if scheme == "isbn13" and chars[:3] not in ("978", "979"):
        return None
    return [10 if c == "X" else int(c) for c in chars]


def luhn_sum(digits):
    total = 0
    for pos, d in enumerate(reversed(digits), start=1):
        if pos % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total


def isbn10_sum(digits):
    return sum(w * d for w, d in zip(range(10, 0, -1), digits))


def isbn13_sum(digits):
    return sum((1 if i % 2 == 0 else 3) * d for i, d in enumerate(digits))


def is_correct(scheme, digits):
    if scheme == "luhn":
        return luhn_sum(digits) % 10 == 0
    if scheme == "isbn10":
        return isbn10_sum(digits) % 11 == 0
    return isbn13_sum(digits) % 10 == 0


def check_character(scheme, digits):
    if scheme == "luhn":
        # The check digit sits at position 1, so the digits shift one place left.
        return str((10 - luhn_sum(digits + [0]) % 10) % 10)
    if scheme == "isbn10":
        c = (11 - isbn10_sum(digits + [0]) % 11) % 11
        return "X" if c == 10 else str(c)
    return str((10 - isbn13_sum(digits) % 10) % 10)


def main():
    args = sys.argv[1:]
    if len(args) < 3 or args[0] not in SCHEMES or args[1] not in MODES:
        print("usage: checkdigit luhn|isbn10|isbn13 check|make VALUE...", file=sys.stderr)
        return 2
    scheme, mode, values = args[0], args[1], args[2:]

    lines = []
    all_good = True
    for value in values:
        digits = parse_digits(value, scheme, mode)
        if digits is None:
            lines.append(f"{value} invalid")
            all_good = False
        elif mode == "check":
            if is_correct(scheme, digits):
                lines.append(f"{value} ok")
            else:
                lines.append(f"{value} bad")
                all_good = False
        else:
            sep = "-" if "-" in value else ""
            lines.append(value + sep + check_character(scheme, digits))

    sys.stdout.write("".join(line + "\n" for line in lines))
    return 0 if all_good else 1


if __name__ == "__main__":
    sys.exit(main())
