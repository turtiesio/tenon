import os
import sys

STAR = "star"
ANY = "any"
LIT = "lit"
CLASS = "class"


class UsageError(Exception):
    pass


class PatternError(Exception):
    pass


def lower(c):
    return chr(ord(c) + 32) if "A" <= c <= "Z" else c


def upper(c):
    return chr(ord(c) - 32) if "a" <= c <= "z" else c


def parse_class(pattern, i):
    """Parse a class whose '[' is at pattern[i-1]. Returns (element, next index)."""
    n = len(pattern)
    negated = i < n and pattern[i] == "!"
    if negated:
        i += 1

    def class_char(i):
        if i >= n:
            raise PatternError("unterminated class")
        if pattern[i] == "\\":
            if i + 1 >= n:
                raise PatternError("unterminated class")
            return pattern[i + 1], i + 2
        return pattern[i], i + 1

    ranges = []
    first = True
    while True:
        if i >= n:
            raise PatternError("unterminated class")
        if pattern[i] == "]" and not first:
            return (CLASS, negated, ranges), i + 1
        first = False
        lo, i = class_char(i)
        hi = lo
        if i + 1 < n and pattern[i] == "-" and pattern[i + 1] != "]":
            hi, i = class_char(i + 1)
            if lo > hi:
                raise PatternError(f"reversed range {lo}-{hi}")
        ranges.append((lo, hi))


def compile_pattern(pattern):
    elements = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        i += 1
        if c == "*":
            if not elements or elements[-1] != (STAR,):
                elements.append((STAR,))
        elif c == "?":
            elements.append((ANY,))
        elif c == "\\":
            if i >= len(pattern):
                raise PatternError("trailing backslash")
            elements.append((LIT, pattern[i]))
            i += 1
        elif c == "[":
            element, i = parse_class(pattern, i)
            elements.append(element)
        else:
            elements.append((LIT, c))
    return elements


def in_ranges(c, ranges):
    return any(lo <= c <= hi for lo, hi in ranges)


def element_matches(element, c, ignore_case):
    kind = element[0]
    if kind == ANY:
        return True
    if kind == LIT:
        return lower(c) == lower(element[1]) if ignore_case else c == element[1]
    _, negated, ranges = element
    found = in_ranges(c, ranges)
    if ignore_case:
        found = found or in_ranges(lower(c), ranges) or in_ranges(upper(c), ranges)
    return found != negated


def matches(elements, line, ignore_case):
    """Whole-line match by simulating the pattern as an NFA: O(pattern * line)."""
    count = len(elements)

    def close(states):
        result = set(states)
        for s in states:
            if s < count and elements[s] == (STAR,):
                result.add(s + 1)
        return result

    states = close({0})
    for c in line:
        next_states = set()
        for s in states:
            if s >= count:
                continue
            element = elements[s]
            if element == (STAR,):
                next_states.add(s)
            elif element_matches(element, c, ignore_case):
                next_states.add(s + 1)
        states = close(next_states)
        if not states:
            return False
    return count in states


def parse_args(argv):
    ignore_case = invert = count_only = False
    pattern = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if pattern is not None:
            raise UsageError(f"unexpected argument {arg!r}")
        if arg == "-i":
            ignore_case = True
        elif arg == "-v":
            invert = True
        elif arg == "-c":
            count_only = True
        elif arg == "--":
            if i + 1 >= len(argv):
                raise UsageError("missing PATTERN")
            pattern = argv[i + 1]
            i += 1
        elif arg.startswith("-"):
            raise UsageError(f"unknown option {arg!r}")
        else:
            pattern = arg
        i += 1
    if pattern is None:
        raise UsageError("missing PATTERN")
    return ignore_case, invert, count_only, pattern


def main():
    try:
        ignore_case, invert, count_only, pattern = parse_args(sys.argv[1:])
        # latin-1 keeps one character per byte, so ordering is by byte value
        elements = compile_pattern(os.fsencode(pattern).decode("latin-1"))
    except UsageError as e:
        print(f"globgrep: {e}", file=sys.stderr)
        print("usage: globgrep [-i] [-v] [-c] [--] PATTERN", file=sys.stderr)
        return 2
    except PatternError as e:
        print(f"globgrep: invalid pattern: {e}", file=sys.stderr)
        return 2

    text = sys.stdin.buffer.read().decode("latin-1")
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()

    selected = []
    for line in lines:
        if line.endswith("\r"):
            line = line[:-1]
        if matches(elements, line, ignore_case) != invert:
            selected.append(line)

    if count_only:
        print(len(selected))
    else:
        out = sys.stdout.buffer
        for line in selected:
            out.write(line.encode("latin-1") + b"\n")
        out.flush()
    return 0 if selected else 1


sys.exit(main())
