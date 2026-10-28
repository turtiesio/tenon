import re
import sys


def main():
    options = {'-f': 10, '-t': 10, '-w': 0, '-g': 0}
    uppercase = False
    values = []
    args = iter(sys.argv[1:])
    try:
        for arg in args:
            if arg == '-u':
                uppercase = True
            elif arg in options:
                raw = next(args)
                if not re.fullmatch('[0-9]{1,2}', raw):
                    raise ValueError()
                number = int(raw)
                low, high = (2, 36) if arg in ('-f', '-t') else (1, 64)
                if not low <= number <= high:
                    raise ValueError()
                options[arg] = number
            else:
                values.append(arg)
        if not values:
            raise ValueError()
    except (ValueError, StopIteration):
        print('invalid arguments', file=sys.stderr)
        return 2
    digits = '0123456789abcdefghijklmnopqrstuvwxyz'
    status = 0
    for raw in values:
        source = raw[1:] if raw.startswith('-') else raw
        number = 0
        valid = bool(source)
        for char in source.lower():
            digit = digits.find(char)
            if digit < 0 or digit >= options['-f']:
                valid = False
                break
            number = number * options['-f'] + digit
            if number > 9223372036854775807:
                valid = False
                break
        if not valid:
            print('invalid value: ' + raw, file=sys.stderr)
            status = 1
            continue
        negative = raw.startswith('-') and number != 0
        result = ''
        while number:
            number, rem = divmod(number, options['-t'])
            result = digits[rem] + result
        result = (result or '0').zfill(options['-w'])
        group = options['-g']
        if group:
            first = len(result) % group or group
            result = '_'.join([result[:first]] + [result[i:i+group] for i in range(first, len(result), group)])
        if uppercase:
            result = result.upper()
        print(('-' if negative else '') + result)
    return status


if __name__ == '__main__':
    sys.exit(main())
