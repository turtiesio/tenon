import re
import sys


def main(args):
    separator = '\n'
    width = False
    limit = None
    numbers = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ('-s', '-n'):
            i += 1
            if i == len(args):
                raise ValueError('missing option value')
            if arg == '-s':
                separator = args[i]
            else:
                if not re.fullmatch(r'[0-9]{1,9}', args[i]):
                    raise ValueError('invalid count')
                limit = int(args[i])
        elif arg == '-w':
            width = True
        else:
            if not re.fullmatch(r'-?[0-9]{1,18}', arg):
                raise ValueError('invalid number')
            numbers.append(int(arg))
        i += 1
    if len(numbers) == 2:
        first, last = numbers
        step = 1
    elif len(numbers) == 3:
        first, step, last = numbers
    else:
        raise ValueError('expected two or three numbers')
    if step == 0:
        raise ValueError('zero step')
    count = max(0, (last - first) // step + 1)
    if limit is not None:
        count = min(count, limit)
    values = [str(first + i * step) for i in range(count)]
    if values:
        if width:
            size = max(map(len, values))
            values = [value.zfill(size) for value in values]
        print(separator.join(values))


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except ValueError as error:
        print(error, file=sys.stderr)
        sys.exit(2)
