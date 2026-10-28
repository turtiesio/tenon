import re
import sys

KEY = re.compile(r'[A-Za-z_][A-Za-z0-9_.]*')

def parse(line):
    pairs = {}
    i = 0
    while i < len(line):
        if line[i] == ' ':
            i += 1
            continue
        match = KEY.match(line, i)
        if not match:
            raise ValueError
        key = match[0]
        i = match.end()
        if key in pairs:
            raise ValueError
        value = 'true'
        if i < len(line) and line[i] != ' ':
            if line[i] != '=':
                raise ValueError
            i += 1
            if i < len(line) and line[i] == '"':
                i += 1
                chars = []
                while i < len(line) and line[i] != '"':
                    if line[i] == '\\':
                        i += 1
                        if i == len(line) or line[i] not in '\\"':
                            raise ValueError
                    chars.append(line[i])
                    i += 1
                if i == len(line):
                    raise ValueError
                i += 1
                if i < len(line) and line[i] != ' ':
                    raise ValueError
                value = ''.join(chars)
            else:
                end = line.find(' ', i)
                if end == -1:
                    end = len(line)
                value = line[i:end]
                if '"' in value or '=' in value:
                    raise ValueError
                i = end
        pairs[key] = value
    return pairs

def main():
    args = sys.argv[1:]
    if len(args) not in (1, 2) or any(not KEY.fullmatch(a) for a in args):
        return 2
    groups = {}
    valid = malformed = nokey = 0
    for line in sys.stdin:
        line = line.removesuffix('\n').removesuffix('\r')
        if not line.strip(' '):
            continue
        try:
            pairs = parse(line)
        except ValueError:
            malformed += 1
            continue
        valid += 1
        if args[0] not in pairs:
            nokey += 1
            continue
        group = groups.setdefault(pairs[args[0]], [0, 0, 0, None, None])
        group[0] += 1
        value = pairs.get(args[1]) if len(args) == 2 else None
        if value is not None and re.fullmatch(r'-?[0-9]{1,15}', value):
            value = int(value)
            group[1] += 1
            group[2] += value
            group[3] = value if group[3] is None else min(group[3], value)
            group[4] = value if group[4] is None else max(group[4], value)
    for name, (count, n, total, low, high) in sorted(groups.items(), key=lambda item: (-item[1][0], item[0])):
        output = f'{name if name else chr(34) * 2} count={count}'
        if len(args) == 2:
            if n:
                cents = (abs(total) * 200 + n) // (2 * n)
                avg = ('-' if total < 0 and cents else '') + f'{cents // 100}.{cents % 100:02}'
                output += f' n={n} sum={total} min={low} max={high} avg={avg}'
            else:
                output += ' n=0 sum=0 min=- max=- avg=-'
        print(output)
    print(f'lines={valid} malformed={malformed} nokey={nokey}')
    return 0

if __name__ == '__main__':
    sys.exit(main())
