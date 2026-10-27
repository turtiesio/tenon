"""Private Gregorian calendar oracle, integer formatting independent of locale."""
import calendar
from datetime import date, timedelta
import re
import sys
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
MONTHS = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()

def main(args):
    fmt = '%Y-%m-%d'
    i = 0
    while i < len(args) and args[i].startswith('-'):
        if args[i] != '-F' or i+1 == len(args):
            return 2
        fmt = args[i+1]; i += 2
    if i == len(args):
        return 2
    cmd, vals = args[i], args[i+1:]
    if cmd not in ('weekday', 'add', 'diff', 'addmonths') or len(vals) != (1 if cmd == 'weekday' else 2):
        return 2
    if cmd in ('add', 'addmonths') and not re.fullmatch(r'-?[0-9]{1,7}', vals[1]):
        return 2
    j = 0
    while j < len(fmt):
        if fmt[j] == '%':
            if j+1 == len(fmt) or fmt[j+1] not in 'Ymdjab%':
                return 2
            j += 1
        j += 1
    try:
        dates = []
        for value in vals[:2 if cmd == 'diff' else 1]:
            if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
                return 1
            dates.append(date(*map(int, value.split('-'))))
        d = dates[0]
        if cmd == 'weekday':
            print(DAYS[d.weekday()]); return 0
        if cmd == 'diff':
            print((dates[1]-d).days); return 0
        amount = int(vals[1])
        if cmd == 'add':
            d += timedelta(days=amount)
        else:
            y, m = divmod((d.year-1)*12 + d.month-1 + amount, 12)
            y += 1; m += 1
            if not 1 <= y <= 9999:
                return 1
            d = date(y, m, min(d.day, calendar.monthrange(y, m)[1]))
    except (ValueError, OverflowError):
        return 1
    replacements = dict(Y=f'{d.year:04}', m=f'{d.month:02}', d=f'{d.day:02}',
                        j=f'{(d-date(d.year,1,1)).days+1:03}', a=DAYS[d.weekday()][:3], b=MONTHS[d.month-1], **{'%':'%'})
    print(re.sub(r'%(.)', lambda m: replacements[m[1]], fmt))
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
