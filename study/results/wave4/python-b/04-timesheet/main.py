from collections import defaultdict
import re
import sys


def format_time(minutes):
    return f'{minutes // 60}:{minutes % 60:02d}'


def main():
    if len(sys.argv) != 1:
        print('No arguments allowed', file=sys.stderr)
        return 2
    punches = defaultdict(lambda: defaultdict(list))
    skipped = 0
    pattern = re.compile(r'([a-z]{1,16}) (Mon|Tue|Wed|Thu|Fri|Sat|Sun) ([0-9]{2}):([0-9]{2}) (IN|OUT)')
    data = sys.stdin.buffer.read().decode('utf-8', errors='replace')
    lines = data.split('\n') if data else []
    if data.endswith('\n'):
        lines.pop()
    for line in lines:
        if line.endswith('\r'):
            line = line[:-1]
        if not line.strip(' '):
            continue
        match = pattern.fullmatch(line)
        if match is None:
            skipped += 1
            continue
        name, day, hour, minute, kind = match.groups()
        if int(hour) > 23 or int(minute) > 59:
            skipped += 1
            continue
        punches[name][day].append((int(hour) * 60 + int(minute), kind))
    for name in sorted(punches):
        parts = [name]
        total = overtime = anomalies = 0
        for day in ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'):
            opened = None
            minutes = 0
            for time, kind in sorted(punches[name][day], key=lambda punch: punch[0]):
                if kind == 'IN':
                    if opened is not None:
                        anomalies += 1
                    opened = time
                elif opened is None:
                    anomalies += 1
                else:
                    minutes += time - opened
                    opened = None
            if opened is not None:
                anomalies += 1
            if minutes:
                parts.append(f'{day}={format_time(minutes)}')
            total += minutes
            overtime += max(0, minutes - 480)
        parts.extend((f'total={format_time(total)}', f'overtime={format_time(overtime)}', f'anomalies={anomalies}'))
        print(' '.join(parts))
    print(f'skipped={skipped}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
