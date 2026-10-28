import calendar
import datetime as dt
import re
import sys

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

def main():
    args = sys.argv[1:]
    fmt = '%Y-%m-%d'
    while args and args[0].startswith('-'):
        if args[0] != '-F' or len(args) < 2:
            return 2
        fmt = args[1]
        args = args[2:]
    if not args or args[0] not in ('weekday', 'add', 'diff', 'addmonths'):
        return 2
    command, *values = args
    if len(values) != (1 if command == 'weekday' else 2):
        return 2
    if re.search(r'%(?:[^Ymdjab%]|$)', fmt.replace('%%', '')):
        return 2
    if command in ('add', 'addmonths') and not re.fullmatch(r'-?[0-9]{1,7}', values[1]):
        return 2
    dates = values if command == 'diff' else values[:1]
    parsed = []
    for value in dates:
        if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
            return 1
        try:
            parsed.append(dt.date.fromisoformat(value))
        except ValueError:
            return 1
    date = parsed[0]
    if command == 'weekday':
        print(DAYS[date.weekday()])
        return 0
    if command == 'diff':
        print((parsed[1] - date).days)
        return 0
    count = int(values[1])
    try:
        if command == 'add':
            date += dt.timedelta(days=count)
        else:
            year, month = divmod((date.year - 1) * 12 + date.month - 1 + count, 12)
            year += 1
            month += 1
            if not 1 <= year <= 9999:
                return 1
            date = dt.date(year, month, min(date.day, calendar.monthrange(year, month)[1]))
    except (OverflowError, ValueError):
        return 1
    replacements = {'Y': f'{date.year:04}', 'm': f'{date.month:02}', 'd': f'{date.day:02}', 'j': f'{date.timetuple().tm_yday:03}', 'a': DAYS[date.weekday()][:3], 'b': MONTHS[date.month - 1], '%': '%'}
    print(re.sub(r'%(.)', lambda m: replacements[m[1]], fmt))
    return 0

if __name__ == '__main__':
    sys.exit(main())
