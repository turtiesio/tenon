#!/usr/bin/env python3
"""lfagg: group logfmt lines by a key and aggregate a numeric field."""

import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field

KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
NUMERIC_RE = re.compile(r"-?[0-9]{1,15}")


class Malformed(Exception):
    pass


def parse_quoted(line, pos):
    """Parse a quoted value starting after the opening quote.

    Return (value, position after the closing quote).
    """
    chars = []
    while pos < len(line):
        c = line[pos]
        if c == '"':
            return "".join(chars), pos + 1
        if c == "\\":
            if pos + 1 >= len(line) or line[pos + 1] not in '"\\':
                raise Malformed("bad escape")
            chars.append(line[pos + 1])
            pos += 2
        else:
            chars.append(c)
            pos += 1
    raise Malformed("missing closing quote")


def parse_line(line):
    """Parse a non-blank logfmt line into a dict; raise Malformed on error."""
    pairs = {}
    pos, end = 0, len(line)
    while True:
        while pos < end and line[pos] == " ":
            pos += 1
        if pos >= end:
            return pairs
        m = KEY_RE.match(line, pos)
        if not m:
            raise Malformed("bad key")
        key, pos = m[0], m.end()
        if key in pairs:
            raise Malformed("duplicate key")

        if pos >= end or line[pos] == " ":
            pairs[key] = "true"
        elif line[pos] == "=":
            pos += 1
            if pos < end and line[pos] == '"':
                value, pos = parse_quoted(line, pos + 1)
                if pos < end and line[pos] != " ":
                    raise Malformed("junk after closing quote")
            else:
                start = pos
                while pos < end and line[pos] != " ":
                    pos += 1
                value = line[start:pos]
                if '"' in value or "=" in value:
                    raise Malformed("bad bare value")
            pairs[key] = value
        else:
            raise Malformed("junk after key")


@dataclass
class Group:
    count: int = 0
    numbers: list = field(default_factory=list)


def format_average(total, n):
    """total / n rounded half away from zero to 2 decimals, as text."""
    hundredths = (2 * abs(total) * 100 + n) // (2 * n)
    if total < 0 and hundredths:
        hundredths = -hundredths
    sign = "-" if hundredths < 0 else ""
    whole, frac = divmod(abs(hundredths), 100)
    return f"{sign}{whole}.{frac:02d}"


def format_group(name, group, with_field):
    label = name if name else '""'
    if not with_field:
        return f"{label} count={group.count}"
    nums = group.numbers
    if not nums:
        return f"{label} count={group.count} n=0 sum=0 min=- max=- avg=-"
    total = sum(nums)
    return (
        f"{label} count={group.count} n={len(nums)} sum={total} "
        f"min={min(nums)} max={max(nums)} avg={format_average(total, len(nums))}"
    )


def main(argv):
    if len(argv) not in (1, 2) or not all(KEY_RE.fullmatch(a) for a in argv):
        print("usage: lfagg BY [FIELD]", file=sys.stderr)
        return 2
    by = argv[0]
    value_field = argv[1] if len(argv) == 2 else None

    text = sys.stdin.buffer.read().decode("latin-1")
    groups = defaultdict(Group)
    valid = malformed = nokey = 0

    for line in text.split("\n"):
        if line.endswith("\r"):
            line = line[:-1]
        if line.strip(" ") == "":
            continue
        try:
            pairs = parse_line(line)
        except Malformed:
            malformed += 1
            continue
        valid += 1
        if by not in pairs:
            nokey += 1
            continue
        group = groups[pairs[by]]
        group.count += 1
        if value_field is not None:
            raw = pairs.get(value_field)
            if raw is not None and NUMERIC_RE.fullmatch(raw):
                group.numbers.append(int(raw))

    ordered = sorted(groups.items(), key=lambda kv: (-kv[1].count, kv[0].encode("latin-1")))
    out = [format_group(name, group, value_field is not None) for name, group in ordered]
    out.append(f"lines={valid} malformed={malformed} nokey={nokey}")
    sys.stdout.write("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
