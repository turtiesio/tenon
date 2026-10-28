import itertools
import re
import sys


def main():
    flags = set()
    skips = {'-f': 0, '-s': 0}
    args = iter(sys.argv[1:])
    try:
        for arg in args:
            if arg in ('-c', '-d', '-u', '-i'):
                flags.add(arg)
            elif arg in skips:
                value = next(args)
                if not re.fullmatch(r'[0-9]{1,4}', value):
                    raise ValueError
                skips[arg] = int(value)
            else:
                raise ValueError
    except (ValueError, StopIteration):
        print('Invalid arguments', file=sys.stderr)
        return 2

    def key(line):
        position = 0
        for _ in range(skips['-f']):
            while position < len(line) and line[position] in ' \t':
                position += 1
            while position < len(line) and line[position] not in ' \t':
                position += 1
            if position == len(line):
                break
        result = line[position + skips['-s']:]
        return result.lower() if '-i' in flags else result

    data = sys.stdin.buffer.read().decode('ascii')
    lines = data.split('\n') if data else []
    if data.endswith('\n'):
        lines.pop()
    lines = [line[:-1] if line.endswith('\r') else line for line in lines]
    for _, group in itertools.groupby(lines, key):
        first = next(group)
        count = 1 + sum(1 for _ in group)
        if '-d' in flags and count < 2 or '-u' in flags and count != 1:
            continue
        print((f'{count:7d} ' if '-c' in flags else '') + first)
    return 0


if __name__ == '__main__':
    sys.exit(main())
