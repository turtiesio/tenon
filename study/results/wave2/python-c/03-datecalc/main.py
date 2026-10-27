"""datecalc: proleptic Gregorian date calculator."""
import calendar
import datetime
import re
import sys

DATE_RE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
N_RE = re.compile(r"-?[0-9]{1,7}")
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
# Number of positional arguments, and which of them are N (the rest are DATEs).
COMMANDS = {
    "weekday": ("D",),
    "add": ("D", "N"),
    "diff": ("D", "D"),
    "addmonths": ("D", "N"),
}
FMT_DIRECTIVES = set("Ymdjab%")


class UsageError(Exception):
    pass


class DateError(Exception):
    pass


def check_format(fmt):
    i = 0
    while i < len(fmt):
        if fmt[i] == "%":
            if i + 1 >= len(fmt) or fmt[i + 1] not in FMT_DIRECTIVES:
                raise UsageError(f"invalid format: {fmt!r}")
            i += 2
        else:
            i += 1


def format_date(d, fmt):
    replacements = {
        "Y": f"{d.year:04d}",
        "m": f"{d.month:02d}",
        "d": f"{d.day:02d}",
        "j": f"{d.timetuple().tm_yday:03d}",
        "a": WEEKDAYS[d.weekday()][:3],
        "b": MONTH_ABBR[d.month - 1],
        "%": "%",
    }
    out = []
    i = 0
    while i < len(fmt):
        if fmt[i] == "%":
            out.append(replacements[fmt[i + 1]])
            i += 2
        else:
            out.append(fmt[i])
            i += 1
    return "".join(out)


def parse_date(text):
    m = DATE_RE.fullmatch(text)
    if not m:
        raise DateError(f"invalid date: {text!r}")
    try:
        return datetime.date(*(int(g) for g in m.groups()))
    except ValueError:
        raise DateError(f"invalid date: {text!r}") from None


def add_months(d, n):
    index = d.year * 12 + (d.month - 1) + n
    year, month0 = divmod(index, 12)
    if not datetime.MINYEAR <= year <= datetime.MAXYEAR:
        raise DateError("result out of range")
    month = month0 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def parse_args(argv):
    fmt = "%Y-%m-%d"
    i = 0
    while i < len(argv) and argv[i].startswith("-"):
        if argv[i] != "-F":
            raise UsageError(f"unknown option {argv[i]}")
        if i + 1 >= len(argv):
            raise UsageError("-F needs an argument")
        fmt = argv[i + 1]
        i += 2
    if i >= len(argv):
        raise UsageError("missing command")
    command, args = argv[i], argv[i + 1:]
    if command not in COMMANDS:
        raise UsageError(f"unknown command {command}")
    kinds = COMMANDS[command]
    if len(args) != len(kinds):
        raise UsageError(f"{command}: wrong number of arguments")
    for kind, arg in zip(kinds, args):
        if kind == "N" and not N_RE.fullmatch(arg):
            raise UsageError(f"malformed number {arg!r}")
    check_format(fmt)
    return fmt, command, args


def run(fmt, command, args):
    if command == "weekday":
        return WEEKDAYS[parse_date(args[0]).weekday()]
    if command == "diff":
        return str((parse_date(args[1]) - parse_date(args[0])).days)
    d, n = parse_date(args[0]), int(args[1])
    if command == "add":
        try:
            result = d + datetime.timedelta(days=n)
        except OverflowError:
            raise DateError("result out of range") from None
    else:
        result = add_months(d, n)
    return format_date(result, fmt)


def main(argv):
    try:
        fmt, command, args = parse_args(argv)
    except UsageError as e:
        print(f"datecalc: {e}", file=sys.stderr)
        return 2
    try:
        print(run(fmt, command, args))
    except DateError as e:
        print(f"datecalc: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
