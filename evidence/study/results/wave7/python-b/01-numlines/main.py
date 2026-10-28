import re
import sys


def main():
    opts = {'-b': 't', '-w': '6', '-s': '\t', '-v': '1', '-i': '1', '-f': 'rn'}
    filename = None
    args = iter(sys.argv[1:])
    try:
        for arg in args:
            if arg in opts:
                opts[arg] = next(args)
            elif arg.startswith('-') or filename is not None:
                raise ValueError('invalid argument')
            else:
                filename = arg
        if opts['-b'] not in ('a', 't', 'n') or opts['-f'] not in ('ln', 'rn', 'rz'):
            raise ValueError('invalid style or format')
        if not re.fullmatch(r'[1-9][0-9]?', opts['-w']) or int(opts['-w']) > 20:
            raise ValueError('invalid width')
        for key in ('-v', '-i'):
            if not re.fullmatch(r'-?[0-9]{1,9}', opts[key]):
                raise ValueError('invalid number')
    except (ValueError, StopIteration) as exc:
        print('usage error:', exc, file=sys.stderr)
        return 2
    try:
        if filename is None:
            data = sys.stdin.buffer.read()
        else:
            with open(filename, 'rb') as source:
                data = source.read()
    except OSError as exc:
        print(exc, file=sys.stderr)
        return 1
    lines = data.split(b'\n') if data else []
    if lines and lines[-1] == b'' and data.endswith(b'\n'):
        lines.pop()
    number, step, width = int(opts['-v']), int(opts['-i']), int(opts['-w'])
    output = []
    for line in lines:
        if opts['-b'] == 'a' or (opts['-b'] == 't' and line):
            digits = str(number)
            field = digits.ljust(width) if opts['-f'] == 'ln' else digits.zfill(width) if opts['-f'] == 'rz' else digits.rjust(width)
            output.append(field.encode() + opts['-s'].encode() + line + b'\n')
            number += step
        else:
            output.append(line + b'\n')
    sys.stdout.buffer.write(b''.join(output))
    return 0


if __name__ == '__main__':
    sys.exit(main())
