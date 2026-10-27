import sys


def expand(value):
    tokens = []
    i = 0
    escapes = {'n': '\n', 't': '\t', '\\': '\\', '-': '-'}
    while i < len(value):
        char = value[i]
        escaped = False
        if char == '\\':
            i += 1
            if i == len(value) or value[i] not in escapes:
                raise ValueError('invalid escape')
            char = escapes[value[i]]
            escaped = True
        tokens.append((char, escaped))
        i += 1
    result = []
    i = 0
    while i < len(tokens):
        if i + 2 < len(tokens) and tokens[i + 1] == ('-', False):
            start, end = ord(tokens[i][0]), ord(tokens[i + 2][0])
            if start > end:
                raise ValueError('reversed range')
            result.extend(range(start, end + 1))
            i += 3
        else:
            result.append(ord(tokens[i][0]))
            i += 1
    return result


def main(args):
    delete = squeeze = False
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == '--':
            i += 1
            break
        if arg == '-d':
            delete = True
        elif arg == '-s':
            squeeze = True
        elif arg.startswith('-') and len(arg) >= 2:
            raise ValueError('unknown option')
        else:
            break
        i += 1
    sets = [expand(arg) for arg in args[i:]]
    valid_counts = (2,) if delete and squeeze or not (delete or squeeze) else ((1,) if delete else (1, 2))
    if len(sets) not in valid_counts:
        raise ValueError('wrong number of sets')
    translate = not delete and len(sets) == 2
    if translate and not sets[1]:
        raise ValueError('empty translation target')
    mapping = {char: sets[1][min(j, len(sets[1]) - 1)] for j, char in enumerate(sets[0])} if translate else {}
    deleted = set(sets[0]) if delete else set()
    squeezed = set(sets[-1]) if squeeze else set()
    result = bytearray()
    for char in sys.stdin.buffer.read():
        if char in deleted:
            continue
        char = mapping.get(char, char)
        if result and result[-1] == char and char in squeezed:
            continue
        result.append(char)
    sys.stdout.buffer.write(result)


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except ValueError as error:
        print(error, file=sys.stderr)
        sys.exit(2)
