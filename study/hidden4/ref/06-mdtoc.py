"""Private specification reference: all-heading unique slug assignment."""
import re
import sys

def main():
    args = sys.argv[1:]
    if args and not (len(args) == 2 and args[0] == '-l' and re.fullmatch('[1-6]', args[1])):
        print('usage error', file=sys.stderr); return 2
    level = int(args[1]) if args else 6
    used, listed, fenced = set(), [], False
    rows = sys.stdin.buffer.read().decode('ascii').split('\n')
    if rows[-1] == '': rows.pop()
    for line in rows:
        if line.endswith('\r'): line = line[:-1]
        if line.startswith('```'): fenced = not fenced; continue
        if fenced: continue
        match = re.match(r'^(#{1,6}) (.*)$', line)
        if not match: continue
        text = match[2].strip(' ')
        if not text: continue
        base = re.sub('[^a-z0-9_-]', '', text.lower().replace(' ', '-')) or 'section'
        slug, i = base, 0
        while slug in used:
            i += 1; slug = base+'-'+str(i)
        used.add(slug)
        if len(match[1]) <= level: listed.append((len(match[1]), text, slug))
    minimum = min((x[0] for x in listed), default=0)
    for depth, text, slug in listed: print(' '*(2*(depth-minimum))+f'- [{text}](#{slug})')
    return 0
if __name__ == '__main__': sys.exit(main())
