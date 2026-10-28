import base64
import binascii
import re
import sys


def main():
    args = iter(sys.argv[1:])
    decode = False
    width = 76
    try:
        for arg in args:
            if arg == '-d':
                decode = True
            elif arg == '-w':
                value = next(args, '')
                if not re.fullmatch(r'[0-9]{1,4}', value):
                    raise ValueError('invalid width')
                width = int(value)
            else:
                raise ValueError(f'unknown argument: {arg}')
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    data = sys.stdin.buffer.read()
    if decode:
        data = data.replace(b'\r', b'').replace(b'\n', b'')
        try:
            result = base64.b64decode(data, validate=True)
            if base64.b64encode(result) != data:
                raise ValueError('noncanonical Base64')
        except (ValueError, binascii.Error) as exc:
            print(f'invalid Base64: {exc}', file=sys.stderr)
            return 1
        sys.stdout.buffer.write(result)
    else:
        result = base64.b64encode(data)
        if result:
            width = width or len(result)
            sys.stdout.buffer.write(b'\n'.join(result[i:i + width] for i in range(0, len(result), width)) + b'\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
