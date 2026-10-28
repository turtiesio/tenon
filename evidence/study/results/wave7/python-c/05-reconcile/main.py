"""reconcile: match a bank statement against a ledger."""
import datetime
import re
import sys
from dataclasses import dataclass

DAYS_RULE = re.compile(r"0|[1-9][0-9]{0,2}")
LINE_RULE = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2}),"
    r"(-?(?:0|[1-9][0-9]{0,8})\.[0-9]{2}),"
    r"([^,]*)"
)
USAGE = "usage: reconcile [-d DAYS] BANK LEDGER"


class UsageError(Exception):
    pass


class InputError(Exception):
    pass


@dataclass
class Entry:
    line_no: int
    date: datetime.date
    cents: int
    text: str


def parse_args(args):
    days = 3
    files = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "-d":
            if i + 1 >= len(args):
                raise UsageError("-d needs a value")
            value = args[i + 1]
            if not DAYS_RULE.fullmatch(value) or int(value) > 365:
                raise UsageError(f"invalid DAYS: {value!r}")
            days = int(value)
            i += 2
            continue
        if arg.startswith("-"):
            raise UsageError(f"unknown option: {arg}")
        files.append(arg)
        i += 1
    if len(files) != 2:
        raise UsageError("exactly two files are needed")
    return days, files[0], files[1]


def parse_cents(amount):
    negative = amount.startswith("-")
    units, frac = amount.lstrip("-").split(".")
    cents = int(units) * 100 + int(frac)
    return -cents if negative else cents


def format_cents(cents):
    sign = "-" if cents < 0 else ""
    units, frac = divmod(abs(cents), 100)
    return f"{sign}{units}.{frac:02d}"


def valid_text(text):
    return (
        1 <= len(text) <= 40
        and all(" " <= ch <= "~" and ch != "," for ch in text)
        and not text.startswith(" ")
        and not text.endswith(" ")
    )


def parse_line(line):
    m = LINE_RULE.fullmatch(line)
    if not m or not valid_text(m.group(5)):
        return None
    year, month, day = (int(g) for g in m.group(1, 2, 3))
    if not 1970 <= year <= 2099:
        return None
    try:
        date = datetime.date(year, month, day)
    except ValueError:
        return None
    return date, parse_cents(m.group(4)), m.group(5)


def read_entries(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        raise InputError(f"{path}: {e.strerror}")
    text = data.decode("latin-1")
    lines = text.split("\n") if text else []
    if text.endswith("\n"):
        lines.pop()
    entries = []
    for line_no, line in enumerate(lines, start=1):
        if line.endswith("\r"):
            line = line[:-1]
        if line == "":
            continue
        parsed = parse_line(line)
        if parsed is None:
            raise InputError(f"{path}: line {line_no}: invalid line")
        entries.append(Entry(line_no, *parsed))
    return entries


def reconcile(bank, ledger, days):
    """Greedy matching; returns (matches, unmatched bank, unmatched ledger)."""
    matched_ledger = set()
    matches = []
    bank_only = []
    for b in bank:
        best = None
        for idx, k in enumerate(ledger):
            if idx in matched_ledger or k.cents != b.cents:
                continue
            distance = abs((k.date - b.date).days)
            if distance > days:
                continue
            if best is None or distance < best[0]:
                best = (distance, idx)
        if best is None:
            bank_only.append(b)
        else:
            distance, idx = best
            matched_ledger.add(idx)
            matches.append((b, ledger[idx], distance))
    ledger_only = [k for idx, k in enumerate(ledger) if idx not in matched_ledger]
    return matches, bank_only, ledger_only


def main(argv):
    try:
        days, bank_path, ledger_path = parse_args(argv)
    except UsageError as e:
        print(f"reconcile: {e}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    try:
        bank = read_entries(bank_path)
        ledger = read_entries(ledger_path)
    except InputError as e:
        print(f"reconcile: {e}", file=sys.stderr)
        return 1

    matches, bank_only, ledger_only = reconcile(bank, ledger, days)
    out = []
    for b, k, distance in matches:
        out.append(f"M {b.line_no} {k.line_no} {format_cents(b.cents)} {distance}")
    for tag, entries in (("B", bank_only), ("L", ledger_only)):
        for e in entries:
            out.append(f"{tag} {e.line_no} {e.date.isoformat()} {format_cents(e.cents)} {e.text}")
    diff = sum(e.cents for e in bank_only) - sum(e.cents for e in ledger_only)
    out.append(
        f"matched={len(matches)} bank_only={len(bank_only)} "
        f"ledger_only={len(ledger_only)} diff={format_cents(diff)}"
    )
    sys.stdout.write("".join(line + "\n" for line in out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
