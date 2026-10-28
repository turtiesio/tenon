import calendar
import re
import sys

DATE_RE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
TEMP_RE = re.compile(r"(-?)([0-9]{1,2})\.([0-9])")


def parse_reading(line):
    """Return (station, date, tenths) or None if the line is not a valid reading."""
    fields = line.split(";")
    if len(fields) != 3:
        return None
    station, date, temp = fields
    if not 1 <= len(station) <= 40 or station.startswith(" ") or station.endswith(" "):
        return None
    m = DATE_RE.fullmatch(date)
    if not m:
        return None
    year, month, day = (int(g) for g in m.groups())
    if not (1 <= year <= 9999 and 1 <= month <= 12):
        return None
    if not 1 <= day <= calendar.monthrange(year, month)[1]:
        return None
    m = TEMP_RE.fullmatch(temp)
    if not m:
        return None
    tenths = int(m.group(2)) * 10 + int(m.group(3))
    if m.group(1):
        tenths = -tenths
    return station, date, tenths


def format_tenths(t):
    sign = "-" if t < 0 else ""
    return f"{sign}{abs(t) // 10}.{abs(t) % 10}"


def mean_tenths(total, days):
    """total / days rounded to nearest, halves away from zero."""
    q = (2 * abs(total) + days) // (2 * days)
    return -q if total < 0 else q


def main(argv):
    if argv not in ([], ["-y"]):
        print("usage: climate [-y]", file=sys.stderr)
        return 2
    by_year = bool(argv)

    text = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()

    skipped = 0
    replaced = 0
    used = {}  # (station, date) -> tenths
    for line in lines:
        if line.endswith("\r"):
            line = line[:-1]
        if line == "":
            continue
        reading = parse_reading(line)
        if reading is None:
            skipped += 1
            continue
        station, date, tenths = reading
        if (station, date) in used:
            replaced += 1
        used[(station, date)] = tenths

    groups = {}  # (station, period) -> [temps]
    for (station, date), tenths in used.items():
        period = date[:4] if by_year else date[:7]
        groups.setdefault((station, period), []).append(tenths)

    out = []
    for (station, period) in sorted(groups, key=lambda k: (k[0].encode("utf-8"), k[1])):
        temps = groups[(station, period)]
        out.append(
            f"{station} {period} days={len(temps)} "
            f"min={format_tenths(min(temps))} max={format_tenths(max(temps))} "
            f"mean={format_tenths(mean_tenths(sum(temps), len(temps)))}\n"
        )
    out.append(f"readings={len(used)} skipped={skipped} replaced={replaced}\n")
    sys.stdout.write("".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
