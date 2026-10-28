import bisect
import re
import sys


def main():
    stops, leading_only, files = [8], False, []
    args = iter(sys.argv[1:])
    try:
        for arg in args:
            if arg == '-i':
                leading_only = True
            elif arg == '-t':
                value = next(args)
                if not re.fullmatch(r'[1-9][0-9]{0,3}(,[1-9][0-9]{0,3})*', value):
                    raise ValueError('invalid stops')
                stops = list(map(int, value.split(',')))
                if any(a >= b for a, b in zip(stops, stops[1:])):
                    raise ValueError('stops must increase')
            elif arg.startswith('-'):
                raise ValueError('unknown option')
            else:
                files.append(arg)
    except (ValueError, StopIteration) as exc:
        print('usage error:', exc, file=sys.stderr)
        return 2
    failed = False
    chunks = []
    if not files:
        chunks.append(sys.stdin.buffer.read().decode('utf-8'))
    for filename in files:
        try:
            with open(filename, 'rb') as source:
                chunks.append(source.read().decode('utf-8'))
        except OSError as exc:
            print(exc, file=sys.stderr)
            failed = True
    column, leading = 0, True
    output = []
    for chunk in chunks:
        for char in chunk:
            if char == '\n':
                output.append(char)
                column, leading = 0, True
                continue
            if char == '\t' and (not leading_only or leading):
                if len(stops) == 1:
                    count = stops[0] - column % stops[0]
                else:
                    index = bisect.bisect_right(stops, column)
                    count = stops[index] - column if index < len(stops) else 1
                output.append(' ' * count)
                column += count
            else:
                output.append(char)
                column += 1
            if char not in (' ', '\t'):
                leading = False
    sys.stdout.buffer.write(''.join(output).encode('utf-8'))
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
