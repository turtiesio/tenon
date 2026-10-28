"""cachesim: two-level cache hierarchy simulator."""
import re
import sys
from collections import OrderedDict

BLOCK = re.compile(r"[0-9]{1,4}")
GEOMETRY = re.compile(r"([0-9]{1,4}):([0-9]{1,2})")
ACCESS = re.compile(r"([RW]) 0x([0-9A-Fa-f]{1,8})")


class UsageError(Exception):
    pass


class TraceError(Exception):
    pass


def parse_block(text):
    if BLOCK.fullmatch(text):
        size = int(text)
        if 1 <= size <= 4096 and size & (size - 1) == 0:
            return size
    raise UsageError(f"bad block size {text!r}")


def parse_geometry(text):
    m = GEOMETRY.fullmatch(text)
    if m:
        sets, ways = int(m.group(1)), int(m.group(2))
        if 1 <= sets <= 4096 and 1 <= ways <= 64:
            return sets, ways
    raise UsageError(f"bad geometry {text!r}")


def parse_args(argv):
    config = {"-b": 16, "-1": (4, 2), "-2": (16, 4)}
    parsers = {"-b": parse_block, "-1": parse_geometry, "-2": parse_geometry}
    i = 0
    while i < len(argv):
        option = argv[i]
        if option not in parsers:
            raise UsageError(f"unexpected argument {option!r}")
        if i + 1 >= len(argv):
            raise UsageError(f"option {option} needs a value")
        config[option] = parsers[option](argv[i + 1])
        i += 2
    return config["-b"], config["-1"], config["-2"]


def parse_trace(data):
    lines = data.split("\n")
    if lines[-1] == "":
        lines.pop()
    accesses = []
    for number, line in enumerate(lines, start=1):
        if line.endswith("\r"):
            line = line[:-1]
        if not line.strip(" "):
            continue
        m = ACCESS.fullmatch(line)
        if not m:
            raise TraceError(f"line {number}: invalid access {line!r}")
        accesses.append((line, m.group(1), int(m.group(2), 16)))
    return accesses


class Cache:
    """A set-associative LRU cache. Each set maps block -> dirty, LRU first."""

    def __init__(self, sets, ways):
        self.ways = ways
        self.sets = [OrderedDict() for _ in range(sets)]
        self.hits = 0
        self.misses = 0
        self.writebacks = 0

    def set_of(self, block):
        return self.sets[block % len(self.sets)]

    def touch(self, block, dirty=False):
        """If the block is held, make it MRU (OR-ing in dirty) and return True."""
        s = self.set_of(block)
        if block not in s:
            return False
        s.move_to_end(block)
        if dirty:
            s[block] = True
        return True

    def install(self, block, dirty):
        """Add the block as MRU; return the victim (block, dirty) or None."""
        s = self.set_of(block)
        victim = s.popitem(last=False) if len(s) >= self.ways else None
        s[block] = dirty
        return victim


class Hierarchy:
    def __init__(self, block_size, l1, l2):
        self.block_size = block_size
        self.l1 = Cache(*l1)
        self.l2 = Cache(*l2)

    def install_l2(self, block, dirty):
        victim = self.l2.install(block, dirty)
        if victim and victim[1]:
            self.l2.writebacks += 1

    def access(self, op, address):
        block = address // self.block_size
        write = op == "W"
        if self.l1.touch(block, dirty=write):
            self.l1.hits += 1
            return "L1"
        self.l1.misses += 1
        if self.l2.touch(block):
            self.l2.hits += 1
            result = "L2"
        else:
            self.l2.misses += 1
            self.install_l2(block, dirty=False)
            result = "MEM"
        victim = self.l1.install(block, dirty=write)
        if victim and victim[1]:
            self.l1.writebacks += 1
            if not self.l2.touch(victim[0], dirty=True):
                self.install_l2(victim[0], dirty=True)
        return result


def main():
    try:
        block_size, l1, l2 = parse_args(sys.argv[1:])
    except UsageError as e:
        print(f"cachesim: {e}", file=sys.stderr)
        return 2
    try:
        accesses = parse_trace(sys.stdin.buffer.read().decode("latin-1"))
    except TraceError as e:
        print(f"cachesim: {e}", file=sys.stderr)
        return 1
    sim = Hierarchy(block_size, l1, l2)
    out = [f"{line} {sim.access(op, address)}" for line, op, address in accesses]
    for name, cache in (("L1", sim.l1), ("L2", sim.l2)):
        out.append(f"{name} hits={cache.hits} misses={cache.misses} writebacks={cache.writebacks}")
    sys.stdout.write("".join(line + "\n" for line in out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
