"""Private globgrep reference using an iterative wildcard automaton."""
import sys

def parse(p):
    tokens = []; i = 0
    def char(j):
        if j >= len(p): raise ValueError('missing character')
        if p[j] == '\\':
            j += 1
            if j >= len(p): raise ValueError('escape')
        return p[j], j+1
    while i < len(p):
        c = p[i]; i += 1
        if c in '*?': tokens.append((c,None))
        elif c == '\\':
            if i == len(p): raise ValueError('escape')
            tokens.append(('lit',p[i])); i += 1
        elif c != '[': tokens.append(('lit',c))
        else:
            neg = i < len(p) and p[i] == '!'
            if neg: i += 1
            members = set(); first = True
            while True:
                if i >= len(p): raise ValueError('unclosed class')
                if p[i] == ']' and not first:
                    i += 1; break
                x,i = char(i); first = False
                if i+1 < len(p) and p[i] == '-' and p[i+1] != ']':
                    y,i = char(i+1)
                    if ord(x)>ord(y): raise ValueError('range')
                    members.update(map(chr,range(ord(x),ord(y)+1)))
                else: members.add(x)
            tokens.append(('not' if neg else 'set',members))
    return tokens

def matches(tokens,s,ignore):
    # dp[j] means the first j input bytes match the tokens processed so far.
    dp = [True]+[False]*len(s)
    for kind,value in tokens:
        nxt = [False]*(len(s)+1)
        if kind == '*':
            nxt[0] = dp[0]
            for j in range(1,len(s)+1): nxt[j] = dp[j] or nxt[j-1]
        else:
            for j,c in enumerate(s,1):
                if kind == '?': ok = True
                elif kind == 'lit': ok = c.lower() == value.lower() if ignore else c == value
                else:
                    ok = (c.lower() in value or c.upper() in value) if ignore else c in value
                    if kind == 'not': ok = not ok
                nxt[j] = dp[j-1] and ok
        dp = nxt
    return dp[-1]

def main():
    ignore = invert = count = False
    p = None; ended = False
    for x in sys.argv[1:]:
        if p is not None: return 2
        if ended: p = x
        elif x == '--': ended = True
        elif x == '-i': ignore = True
        elif x == '-v': invert = True
        elif x == '-c': count = True
        elif x.startswith('-'): return 2
        else: p = x
    if p is None: return 2
    try: tokens = parse(p)
    except ValueError: return 2
    data = sys.stdin.buffer.read().decode('ascii')
    lines = data.split('\n')
    if lines[-1] == '': lines.pop()
    selected = []
    for s in lines:
        if s.endswith('\r'): s = s[:-1]
        if matches(tokens,s,ignore) != invert: selected.append(s)
    if count: print(len(selected))
    elif selected: sys.stdout.write('\n'.join(selected)+'\n')
    return 0 if selected else 1

if __name__ == '__main__':
    status = main()
    if status == 2: print('globgrep: error',file=sys.stderr)
    sys.exit(status)
