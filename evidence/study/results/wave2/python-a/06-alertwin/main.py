#!/usr/bin/env python3
"""alertwin: sliding-window error alerting with per-service cooldown."""

import re
import sys
from collections import deque
from dataclasses import dataclass, field

TS_RE = re.compile(r"[0-9]{1,12}")
SERVICE_RE = re.compile(r"[a-z][a-z0-9-]{0,31}")
VALUE_RE = re.compile(r"[0-9]{1,9}")
LEVELS = ("INFO", "WARN", "ERROR")

# option -> (name, minimum, default)
OPTIONS = {
    "-w": ("window", 1, 60),
    "-t": ("threshold", 1, 3),
    "-c": ("cooldown", 0, 300),
}


@dataclass
class Service:
    errors: int = 0
    warns: int = 0
    alerts: int = 0
    peak: int = 0
    last_alert: int | None = None
    recent: deque = field(default_factory=deque)  # error timestamps in the window


def parse_options(argv):
    """Return {'window': .., 'threshold': .., 'cooldown': ..} or None on a usage error."""
    settings = {name: default for name, _, default in OPTIONS.values()}
    i = 0
    while i < len(argv):
        spec = OPTIONS.get(argv[i])
        if spec is None or i + 1 >= len(argv):
            return None
        name, minimum, _ = spec
        raw = argv[i + 1]
        if not VALUE_RE.fullmatch(raw) or int(raw) < minimum:
            return None
        settings[name] = int(raw)
        i += 2
    return settings


def parse_event(line):
    """Return (ts, service, level) for a well-formed line, else None."""
    parts = line.split(" ")
    if len(parts) != 3:
        return None
    ts, service, level = parts
    if not (TS_RE.fullmatch(ts) and SERVICE_RE.fullmatch(service) and level in LEVELS):
        return None
    return int(ts), service, level


def main(argv):
    settings = parse_options(argv)
    if settings is None:
        print("usage: alertwin [-w WINDOW] [-t THRESHOLD] [-c COOLDOWN]", file=sys.stderr)
        return 2
    window, threshold, cooldown = settings["window"], settings["threshold"], settings["cooldown"]

    services = {}
    skipped = 0
    last_ts = None
    out = []

    for line in sys.stdin.buffer.read().decode("latin-1").split("\n"):
        if line.endswith("\r"):
            line = line[:-1]
        if line.strip(" ") == "":
            continue
        event = parse_event(line)
        if event is None or (last_ts is not None and event[0] < last_ts):
            skipped += 1
            continue
        t, name, level = event
        last_ts = t
        svc = services.setdefault(name, Service())

        if level == "WARN":
            svc.warns += 1
        elif level == "ERROR":
            svc.errors += 1
            svc.recent.append(t)
            while svc.recent[0] <= t - window:
                svc.recent.popleft()
            count = len(svc.recent)
            svc.peak = max(svc.peak, count)
            in_cooldown = svc.last_alert is not None and t - svc.last_alert < cooldown
            if count >= threshold and not in_cooldown:
                svc.alerts += 1
                svc.last_alert = t
                out.append(f"ALERT {t} {name} {count}")

    for name in sorted(services):
        s = services[name]
        out.append(f"{name} errors={s.errors} warns={s.warns} alerts={s.alerts} peak={s.peak}")
    out.append(f"skipped={skipped}")
    sys.stdout.write("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
