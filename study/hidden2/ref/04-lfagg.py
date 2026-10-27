"""Private logfmt parser and exact integer mean oracle."""
import re
import sys
KEY = r'[A-Za-z_][A-Za-z0-9_.]*'

def parse(s):
    pairs = {}; i = 0
    while i < len(s):
        if s[i] == ' ':
            i += 1; continue
        m = re.match(KEY, s[i:])
        if not m:
            return None
        key = m[0]; i += len(key)
        if key in pairs:
            return None
        value = 'true'
        if i < len(s) and s[i] == '=':
            i += 1
            if i < len(s) and s[i] == '"':
                i += 1; value = ''
                while i < len(s) and s[i] != '"':
                    c = s[i]; i += 1
                    if c == '\\':
                        if i == len(s) or s[i] not in '\\"':
                            return None
                        c = s[i]; i += 1
                    value += c
                if i == len(s):
                    return None
                i += 1
            else:
                start = i
                while i < len(s) and s[i] != ' ':
                    i += 1
                value = s[start:i]
                if '"' in value or '=' in value:
                    return None
        if i < len(s) and s[i] != ' ':
            return None
        pairs[key] = value
    return pairs

def main(args):
    if len(args) not in (1,2) or not all(re.fullmatch(KEY, a) for a in args):
        return 2
    groups = {}; valid = malformed = nokey = 0
    raw = sys.stdin.buffer.read().decode('ascii')
    lines = raw.split('\n')
    if lines[-1] == '':
        lines.pop()
    for s in lines:
        s = s[:-1] if s.endswith('\r') else s
        if not s.strip(' '):
            continue
        p = parse(s)
        if p is None:
            malformed += 1; continue
        valid += 1
        if args[0] not in p:
            nokey += 1; continue
        name = p[args[0]]
        count, nums = groups.setdefault(name, [0, []]); groups[name][0] += 1
        if len(args) == 2 and args[1] in p and re.fullmatch(r'-?[0-9]{1,15}', p[args[1]]):
            nums.append(int(p[args[1]]))
    for name, (count, nums) in sorted(groups.items(), key=lambda p: (-p[1][0], p[0])):
        line = (name if name else '""') + f' count={count}'
        if len(args) == 2:
            if not nums:
                line += ' n=0 sum=0 min=- max=- avg=-'
            else:
                total = sum(nums); n = len(nums)
                cents = (abs(total)*200+n)//(2*n)
                avg = ('-' if total < 0 and cents else '') + f'{cents//100}.{cents%100:02}'
                line += f' n={n} sum={total} min={min(nums)} max={max(nums)} avg={avg}'
        print(line)
    print(f'lines={valid} malformed={malformed} nokey={nokey}')
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
