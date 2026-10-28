import datetime
import re
import sys
from dataclasses import dataclass

DATE_RE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
AMOUNT_RE = re.compile(r"(-?)(0|[1-9][0-9]{0,8})\.([0-9]{2})")
DAYS_RE = re.compile(r"0|[1-9][0-9]{0,2}")
TEXT_RE = re.compile(r"[ -~]{1,40}")


class UsageError(Exception):
    pass


class InputError(Exception):
    pass


@dataclass
class Entry:
    number: int
    date_text: str
    date: datetime.date
    cents: int
    text: str


def parse_args(argv):
    days = 3
    files = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "-d":
            if i + 1 >= len(argv):
                raise UsageError("-d needs a value")
            value = argv[i + 1]
            if not DAYS_RE.fullmatch(value) or int(value) > 365:
                raise UsageError(f"bad DAYS: {value!r}")
            days = int(value)
            i += 2
        elif arg.startswith("-"):
            raise UsageError(f"unknown argument: {arg}")
        else:
            files.append(arg)
            i += 1
    if len(files) != 2:
        raise UsageError("expected exactly two files: BANK LEDGER")
    return days, files[0], files[1]


def parse_line(number, line):
    parts = line.split(",")
    if len(parts) != 3:
        raise ValueError("expected <date>,<amount>,<text>")
    date_text, amount_text, text = parts

    m = DATE_RE.fullmatch(date_text)
    if m is None:
        raise ValueError("bad date")
    year, month, day = (int(g) for g in m.groups())
    if not 1970 <= year <= 2099:
        raise ValueError("year out of range")
    try:
        date = datetime.date(year, month, day)
    except ValueError:
        raise ValueError("not a calendar date") from None

    m = AMOUNT_RE.fullmatch(amount_text)
    if m is None:
        raise ValueError("bad amount")
    cents = int(m.group(2)) * 100 + int(m.group(3))
    if m.group(1):
        cents = -cents

    if not TEXT_RE.fullmatch(text) or text != text.strip(" "):
        raise ValueError("bad text")
    return Entry(number, date_text, date, cents, text)


def read_entries(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        raise InputError(f"{path}: {e.strerror or e}") from None
    try:
        content = data.decode("ascii")
    except UnicodeDecodeError:
        raise InputError(f"{path}: not ASCII text") from None

    lines = content.split("\n")
    if lines[-1] == "":
        lines.pop()

    entries = []
    for number, line in enumerate(lines, start=1):
        if line.endswith("\r"):
            line = line[:-1]
        if line == "":
            continue
        try:
            entries.append(parse_line(number, line))
        except ValueError as e:
            raise InputError(f"{path}:{number}: {e}") from None
    return entries


def money(cents):
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(cents), 100)
    return f"{sign}{whole}.{frac:02d}"


def reconcile(bank, ledger, max_days):
    matches = []
    unmatched_bank = []
    used = set()
    for b in bank:
        best = None
        for l in ledger:
            if l.number in used or l.cents != b.cents:
                continue
            distance = abs((b.date - l.date).days)
            if distance > max_days:
                continue
            if best is None or (distance, l.number) < (best[0], best[1].number):
                best = (distance, l)
        if best is None:
            unmatched_bank.append(b)
        else:
            distance, l = best
            used.add(l.number)
            matches.append((b, l, distance))
    unmatched_ledger = [l for l in ledger if l.number not in used]
    return matches, unmatched_bank, unmatched_ledger


def main():
    try:
        max_days, bank_path, ledger_path = parse_args(sys.argv[1:])
    except UsageError as e:
        print(f"reconcile: {e}", file=sys.stderr)
        return 2

    try:
        bank = read_entries(bank_path)
        ledger = read_entries(ledger_path)
    except InputError as e:
        print(f"reconcile: {e}", file=sys.stderr)
        return 1

    matches, bank_only, ledger_only = reconcile(bank, ledger, max_days)

    out = []
    for b, l, distance in matches:
        out.append(f"M {b.number} {l.number} {money(b.cents)} {distance}")
    for b in bank_only:
        out.append(f"B {b.number} {b.date_text} {money(b.cents)} {b.text}")
    for l in ledger_only:
        out.append(f"L {l.number} {l.date_text} {money(l.cents)} {l.text}")
    diff = sum(b.cents for b in bank_only) - sum(l.cents for l in ledger_only)
    out.append(
        f"matched={len(matches)} bank_only={len(bank_only)} "
        f"ledger_only={len(ledger_only)} diff={money(diff)}"
    )
    sys.stdout.write("".join(line + "\n" for line in out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
