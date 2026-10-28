import sys
from collections import defaultdict
from pathlib import Path


def read_csv(path):
    text = Path(path).read_bytes().decode('ascii')
    records = []
    i = 0
    while i < len(text):
        if text[i] == '\n' or text.startswith('\r\n', i):
            i += 2 if text[i] == '\r' else 1
            continue
        row = []
        while True:
            field = []
            if i < len(text) and text[i] == '"':
                i += 1
                while True:
                    if i == len(text):
                        raise ValueError('unclosed quote')
                    if text[i] == '"':
                        i += 1
                        if i < len(text) and text[i] == '"':
                            field.append('"')
                            i += 1
                        else:
                            break
                    else:
                        field.append(text[i])
                        i += 1
            else:
                while i < len(text) and text[i] not in ',\r\n':
                    if text[i] == '"':
                        raise ValueError('quote inside field')
                    field.append(text[i])
                    i += 1
            row.append(''.join(field))
            if i == len(text):
                break
            if text[i] == ',':
                i += 1
                continue
            if text[i] == '\n':
                i += 1
                break
            if text.startswith('\r\n', i):
                i += 2
                break
            raise ValueError('invalid field ending')
        records.append(row)
    if not records:
        raise ValueError('missing header')
    header = records[0]
    if len(set(header)) != len(header) or any(len(row) != len(header) for row in records):
        raise ValueError('invalid columns')
    return header, records[1:]


def encode(row):
    return ','.join('"' + field.replace('"', '""') + '"' if any(c in field for c in ',"\r\n') else field for field in row)


def main():
    key, left_join, paths = 'id', False, []
    args = iter(sys.argv[1:])
    try:
        for arg in args:
            if arg == '-l':
                left_join = True
            elif arg == '-k':
                key = next(args)
                if not key:
                    raise ValueError()
            elif arg.startswith('-'):
                raise ValueError()
            else:
                paths.append(arg)
        if len(paths) != 2:
            raise ValueError()
    except (ValueError, StopIteration):
        print('invalid arguments', file=sys.stderr)
        return 2
    try:
        lh, left = read_csv(paths[0])
        rh, right = read_csv(paths[1])
        li, ri = lh.index(key), rh.index(key)
    except (OSError, ValueError, UnicodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    columns = [i for i in range(len(rh)) if i != ri]
    output = [lh + [('r.' + rh[i]) if rh[i] in lh else rh[i] for i in columns]]
    lookup = defaultdict(list)
    for row in right:
        lookup[row[ri]].append([row[i] for i in columns])
    for row in left:
        matches = lookup[row[li]]
        if not matches and left_join:
            matches = [[''] * len(columns)]
        for match in matches:
            output.append(row + match)
    sys.stdout.write('\n'.join(map(encode, output)) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
