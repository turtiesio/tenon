"""Private specification reference: adjacent-line grouping."""
import re
import sys

def main():
    flags = set()
    fields = chars = 0
    args = iter(sys.argv[1:])
    try:
        for arg in args:
            if arg in ('-c', '-d', '-u', '-i'):
                flags.add(arg)
            elif arg in ('-f', '-s'):
                n = next(args)
                if not re.fullmatch(r'[0-9]{1,4}', n):
                    raise ValueError()
                if arg == '-f': fields = int(n)
                else: chars = int(n)
            else:
                raise ValueError()
    except (ValueError, StopIteration):
        print('usage error', file=sys.stderr)
        return 2
    raw = sys.stdin.buffer.read().split(b'\n')
    if raw[-1] == b'': raw.pop()
    groups = []
    for line in raw:
        if line.endswith(b'\r'): line = line[:-1]
        pos = 0
        for _ in range(fields):
            while pos < len(line) and line[pos] in (32, 9): pos += 1
            while pos < len(line) and line[pos] not in (32, 9): pos += 1
        key = line[pos+chars:]
        if '-i' in flags: key = key.lower()
        if groups and groups[-1][0] == key:
            groups[-1][2] += 1
        else:
            groups.append([key, line, 1])
    for _, line, count in groups:
        if ('-d' in flags and count < 2) or ('-u' in flags and count != 1): continue
        prefix = f'{count:7d} '.encode() if '-c' in flags else b''
        sys.stdout.buffer.write(prefix+line+b'\n')
    return 0

if __name__ == '__main__': sys.exit(main())
