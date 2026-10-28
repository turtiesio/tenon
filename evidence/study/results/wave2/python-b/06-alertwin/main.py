import re
import sys
from collections import deque

def main():
    options = {'-w': 60, '-t': 3, '-c': 300}
    args = sys.argv[1:]
    if len(args) % 2:
        return 2
    for key, value in zip(args[::2], args[1::2]):
        if key not in options or not re.fullmatch(r'[0-9]{1,9}', value):
            return 2
        number = int(value)
        if number < (0 if key == '-c' else 1):
            return 2
        options[key] = number
    services = {}
    last = -1
    skipped = 0
    pattern = re.compile(r'([0-9]{1,12}) ([a-z][a-z0-9-]{0,31}) (INFO|WARN|ERROR)')
    for line in sys.stdin:
        line = line.removesuffix('\n').removesuffix('\r')
        if not line.strip(' '):
            continue
        match = pattern.fullmatch(line)
        if not match or int(match[1]) < last:
            skipped += 1
            continue
        time, service, level = int(match[1]), match[2], match[3]
        last = time
        state = services.setdefault(service, {'errors': 0, 'warns': 0, 'alerts': 0, 'peak': 0, 'last_alert': None, 'window': deque()})
        if level == 'WARN':
            state['warns'] += 1
        elif level == 'ERROR':
            state['errors'] += 1
            window = state['window']
            while window and window[0] <= time - options['-w']:
                window.popleft()
            window.append(time)
            count = len(window)
            state['peak'] = max(state['peak'], count)
            if count >= options['-t'] and (state['last_alert'] is None or time - state['last_alert'] >= options['-c']):
                state['last_alert'] = time
                state['alerts'] += 1
                print(f'ALERT {time} {service} {count}')
    for service, state in sorted(services.items()):
        print(service + ' ' + ' '.join(f'{key}={state[key]}' for key in ('errors', 'warns', 'alerts', 'peak')))
    print(f'skipped={skipped}')
    return 0

if __name__ == '__main__':
    sys.exit(main())
