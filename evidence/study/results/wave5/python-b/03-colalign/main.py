import re
import sys


def main(args):
    separator = None
    output_separator = '  '
    right = set()
    i = 0
    while i < len(args):
        option = args[i]
        if option not in ('-s', '-o', '-r') or i + 1 == len(args):
            raise ValueError('invalid option')
        value = args[i + 1]
        if option == '-s':
            if len(value) != 1:
                raise ValueError('separator must be one character')
            separator = value
        elif option == '-o':
            output_separator = value
        else:
            if not re.fullmatch(r'[1-9][0-9]{0,2}(,[1-9][0-9]{0,2})*', value):
                raise ValueError('invalid column list')
            right = {int(number) - 1 for number in value.split(',')}
        i += 2
    data = sys.stdin.read()
    lines = data.split('\n') if data else []
    if lines and lines[-1] == '' and data.endswith('\n'):
        lines.pop()
    rows = []
    widths = []
    for line in lines:
        if line.endswith('\r'):
            line = line[:-1]
        fields = (line.split(separator) if separator is not None else re.findall(r'[^ \t]+', line)) if line else []
        rows.append(fields)
        for column, field in enumerate(fields):
            if column == len(widths):
                widths.append(len(field))
            else:
                widths[column] = max(widths[column], len(field))
    for fields in rows:
        padded = []
        for column, field in enumerate(fields):
            if column in right:
                field = field.rjust(widths[column])
            elif column < len(fields) - 1:
                field = field.ljust(widths[column])
            padded.append(field)
        print(output_separator.join(padded))


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except ValueError as error:
        print(error, file=sys.stderr)
        sys.exit(2)
