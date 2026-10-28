"""globgrep: filter lines with a shell-style wildcard pattern."""
import sys


class UsageError(Exception):
    pass


class PatternError(Exception):
    pass


# Pattern elements:
#   ("star",)                    any sequence
#   ("any",)                     exactly one character
#   ("lit", c)                   the character c
#   ("class", negated, ranges)   ranges is a list of (low, high) characters


def parse_class(pattern, i):
    """Parse a class starting just after '['. Returns (element, next index)."""
    negated = False
    if i < len(pattern) and pattern[i] == "!":
        negated = True
        i += 1
    ranges = []
    first = True

    def class_char(j):
        if j >= len(pattern):
            raise PatternError("unterminated class")
        if pattern[j] == "\\":
            if j + 1 >= len(pattern):
                raise PatternError("unterminated class")
            return pattern[j + 1], j + 2
        return pattern[j], j + 1

    while True:
        if i >= len(pattern):
            raise PatternError("unterminated class")
        if pattern[i] == "]" and not first:
            return ("class", negated, ranges), i + 1
        first = False
        low, i = class_char(i)
        if i + 1 < len(pattern) and pattern[i] == "-" and pattern[i + 1] != "]":
            high, i = class_char(i + 1)
            if low > high:
                raise PatternError(f"invalid range {low}-{high}")
            ranges.append((low, high))
        else:
            ranges.append((low, low))


def compile_pattern(pattern):
    elements = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "*":
            elements.append(("star",))
            i += 1
        elif c == "?":
            elements.append(("any",))
            i += 1
        elif c == "\\":
            if i + 1 >= len(pattern):
                raise PatternError("trailing backslash")
            elements.append(("lit", pattern[i + 1]))
            i += 2
        elif c == "[":
            element, i = parse_class(pattern, i + 1)
            elements.append(element)
        else:
            elements.append(("lit", c))
            i += 1
    return elements


def ascii_lower(c):
    return chr(ord(c) + 32) if "A" <= c <= "Z" else c


def ascii_upper(c):
    return chr(ord(c) - 32) if "a" <= c <= "z" else c


def in_ranges(c, ranges):
    return any(low <= c <= high for low, high in ranges)


def element_matches(element, c, fold):
    kind = element[0]
    if kind == "any":
        return True
    if kind == "lit":
        if fold:
            return ascii_lower(element[1]) == ascii_lower(c)
        return element[1] == c
    _, negated, ranges = element
    if fold:
        found = in_ranges(ascii_lower(c), ranges) or in_ranges(ascii_upper(c), ranges)
    else:
        found = in_ranges(c, ranges)
    return found != negated


def matches(elements, line, fold):
    """NFA simulation: the set of pattern positions reachable after each character."""
    n = len(elements)

    def close(states):
        # A star may match the empty sequence, so skip past it.
        result = set()
        stack = list(states)
        while stack:
            k = stack.pop()
            if k in result:
                continue
            result.add(k)
            if k < n and elements[k][0] == "star":
                stack.append(k + 1)
        return result

    states = close({0})
    for c in line:
        following = set()
        for k in states:
            if k == n:
                continue
            element = elements[k]
            if element[0] == "star":
                following.add(k)
            elif element_matches(element, c, fold):
                following.add(k + 1)
        if not following:
            return False
        states = close(following)
    return n in states


def parse_args(argv):
    flags = set()
    pattern = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if pattern is not None:
            raise UsageError(f"unexpected argument {arg!r}")
        if arg in ("-i", "-v", "-c"):
            flags.add(arg)
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
    return flags, pattern


def read_lines(data):
    lines = data.split("\n")
    if lines[-1] == "":
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def main():
    try:
        flags, pattern = parse_args(sys.argv[1:])
        elements = compile_pattern(pattern)
    except (UsageError, PatternError) as e:
        print(f"globgrep: {e}", file=sys.stderr)
        return 2
    fold = "-i" in flags
    invert = "-v" in flags
    lines = read_lines(sys.stdin.buffer.read().decode("latin-1"))
    selected = [line for line in lines if matches(elements, line, fold) != invert]
    if "-c" in flags:
        print(len(selected))
    else:
        sys.stdout.write("".join(line + "\n" for line in selected))
    return 0 if selected else 1


if __name__ == "__main__":
    sys.exit(main())
