import re
import sys


def main():
    args = sys.argv[1:]
    if not args:
        limit = 6
    elif len(args) == 2 and args[0] == '-l' and args[1] in tuple('123456'):
        limit = int(args[1])
    else:
        print('Invalid arguments', file=sys.stderr)
        return 2
    used = set()
    headings = []
    fenced = False
    for line in sys.stdin.buffer.read().decode('ascii').split('\n'):
        if line.endswith('\r'):
            line = line[:-1]
        if line.startswith('```'):
            fenced = not fenced
            continue
        if fenced:
            continue
        match = re.match(r'^(#{1,6}) (.*)$', line)
        if match is None:
            continue
        level = len(match[1])
        text = match[2].strip(' ')
        if not text:
            continue
        base = re.sub(r'[^a-z0-9_-]', '', text.lower().replace(' ', '-')) or 'section'
        slug = base
        suffix = 1
        while slug in used:
            slug = f'{base}-{suffix}'
            suffix += 1
        used.add(slug)
        if level <= limit:
            headings.append((level, text, slug))
    if headings:
        minimum = min(level for level, _, _ in headings)
        for level, text, slug in headings:
            print('  ' * (level - minimum) + f'- [{text}](#{slug})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
