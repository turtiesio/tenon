import re
import sys


def main():
    options = {'-s': 0, '-n': None, '-w': 16}
    filename = None
    args = iter(sys.argv[1:])
    try:
        for arg in args:
            if arg in options:
                value = next(args)
                pattern = r'[0-9]{1,2}' if arg == '-w' else r'[0-9]{1,9}'
                if not re.fullmatch(pattern, value):
                    raise ValueError('Invalid option value')
                number = int(value)
                if arg == '-w' and not 1 <= number <= 32:
                    raise ValueError('Invalid width')
                options[arg] = number
            elif arg.startswith('-') and arg != '-':
                raise ValueError('Unknown option')
            elif filename is not None:
                raise ValueError('Too many files')
            else:
                filename = arg
    except (ValueError, StopIteration) as error:
        print(str(error) or 'Missing option value', file=sys.stderr)
        return 2
    try:
        if filename is None or filename == '-':
            data = sys.stdin.buffer.read()
        else:
            with open(filename, 'rb') as source:
                data = source.read()
    except OSError as error:
        print(error, file=sys.stderr)
        return 1
    skip, length, width = options['-s'], options['-n'], options['-w']
    selected = data[skip:] if length is None else data[skip:skip + length]
    for index in range(0, len(selected), width):
        chunk = selected[index:index + width]
        fields = [f'{byte:02x}' for byte in chunk] + ['  '] * (width - len(chunk))
        ascii_text = ''.join(chr(byte) if 32 <= byte <= 126 else '.' for byte in chunk)
        print(f'{skip + index:08x}  {" ".join(fields)}  |{ascii_text}|')
    print(f'{skip + len(selected):08x}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
