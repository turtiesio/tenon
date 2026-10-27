"""Private spec-derived reference for wrap (stdlib only)."""
import re
import sys

def main():
    opts = {'-w':72, '-i':0, '-j':False}
    seen = set()
    a = iter(sys.argv[1:])
    for x in a:
        if x not in opts or x in seen:
            return 2
        seen.add(x)
        if x == '-j':
            opts[x] = True
        else:
            v = next(a, '')
            if not re.fullmatch(r'[0-9]{1,4}', v):
                return 2
            opts[x] = int(v)
    w, indent = opts['-w'], opts['-i']
    if not 1 <= w <= 1000 or not 0 <= indent < w:
        return 2
    data = sys.stdin.buffer.read()
    lines = data.split(b'\n')
    lines = [s[:-1] if s.endswith(b'\r') else s for s in lines]
    if any(any(c < 32 or c > 126 for c in s) for s in lines):
        return 1
    paragraphs, words = [], []
    for line in lines + [b'']:
        if line.strip(b' '):
            words.extend(line.decode('ascii').split())
        elif words:
            paragraphs.append(words)
            words = []
    rendered = []
    for words in paragraphs:
        groups = []
        i = 0
        while i < len(words):
            pad = indent if not groups else 0
            group = [words[i]]
            size = pad + len(words[i])
            i += 1
            while i < len(words) and size + 1 + len(words[i]) <= w:
                size += 1 + len(words[i])
                group.append(words[i]); i += 1
            groups.append((pad, group))
        output = []
        for n, (pad, group) in enumerate(groups):
            if opts['-j'] and n < len(groups)-1 and len(group) > 1:
                q, r = divmod(w-pad-sum(map(len,group)), len(group)-1)
                s = group[0] + ''.join(' '*(q+(j<r)) + word for j,word in enumerate(group[1:]))
            else:
                s = ' '.join(group)
            output.append(' '*pad+s)
        rendered.append('\n'.join(output))
    if rendered:
        sys.stdout.write('\n\n'.join(rendered)+'\n')
    return 0

if __name__ == '__main__':
    status = main()
    if status: print('wrap: error', file=sys.stderr)
    sys.exit(status)
