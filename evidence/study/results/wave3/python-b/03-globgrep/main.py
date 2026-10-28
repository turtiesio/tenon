import sys


def compile_pattern(pattern):
    tokens = []
    i = 0

    def character(pos):
        if pos >= len(pattern):
            raise ValueError()
        if pattern[pos] == '\\':
            pos += 1
            if pos >= len(pattern):
                raise ValueError()
        return pattern[pos], pos + 1

    while i < len(pattern):
        char = pattern[i]
        i += 1
        if char in '*?':
            tokens.append((char, None))
        elif char == '\\':
            literal, i = character(i - 1)
            tokens.append(('literal', literal))
        elif char == '[':
            negate = i < len(pattern) and pattern[i] == '!'
            i += negate
            members = set()
            first = True
            while True:
                if i >= len(pattern):
                    raise ValueError()
                if pattern[i] == ']' and not first:
                    i += 1
                    break
                start, i = character(i)
                first = False
                if i + 1 < len(pattern) and pattern[i] == '-' and pattern[i + 1] != ']':
                    end, i = character(i + 1)
                    if ord(start) > ord(end):
                        raise ValueError()
                    members.update(chr(n) for n in range(ord(start), ord(end) + 1))
                else:
                    members.add(start)
            tokens.append(('negative' if negate else 'class', members))
        else:
            tokens.append(('literal', char))
    return tokens


def matches(tokens, line, insensitive):
    previous = [True] + [False] * len(line)
    for kind, value in tokens:
        current = [False] * (len(line) + 1)
        if kind == '*':
            current[0] = previous[0]
            for j in range(1, len(current)):
                current[j] = previous[j] or current[j - 1]
        else:
            for j, char in enumerate(line, 1):
                if kind == '?':
                    hit = True
                elif kind == 'literal':
                    hit = char.lower() == value.lower() if insensitive else char == value
                else:
                    hit = char in value
                    if insensitive:
                        hit = char.lower() in value or char.upper() in value
                    if kind == 'negative':
                        hit = not hit
                current[j] = previous[j - 1] and hit
        previous = current
    return previous[-1]


def main():
    options = set()
    pattern = None
    ended = False
    try:
        for arg in sys.argv[1:]:
            if pattern is not None:
                raise ValueError()
            if not ended and arg in ('-i', '-v', '-c'):
                options.add(arg)
            elif not ended and arg == '--':
                ended = True
            elif not ended and arg.startswith('-'):
                raise ValueError()
            else:
                pattern = arg
        if pattern is None:
            raise ValueError()
        tokens = compile_pattern(pattern)
    except ValueError:
        print('invalid arguments or pattern', file=sys.stderr)
        return 2
    data = sys.stdin.buffer.read()
    lines = data.split(b'\n')
    if lines[-1] == b'':
        lines.pop()
    selected = []
    for raw in lines:
        line = raw.removesuffix(b'\r').decode('ascii')
        if matches(tokens, line, '-i' in options) != ('-v' in options):
            selected.append(line)
    if '-c' in options:
        print(len(selected))
    elif selected:
        sys.stdout.write('\n'.join(selected) + '\n')
    return 0 if selected else 1


if __name__ == '__main__':
    sys.exit(main())
