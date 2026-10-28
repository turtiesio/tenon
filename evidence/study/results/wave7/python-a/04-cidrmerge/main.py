import re
import sys

NUM_RE = r"(0|[1-9][0-9]{0,2})"
ENTRY_RE = re.compile(rf"{NUM_RE}\.{NUM_RE}\.{NUM_RE}\.{NUM_RE}(?:/(0|[1-9][0-9]?))?")
ADDRESS_SPACE = 1 << 32


def parse_entry(line):
    """Return (start, end) inclusive for a valid entry, or raise ValueError."""
    m = ENTRY_RE.fullmatch(line)
    if m is None:
        raise ValueError("not an address or block")
    octets = [int(m.group(i)) for i in range(1, 5)]
    if any(o > 255 for o in octets):
        raise ValueError("octet above 255")
    prefix = 32 if m.group(5) is None else int(m.group(5))
    if prefix > 32:
        raise ValueError("prefix above 32")
    address = (octets[0] << 24) | (octets[1] << 16) | (octets[2] << 8) | octets[3]
    size = 1 << (32 - prefix)
    if address % size != 0:
        raise ValueError("non-zero bits after the prefix")
    return address, address + size - 1


def dotted(n):
    return ".".join(str((n >> shift) & 255) for shift in (24, 16, 8, 0))


def merge(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1] + 1:
            if end > merged[-1][1]:
                merged[-1][1] = end
        else:
            merged.append([start, end])
    return merged


def blocks(start, end):
    """Fewest CIDR blocks covering start..end, greedily."""
    while start <= end:
        size = start & -start if start else ADDRESS_SPACE
        while size > end - start + 1:
            size >>= 1
        yield start, 32 - (size.bit_length() - 1)
        start += size


def main():
    args = sys.argv[1:]
    if args not in ([], ["-r"]):
        print("usage: cidrmerge [-r]", file=sys.stderr)
        return 2
    ranges_mode = bool(args)

    text = sys.stdin.buffer.read().decode("ascii", errors="replace")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()

    intervals = []
    bad = False
    for number, line in enumerate(lines, start=1):
        if line.endswith("\r"):
            line = line[:-1]
        if line == "" or line.startswith("#"):
            continue
        try:
            intervals.append(parse_entry(line))
        except ValueError as e:
            print(f"cidrmerge: line {number}: {e}: {line!r}", file=sys.stderr)
            bad = True

    out = []
    for start, end in merge(intervals):
        if ranges_mode:
            out.append(f"{dotted(start)}-{dotted(end)} {end - start + 1}")
        else:
            out.extend(f"{dotted(s)}/{p}" for s, p in blocks(start, end))

    sys.stdout.write("".join(line + "\n" for line in out))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
