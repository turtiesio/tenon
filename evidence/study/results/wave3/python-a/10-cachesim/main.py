import re
import sys
from collections import OrderedDict

GEOMETRY = re.compile(r"([0-9]{1,4}):([0-9]{1,2})")
BLOCK_SIZE = re.compile(r"[0-9]{1,4}")
ACCESS = re.compile(r"([RW]) 0x([0-9a-fA-F]{1,8})")


class UsageError(Exception):
    pass


class TraceError(Exception):
    pass


class Cache:
    """Set-associative LRU cache; each set maps block -> dirty, LRU first."""

    def __init__(self, sets, ways):
        self.sets = sets
        self.ways = ways
        self.data = [OrderedDict() for _ in range(sets)]
        self.hits = self.misses = self.writebacks = 0

    def _set(self, block):
        return self.data[block % self.sets]

    def lookup(self, block):
        """Return True and make the block MRU if it is present."""
        s = self._set(block)
        if block in s:
            s.move_to_end(block)
            return True
        return False

    def mark_dirty(self, block):
        self._set(block)[block] = True

    def install(self, block, dirty):
        """Install block as MRU; return the dirty victim's block, or None."""
        s = self._set(block)
        victim = None
        if len(s) >= self.ways:
            old, old_dirty = s.popitem(last=False)
            if old_dirty:
                victim = old
        s[block] = dirty
        return victim


class Hierarchy:
    def __init__(self, l1, l2):
        self.l1 = l1
        self.l2 = l2

    def install_l2(self, block, dirty):
        if self.l2.install(block, dirty) is not None:
            self.l2.writebacks += 1

    def access(self, block, is_write):
        l1, l2 = self.l1, self.l2
        if l1.lookup(block):
            l1.hits += 1
            if is_write:
                l1.mark_dirty(block)
            return "L1"
        l1.misses += 1
        if l2.lookup(block):
            l2.hits += 1
            result = "L2"
        else:
            l2.misses += 1
            self.install_l2(block, False)
            result = "MEM"
        victim = l1.install(block, is_write)
        if victim is not None:
            l1.writebacks += 1
            if l2.lookup(victim):
                l2.mark_dirty(victim)
            else:
                self.install_l2(victim, True)
        return result


def parse_geometry(text):
    m = GEOMETRY.fullmatch(text)
    if not m:
        raise UsageError(f"bad geometry {text!r}")
    sets, ways = int(m.group(1)), int(m.group(2))
    if not (1 <= sets <= 4096 and 1 <= ways <= 64):
        raise UsageError(f"geometry out of range: {text!r}")
    return sets, ways


def parse_block_size(text):
    if not BLOCK_SIZE.fullmatch(text):
        raise UsageError(f"bad block size {text!r}")
    size = int(text)
    if not (1 <= size <= 4096) or size & (size - 1):
        raise UsageError(f"block size must be a power of two in 1..4096: {text!r}")
    return size


def parse_args(argv):
    block = 16
    l1 = (4, 2)
    l2 = (16, 4)
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg not in ("-b", "-1", "-2"):
            raise UsageError(f"unexpected argument {arg!r}")
        if i + 1 >= len(argv):
            raise UsageError(f"{arg} needs a value")
        value = argv[i + 1]
        if arg == "-b":
            block = parse_block_size(value)
        elif arg == "-1":
            l1 = parse_geometry(value)
        else:
            l2 = parse_geometry(value)
        i += 2
    return block, l1, l2


def parse_trace(text):
    """Return a list of (is_write, address, original text of the access)."""
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    accesses = []
    for number, line in enumerate(lines, 1):
        if line.endswith("\r"):
            line = line[:-1]
        if not line.strip(" "):
            continue
        m = ACCESS.fullmatch(line)
        if not m:
            raise TraceError(f"line {number}: bad access {line!r}")
        accesses.append((m.group(1) == "W", int(m.group(2), 16), line))
    return accesses


def main():
    try:
        block_size, l1_geometry, l2_geometry = parse_args(sys.argv[1:])
    except UsageError as e:
        print(f"cachesim: {e}", file=sys.stderr)
        print("usage: cachesim [-b BLOCK] [-1 SETS:WAYS] [-2 SETS:WAYS]",
              file=sys.stderr)
        return 2
    try:
        accesses = parse_trace(sys.stdin.buffer.read().decode("latin-1"))
    except TraceError as e:
        print(f"cachesim: {e}", file=sys.stderr)
        return 1

    hierarchy = Hierarchy(Cache(*l1_geometry), Cache(*l2_geometry))
    out = []
    for is_write, address, text in accesses:
        result = hierarchy.access(address // block_size, is_write)
        out.append(f"{text} {result}\n")
    for name, cache in (("L1", hierarchy.l1), ("L2", hierarchy.l2)):
        out.append(f"{name} hits={cache.hits} misses={cache.misses} "
                   f"writebacks={cache.writebacks}\n")
    sys.stdout.write("".join(out))
    return 0


sys.exit(main())
