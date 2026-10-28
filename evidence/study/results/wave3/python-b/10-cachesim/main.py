import re
import sys
from collections import OrderedDict


class Cache:
    def __init__(self, sets, ways, lower=None):
        self.sets = [OrderedDict() for _ in range(sets)]
        self.ways = ways
        self.lower = lower
        self.hits = 0
        self.misses = 0
        self.writebacks = 0

    def lookup(self, block, dirty=False):
        bucket = self.sets[block % len(self.sets)]
        if block not in bucket:
            self.misses += 1
            return False
        self.hits += 1
        bucket[block] |= dirty
        bucket.move_to_end(block)
        return True

    def install(self, block, dirty):
        bucket = self.sets[block % len(self.sets)]
        if len(bucket) == self.ways:
            victim, was_dirty = bucket.popitem(last=False)
            if was_dirty:
                self.writebacks += 1
                if self.lower is not None:
                    self.lower.writeback(victim)
        bucket[block] = dirty

    def writeback(self, block):
        bucket = self.sets[block % len(self.sets)]
        if block in bucket:
            bucket[block] = True
            bucket.move_to_end(block)
        else:
            self.install(block, True)

    def summary(self, name):
        return f'{name} hits={self.hits} misses={self.misses} writebacks={self.writebacks}'


def main():
    block_size = 16
    geometries = {'-1': (4, 2), '-2': (16, 4)}
    args = iter(sys.argv[1:])
    try:
        for arg in args:
            if arg not in ('-b', '-1', '-2'):
                raise ValueError()
            value = next(args)
            if arg == '-b':
                if not re.fullmatch('[0-9]{1,4}', value):
                    raise ValueError()
                block_size = int(value)
                if not 1 <= block_size <= 4096 or block_size & (block_size - 1):
                    raise ValueError()
            else:
                if not re.fullmatch('[0-9]{1,4}:[0-9]{1,2}', value):
                    raise ValueError()
                sets, ways = map(int, value.split(':'))
                if not 1 <= sets <= 4096 or not 1 <= ways <= 64:
                    raise ValueError()
                geometries[arg] = sets, ways
    except (ValueError, StopIteration):
        print('invalid arguments', file=sys.stderr)
        return 2
    trace = []
    for number, raw in enumerate(sys.stdin.buffer.read().split(b'\n'), 1):
        line = raw.removesuffix(b'\r')
        if not line.strip(b' '):
            continue
        if not re.fullmatch(rb'[RW] 0x[0-9A-Fa-f]{1,8}', line):
            print(f'invalid trace on line {number}', file=sys.stderr)
            return 1
        trace.append(line.decode('ascii'))
    l2 = Cache(*geometries['-2'])
    l1 = Cache(*geometries['-1'], lower=l2)
    output = []
    for line in trace:
        block = int(line[2:], 16) // block_size
        dirty = line[0] == 'W'
        if l1.lookup(block, dirty):
            result = 'L1'
        else:
            if l2.lookup(block):
                result = 'L2'
            else:
                result = 'MEM'
                l2.install(block, False)
            l1.install(block, dirty)
        output.append(line + ' ' + result)
    output.extend((l1.summary('L1'), l2.summary('L2')))
    print('\n'.join(output))
    return 0


if __name__ == '__main__':
    sys.exit(main())
