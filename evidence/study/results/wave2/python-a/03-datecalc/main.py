#!/usr/bin/env python3
"""datecalc: calendar date calculator for the proleptic Gregorian calendar."""

import calendar
import re
import sys
from datetime import date, timedelta

EXIT_OK, EXIT_BAD_DATE, EXIT_USAGE = 0, 1, 2

DATE_RE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
NUMBER_RE = re.compile(r"-?[0-9]{1,7}")

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DEFAULT_FORMAT = "%Y-%m-%d"

# Number of positional arguments each command takes.
COMMANDS = {"weekday": 1, "add": 2, "diff": 2, "addmonths": 2}


class UsageError(Exception):
    pass


class DateError(Exception):
    pass


def parse_date(text):
    m = DATE_RE.fullmatch(text)
    if not m:
        raise DateError(f"invalid date: {text!r}")
    try:
        return date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:  # year 0, month 13, Feb 30, ...
        raise DateError(f"invalid date: {text!r}") from None


def parse_number(text):
    if not NUMBER_RE.fullmatch(text):
        raise UsageError(f"malformed number: {text!r}")
    return int(text)


def check_format(fmt):
    """Raise UsageError if fmt contains an unknown or dangling directive."""
    i = 0
    while i < len(fmt):
        if fmt[i] == "%":
            if i + 1 >= len(fmt) or fmt[i + 1] not in "Ymdjab%":
                raise UsageError(f"bad format directive in {fmt!r}")
            i += 2
        else:
            i += 1


def format_date(fmt, d):
    replacements = {
        "Y": f"{d.year:04d}",
        "m": f"{d.month:02d}",
        "d": f"{d.day:02d}",
        "j": f"{d.timetuple().tm_yday:03d}",
        "a": WEEKDAYS[d.weekday()][:3],
        "b": MONTHS[d.month - 1],
        "%": "%",
    }
    return re.sub(r"%(.)", lambda m: replacements[m[1]], fmt, flags=re.DOTALL)


def add_days(d, n):
    try:
        return d + timedelta(days=n)
    except OverflowError:
        raise DateError("result out of range") from None


def add_months(d, n):
    index = d.year * 12 + (d.month - 1) + n
    year, month = divmod(index, 12)
    month += 1
    if not 1 <= year <= 9999:
        raise DateError("result out of range")
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def parse_args(argv):
    """Return (fmt, command, positional arguments)."""
    fmt = DEFAULT_FORMAT
    i = 0
    while i < len(argv) and argv[i].startswith("-"):
        if argv[i] != "-F":
            raise UsageError(f"unknown option {argv[i]}")
        if i + 1 >= len(argv):
            raise UsageError("-F requires an argument")
        fmt = argv[i + 1]
        i += 2
    if i >= len(argv):
        raise UsageError("missing command")
    command, args = argv[i], argv[i + 1:]
    if command not in COMMANDS:
        raise UsageError(f"unknown command {command!r}")
    if len(args) != COMMANDS[command]:
        raise UsageError(f"wrong number of arguments for {command}")
    return fmt, command, args


def run(argv):
    fmt, command, args = parse_args(argv)
    check_format(fmt)
    # All usage checks (including N) happen before any date is looked at.
    if command in ("add", "addmonths"):
        n = parse_number(args[1])

    if command == "weekday":
        return WEEKDAYS[parse_date(args[0]).weekday()]
    if command == "diff":
        d1, d2 = parse_date(args[0]), parse_date(args[1])
        return str((d2 - d1).days)
    d = parse_date(args[0])
    if command == "add":
        return format_date(fmt, add_days(d, n))
    return format_date(fmt, add_months(d, n))


def main(argv):
    try:
        output = run(argv)
    except UsageError as e:
        print(f"datecalc: {e}", file=sys.stderr)
        return EXIT_USAGE
    except DateError as e:
        print(f"datecalc: {e}", file=sys.stderr)
        return EXIT_BAD_DATE
    print(output)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
