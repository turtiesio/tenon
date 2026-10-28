"""timesheet: weekly hours per employee from clock-in/clock-out punches."""
import re
import sys
from collections import defaultdict

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
PUNCH_RE = re.compile(
    r"([a-z]{1,16}) (Mon|Tue|Wed|Thu|Fri|Sat|Sun) ([01][0-9]|2[0-3]):([0-5][0-9]) (IN|OUT)"
)
REGULAR_DAY = 480


def read_lines(data):
    text = data.decode("latin-1")
    if not text:
        return []
    lines = text.split("\n")
    if text.endswith("\n"):
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def pair_day(punches):
    """Return (minutes, anomalies) for one employee-day of (minute, kind) punches."""
    minutes = anomalies = 0
    open_at = None
    for at, kind in sorted(punches, key=lambda p: p[0]):  # sorted() is stable
        if kind == "IN":
            if open_at is not None:
                anomalies += 1
            open_at = at
        elif open_at is not None:
            minutes += at - open_at
            open_at = None
        else:
            anomalies += 1
    if open_at is not None:
        anomalies += 1
    return minutes, anomalies


def fmt(minutes):
    return f"{minutes // 60}:{minutes % 60:02d}"


def main(argv):
    if argv:
        print("usage: timesheet  (reads punches from stdin)", file=sys.stderr)
        return 2

    punches = defaultdict(lambda: defaultdict(list))  # name -> day -> [(minute, kind)]
    skipped = 0
    for line in read_lines(sys.stdin.buffer.read()):
        if not line.strip(" "):
            continue
        m = PUNCH_RE.fullmatch(line)
        if not m:
            skipped += 1
            continue
        name, day, hh, mm, kind = m.groups()
        punches[name][day].append((int(hh) * 60 + int(mm), kind))

    out = []
    for name in sorted(punches):
        items, total, overtime, anomalies = [], 0, 0, 0
        for day in DAYS:
            if day not in punches[name]:
                continue
            minutes, bad = pair_day(punches[name][day])
            anomalies += bad
            total += minutes
            overtime += max(0, minutes - REGULAR_DAY)
            if minutes > 0:
                items.append(f"{day}={fmt(minutes)}")
        fields = [name, *items, f"total={fmt(total)}", f"overtime={fmt(overtime)}",
                  f"anomalies={anomalies}"]
        out.append(" ".join(fields) + "\n")
    out.append(f"skipped={skipped}\n")
    sys.stdout.write("".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
