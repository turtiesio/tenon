"""checkdigit: verify and compute check digits (Luhn, ISBN-10, ISBN-13)."""
import re
import sys

SCHEMES = ("luhn", "isbn10", "isbn13")
MODES = ("check", "make")
GROUPS = re.compile(r"[0-9X]+(-[0-9X]+)*")

# (min, max) digit counts per scheme and mode.
DIGIT_COUNTS = {
    ("luhn", "check"): (2, 19),
    ("luhn", "make"): (1, 18),
    ("isbn10", "check"): (10, 10),
    ("isbn10", "make"): (9, 9),
    ("isbn13", "check"): (13, 13),
    ("isbn13", "make"): (12, 12),
}


def parse_digits(value, scheme, mode):
    """Return the list of digit values, or None if the value is not well formed."""
    if not GROUPS.fullmatch(value):
        return None
    if "X" in value:
        allowed = scheme == "isbn10" and mode == "check"
        if not allowed or value.index("X") != len(value) - 1:
            return None
    chars = value.replace("-", "")
    low, high = DIGIT_COUNTS[(scheme, mode)]
    if not low <= len(chars) <= high:
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
    return sum((10 - i) * d for i, d in enumerate(digits))


def isbn13_sum(digits):
    return sum((3 if i % 2 else 1) * d for i, d in enumerate(digits))


def is_correct(scheme, digits):
    if scheme == "luhn":
        return luhn_sum(digits) % 10 == 0
    if scheme == "isbn10":
        return isbn10_sum(digits) % 11 == 0
    return isbn13_sum(digits) % 10 == 0


def check_char(scheme, digits):
    if scheme == "luhn":
        return str(next(c for c in range(10) if luhn_sum(digits + [c]) % 10 == 0))
    if scheme == "isbn10":
        c = (11 - isbn10_sum(digits) % 11) % 11
        return "X" if c == 10 else str(c)
    return str((10 - isbn13_sum(digits) % 10) % 10)


def main(argv):
    if len(argv) < 3 or argv[0] not in SCHEMES or argv[1] not in MODES:
        print("usage: checkdigit luhn|isbn10|isbn13 check|make VALUE...", file=sys.stderr)
        return 2
    scheme, mode, values = argv[0], argv[1], argv[2:]
    all_good = True
    for value in values:
        digits = parse_digits(value, scheme, mode)
        if digits is None:
            print(f"{value} invalid")
            all_good = False
        elif mode == "check":
            if is_correct(scheme, digits):
                print(f"{value} ok")
            else:
                print(f"{value} bad")
                all_good = False
        else:
            sep = "-" if "-" in value else ""
            print(f"{value}{sep}{check_char(scheme, digits)}")
    return 0 if all_good else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
