"""Private sliding-window oracle."""
from collections import deque
import re
import sys

def main(args):
    opts = {'-w':60, '-t':3, '-c':300}
    if len(args)%2:
        return 2
    for key, v in zip(args[::2], args[1::2]):
        if key not in opts or not re.fullmatch('[0-9]{1,9}', v) or int(v) < (0 if key == '-c' else 1):
            return 2
        opts[key] = int(v)
    services = {}; last = 0; skipped = 0
    for line in sys.stdin.buffer.read().decode('ascii').splitlines(keepends=True):
        # Only LF delimits; fixtures contain no other line delimiters except terminal CR.
        s = line.removesuffix('\n').removesuffix('\r')
        if not s.strip(' '):
            continue
        m = re.fullmatch(r'([0-9]{1,12}) ([a-z][a-z0-9-]{0,31}) (INFO|WARN|ERROR)', s)
        if not m or int(m[1]) < last:
            skipped += 1; continue
        t, name, level = int(m[1]), m[2], m[3]; last = t
        state = services.setdefault(name, {'errors':0, 'warns':0, 'alerts':0, 'peak':0, 'queue':deque(), 'alert':None})
        if level == 'WARN':
            state['warns'] += 1
        if level == 'ERROR':
            state['errors'] += 1
            q = state['queue']; q.append(t)
            while q and q[0] <= t-opts['-w']:
                q.popleft()
            n = len(q); state['peak'] = max(state['peak'], n)
            if n >= opts['-t'] and (state['alert'] is None or t-state['alert'] >= opts['-c']):
                print(f'ALERT {t} {name} {n}'); state['alerts'] += 1; state['alert'] = t
    for name, state in sorted(services.items()):
        print(name + ' ' + ' '.join(f'{k}={state[k]}' for k in ('errors','warns','alerts','peak')))
    print(f'skipped={skipped}')
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
