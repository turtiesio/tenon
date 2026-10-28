"""alertwin: sliding-window error alerting with a per-service cooldown."""
import re
import sys
from collections import deque

VALUE_RE = re.compile(r"[0-9]{1,9}")
EVENT_RE = re.compile(r"([0-9]{1,12}) ([a-z][a-z0-9-]{0,31}) (INFO|WARN|ERROR)")
# option -> (name, default, minimum)
OPTIONS = {"-w": ("window", 60, 1), "-t": ("threshold", 3, 1), "-c": ("cooldown", 300, 0)}


class UsageError(Exception):
    pass


class Service:
    def __init__(self):
        self.errors = 0
        self.warns = 0
        self.alerts = 0
        self.peak = 0
        self.window = deque()  # timestamps of recent ERROR events
        self.last_alert = None


def parse_args(argv):
    settings = {name: default for name, default, _ in OPTIONS.values()}
    i = 0
    while i < len(argv):
        opt = argv[i]
        if opt not in OPTIONS:
            raise UsageError(f"unexpected argument {opt!r}")
        if i + 1 >= len(argv):
            raise UsageError(f"{opt} needs a value")
        name, _, minimum = OPTIONS[opt]
        value = argv[i + 1]
        if not VALUE_RE.fullmatch(value) or int(value) < minimum:
            raise UsageError(f"bad value for {opt}: {value!r}")
        settings[name] = int(value)
        i += 2
    return settings["window"], settings["threshold"], settings["cooldown"]


def main(argv):
    try:
        window, threshold, cooldown = parse_args(argv)
    except UsageError as e:
        print(f"alertwin: {e}", file=sys.stderr)
        print("usage: alertwin [-w WINDOW] [-t THRESHOLD] [-c COOLDOWN]", file=sys.stderr)
        return 2

    lines = sys.stdin.buffer.read().decode("latin-1").split("\n")
    if lines[-1] == "":
        lines.pop()

    services = {}
    skipped = 0
    last_ts = None
    out = []
    for line in lines:
        if line.endswith("\r"):
            line = line[:-1]
        if line.strip(" ") == "":
            continue
        m = EVENT_RE.fullmatch(line)
        if not m:
            skipped += 1
            continue
        ts = int(m.group(1))
        if last_ts is not None and ts < last_ts:
            skipped += 1
            continue
        last_ts = ts
        name, level = m.group(2), m.group(3)
        service = services.setdefault(name, Service())
        if level == "WARN":
            service.warns += 1
        elif level == "ERROR":
            service.errors += 1
            recent = service.window
            recent.append(ts)
            while recent[0] <= ts - window:
                recent.popleft()
            count = len(recent)
            service.peak = max(service.peak, count)
            in_cooldown = service.last_alert is not None and ts - service.last_alert < cooldown
            if count >= threshold and not in_cooldown:
                service.alerts += 1
                service.last_alert = ts
                out.append(f"ALERT {ts} {name} {count}")

    for name in sorted(services):
        s = services[name]
        out.append(f"{name} errors={s.errors} warns={s.warns} alerts={s.alerts} peak={s.peak}")
    out.append(f"skipped={skipped}")
    sys.stdout.write("".join(line + "\n" for line in out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
