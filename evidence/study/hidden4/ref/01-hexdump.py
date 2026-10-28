"""Private specification reference: binary canonical dump."""
import re
import sys

def main():
    opts = {'-s': 0, '-n': None, '-w': 16}
    file = None
    args = iter(sys.argv[1:])
    try:
        for arg in args:
            if arg in opts:
                value = next(args)
                if not re.fullmatch(r'[0-9]{1,2}' if arg == '-w' else r'[0-9]{1,9}', value):
                    raise ValueError()
                n = int(value)
                if arg == '-w' and not 1 <= n <= 32:
                    raise ValueError()
                opts[arg] = n
            elif (arg.startswith('-') and arg != '-') or file is not None:
                raise ValueError()
            else:
                file = arg
    except (ValueError, StopIteration):
        print('usage error', file=sys.stderr)
        return 2
    try:
        data = sys.stdin.buffer.read() if file is None or file == '-' else open(file, 'rb').read()
    except OSError:
        print('unreadable file', file=sys.stderr)
        return 1
    start, length, width = opts['-s'], opts['-n'], opts['-w']
    chosen = data[start:][:length] if length is not None else data[start:]
    for i in range(0, len(chosen), width):
        chunk = chosen[i:i+width]
        fields = [f'{b:02x}' for b in chunk] + ['  '] * (width-len(chunk))
        ascii_text = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
        print(f'{start+i:08x}  {" ".join(fields)}  |{ascii_text}|')
    print(f'{start+len(chosen):08x}')
    return 0

if __name__ == '__main__':
    sys.exit(main())
