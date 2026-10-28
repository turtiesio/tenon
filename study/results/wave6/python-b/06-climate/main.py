from collections import defaultdict
from datetime import date
import re
import sys


def temperature(tenths):
    return f'{"-" if tenths < 0 else ""}{abs(tenths) // 10}.{abs(tenths) % 10}'


def main():
    if sys.argv[1:] not in ([], ['-y']):
        print('expected optional -y', file=sys.stderr)
        return 2
    readings = {}
    skipped = replaced = 0
    for line in sys.stdin.buffer.read().decode('utf-8').split('\n'):
        if line.endswith('\r'):
            line = line[:-1]
        if not line:
            continue
        fields = line.split(';')
        try:
            if len(fields) != 3:
                raise ValueError()
            station, day, temp = fields
            if (not 1 <= len(station) <= 40 or station.startswith(' ') or station.endswith(' ')
                    or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', day)
                    or not re.fullmatch(r'-?[0-9]{1,2}\.[0-9]', temp)):
                raise ValueError()
            date.fromisoformat(day)
        except ValueError:
            skipped += 1
            continue
        value = int(temp.replace('.', ''))
        key = station, day
        if key in readings:
            replaced += 1
        readings[key] = value
    groups = defaultdict(list)
    period_length = 4 if sys.argv[1:] else 7
    for (station, day), value in readings.items():
        groups[station, day[:period_length]].append(value)
    for station, period in sorted(groups, key=lambda key: (key[0].encode('utf-8'), key[1])):
        values = groups[station, period]
        total, count = sum(values), len(values)
        mean = (2 * abs(total) + count) // (2 * count)
        if total < 0:
            mean = -mean
        print(f'{station} {period} days={count} min={temperature(min(values))} max={temperature(max(values))} mean={temperature(mean)}')
    print(f'readings={len(readings)} skipped={skipped} replaced={replaced}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
