"""climate: per-station monthly or yearly temperature summary."""
import datetime
import re
import sys

DATE_RE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
TEMP_RE = re.compile(r"(-?)([0-9]{1,2})\.([0-9])")


def parse_reading(line: str) -> tuple[str, str, int] | None:
    """Return (station, date, tenths) for a valid reading, else None."""
    fields = line.split(";")
    if len(fields) != 3:
        return None
    station, date, temp = fields
    if not 1 <= len(station) <= 40 or station[0] == " " or station[-1] == " ":
        return None
    m = DATE_RE.fullmatch(date)
    if not m:
        return None
    try:
        datetime.date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:
        return None
    t = TEMP_RE.fullmatch(temp)
    if not t:
        return None
    tenths = int(t[2]) * 10 + int(t[3])
    return station, date, -tenths if t[1] else tenths


def fmt(tenths: int) -> str:
    sign = "-" if tenths < 0 else ""
    whole, frac = divmod(abs(tenths), 10)
    return f"{sign}{whole}.{frac}"


def rounded_mean(total: int, n: int) -> int:
    """total / n rounded to the nearest integer, halves away from zero."""
    q = (2 * abs(total) + n) // (2 * n)
    return -q if total < 0 else q


def read_lines(data: bytes) -> list[str]:
    text = data.decode("utf-8", errors="replace")
    lines = text.split("\n")
    if text.endswith("\n") or text == "":
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def main(argv: list[str]) -> int:
    if argv not in ([], ["-y"]):
        print("usage: climate [-y]", file=sys.stderr)
        return 2
    by_year = argv == ["-y"]

    latest: dict[tuple[str, str], int] = {}
    skipped = replaced = 0
    for line in read_lines(sys.stdin.buffer.read()):
        if line == "":
            continue
        reading = parse_reading(line)
        if reading is None:
            skipped += 1
            continue
        station, date, tenths = reading
        if (station, date) in latest:
            replaced += 1
        latest[(station, date)] = tenths

    groups: dict[tuple[str, str], list[int]] = {}
    for (station, date), tenths in latest.items():
        period = date[:4] if by_year else date[:7]
        groups.setdefault((station, period), []).append(tenths)

    out = []
    for station, period in sorted(groups, key=lambda k: (k[0].encode(), k[1])):
        temps = groups[(station, period)]
        mean = rounded_mean(sum(temps), len(temps))
        out.append(f"{station} {period} days={len(temps)} min={fmt(min(temps))} "
                   f"max={fmt(max(temps))} mean={fmt(mean)}\n")
    out.append(f"readings={len(latest)} skipped={skipped} replaced={replaced}\n")
    sys.stdout.write("".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
