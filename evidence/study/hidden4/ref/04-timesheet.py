"""Private specification reference: stable punch pairing by employee/day."""
import collections
import re
import sys
DAYS = 'Mon Tue Wed Thu Fri Sat Sun'.split()
def clock(m): return f'{m//60}:{m%60:02d}'
def main():
    if len(sys.argv) != 1:
        print('usage error', file=sys.stderr); return 2
    rows = sys.stdin.buffer.read().decode('ascii').split('\n')
    if rows[-1] == '': rows.pop()
    people = collections.defaultdict(lambda: collections.defaultdict(list))
    skipped = 0
    for line in rows:
        if line.endswith('\r'): line = line[:-1]
        if not line.strip(' '): continue
        m = re.fullmatch(r'([a-z]{1,16}) (Mon|Tue|Wed|Thu|Fri|Sat|Sun) ([0-9]{2}):([0-9]{2}) (IN|OUT)', line)
        if m is None or int(m[3]) > 23 or int(m[4]) > 59:
            skipped += 1; continue
        people[m[1]][m[2]].append((int(m[3])*60+int(m[4]), m[5]))
    for name in sorted(people):
        minutes, anomalies = {}, 0
        for day, punches in people[name].items():
            opened, total = None, 0
            for time, kind in sorted(punches, key=lambda x: x[0]):
                if kind == 'IN':
                    if opened is not None: anomalies += 1
                    opened = time
                elif opened is None: anomalies += 1
                else: total += time-opened; opened = None
            if opened is not None: anomalies += 1
            minutes[day] = total
        parts = [name]+[d+'='+clock(minutes[d]) for d in DAYS if minutes.get(d, 0) > 0]
        parts += ['total='+clock(sum(minutes.values())), 'overtime='+clock(sum(max(0, m-480) for m in minutes.values())), 'anomalies='+str(anomalies)]
        print(' '.join(parts))
    print('skipped='+str(skipped))
    return 0
if __name__ == '__main__': sys.exit(main())
