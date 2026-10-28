"""cidrmerge: merge IPv4 address blocks."""
import re
import sys

NUM = r"(0|[1-9][0-9]*)"
ENTRY = re.compile(rf"{NUM}\.{NUM}\.{NUM}\.{NUM}(?:/{NUM})?")


def parse_entry(line):
    """Return (start, end) inclusive for a valid entry, or None if it is bad."""
    m = ENTRY.fullmatch(line)
    if not m:
        return None
    octets = [int(g) for g in m.groups()[:4]]
    if any(o > 255 for o in octets):
        return None
    prefix = 32 if m.group(5) is None else int(m.group(5))
    if prefix > 32:
        return None
    address = (octets[0] << 24) | (octets[1] << 16) | (octets[2] << 8) | octets[3]
    size = 1 << (32 - prefix)
    if address % size:
        return None
    return address, address + size - 1


def merge(blocks):
    """Merge inclusive (start, end) pairs into maximal disjoint ranges."""
    ranges = []
    for start, end in sorted(blocks):
        if ranges and start <= ranges[-1][1] + 1:
            if end > ranges[-1][1]:
                ranges[-1][1] = end
        else:
            ranges.append([start, end])
    return ranges


def split_into_blocks(start, end):
    """Cover start..end (inclusive) greedily with the fewest CIDR blocks."""
    blocks = []
    while start <= end:
        prefix = 0
        while True:
            size = 1 << (32 - prefix)
            if start % size == 0 and start + size - 1 <= end:
                break
            prefix += 1
        blocks.append((start, prefix))
        start += 1 << (32 - prefix)
    return blocks


def dotted(address):
    return ".".join(str((address >> shift) & 0xFF) for shift in (24, 16, 8, 0))


def read_lines(data):
    if not data:
        return []
    lines = data.split("\n")
    if data.endswith("\n"):
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def main(argv):
    if argv not in ([], ["-r"]):
        print("usage: cidrmerge [-r]", file=sys.stderr)
        return 2
    as_ranges = argv == ["-r"]

    text = sys.stdin.buffer.read().decode("latin-1")
    status = 0
    blocks = []
    for number, line in enumerate(read_lines(text), start=1):
        if line == "" or line.startswith("#"):
            continue
        entry = parse_entry(line)
        if entry is None:
            print(f"cidrmerge: line {number}: bad entry {line!r}", file=sys.stderr)
            status = 1
            continue
        blocks.append(entry)

    out = []
    for start, end in merge(blocks):
        if as_ranges:
            out.append(f"{dotted(start)}-{dotted(end)} {end - start + 1}\n")
        else:
            for address, prefix in split_into_blocks(start, end):
                out.append(f"{dotted(address)}/{prefix}\n")
    sys.stdout.write("".join(out))
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
