import re
import sys


def format_size(value, base, precision):
    if value < base:
        return f'{value} B'
    units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB'] if base == 1024 else ['B', 'kB', 'MB', 'GB', 'TB', 'PB']
    k = 1
    while k < 5 and value >= base ** (k + 1):
        k += 1
    scale = 10 ** precision
    while True:
        divisor = base ** k
        rounded = (2 * value * scale + divisor) // (2 * divisor)
        if rounded < base * scale or k == 5:
            break
        k += 1
    number = str(rounded // scale)
    if precision:
        number += f'.{rounded % scale:0{precision}d}'
    return f'{number} {units[k]}'


def main():
    base, precision = 1024, 1
    sizes = []
    args = iter(sys.argv[1:])
    for arg in args:
        if arg == '-s':
            base = 1000
        elif arg == '-p':
            value = next(args, '')
            if value not in ('0', '1', '2'):
                print('invalid precision', file=sys.stderr)
                return 2
            precision = int(value)
        elif re.fullmatch(r'[0-9]{1,16}', arg):
            sizes.append(arg)
        else:
            print(f'invalid argument: {arg}', file=sys.stderr)
            return 2
    if not sizes:
        data = sys.stdin.buffer.read().decode('ascii')
        sizes = data.split('\n') if data else []
        if sizes and sizes[-1] == '' and data.endswith('\n'):
            sizes.pop()
        sizes = [line[:-1] if line.endswith('\r') else line for line in sizes]
    status = 0
    for size in sizes:
        if re.fullmatch(r'[0-9]{1,16}', size):
            print(format_size(int(size), base, precision))
        else:
            print('?')
            status = 1
    return status


if __name__ == '__main__':
    sys.exit(main())
