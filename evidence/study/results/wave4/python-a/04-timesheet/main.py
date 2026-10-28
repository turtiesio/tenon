import re
import sys
from collections import defaultdict

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
PUNCH_RE = re.compile(
    r"([a-z]{1,16}) (Mon|Tue|Wed|Thu|Fri|Sat|Sun) ([01][0-9]|2[0-3]):([0-5][0-9]) (IN|OUT)"
)
DAY_LIMIT = 480


def format_time(minutes):
    return f"{minutes // 60}:{minutes % 60:02d}"


def read_punches(text):
    """Return ({(name, day): [(minute, kind), ...]}, skipped_count)."""
    punches = defaultdict(list)
    skipped = 0
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    for line in lines:
        if line.endswith("\r"):
            line = line[:-1]
        if line.strip(" ") == "":
            continue
        m = PUNCH_RE.fullmatch(line)
        if not m:
            skipped += 1
            continue
        name, day, hh, mm, kind = m.groups()
        punches[(name, day)].append((int(hh) * 60 + int(mm), kind))
    return punches, skipped


def pair_day(entries):
    """Return (worked minutes, anomaly count) for one employee-day."""
    worked = 0
    anomalies = 0
    open_at = None
    for minute, kind in sorted(entries, key=lambda e: e[0]):  # stable
        if kind == "IN":
            if open_at is not None:
                anomalies += 1
            open_at = minute
        elif open_at is None:
            anomalies += 1
        else:
            worked += minute - open_at
            open_at = None
    if open_at is not None:
        anomalies += 1
    return worked, anomalies


def main():
    if len(sys.argv) > 1:
        print("timesheet: no arguments expected", file=sys.stderr)
        sys.exit(2)

    text = sys.stdin.buffer.read().decode("latin-1")
    punches, skipped = read_punches(text)

    employees = {}  # name -> {day: minutes}, anomalies tracked separately
    anomaly_counts = defaultdict(int)
    for (name, day), entries in punches.items():
        worked, anomalies = pair_day(entries)
        employees.setdefault(name, {})[day] = worked
        anomaly_counts[name] += anomalies

    out = []
    for name in sorted(employees):
        per_day = employees[name]
        total = sum(per_day.values())
        overtime = sum(max(0, m - DAY_LIMIT) for m in per_day.values())
        parts = [name]
        parts += [f"{d}={format_time(per_day[d])}" for d in DAYS if per_day.get(d, 0) > 0]
        parts.append(f"total={format_time(total)}")
        parts.append(f"overtime={format_time(overtime)}")
        parts.append(f"anomalies={anomaly_counts[name]}")
        out.append(" ".join(parts))
    out.append(f"skipped={skipped}")
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
