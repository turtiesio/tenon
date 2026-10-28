"""lfagg: logfmt parser and group-by aggregator."""
import re
import sys

KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
NUMBER_RE = re.compile(r"-?[0-9]{1,15}")


class Malformed(Exception):
    pass


def parse_quoted(line, pos):
    """Parse a quoted value starting just after the opening quote.

    Return (value, position after the closing quote)."""
    chars = []
    n = len(line)
    while True:
        if pos >= n:
            raise Malformed("missing closing quote")
        c = line[pos]
        if c == '"':
            return "".join(chars), pos + 1
        if c == "\\":
            if pos + 1 < n and line[pos + 1] in '"\\':
                chars.append(line[pos + 1])
                pos += 2
                continue
            raise Malformed("bad escape")
        chars.append(c)
        pos += 1


def parse_line(line):
    """Return the line's pairs as a dict, or raise Malformed."""
    pairs = {}
    pos, n = 0, len(line)
    while True:
        while pos < n and line[pos] == " ":
            pos += 1
        if pos == n:
            return pairs
        m = KEY_RE.match(line, pos)
        if not m:
            raise Malformed("bad key")
        key = m.group()
        pos = m.end()
        if pos == n or line[pos] == " ":
            value = "true"
        elif line[pos] == "=":
            pos += 1
            if pos < n and line[pos] == '"':
                value, pos = parse_quoted(line, pos + 1)
                if pos < n and line[pos] != " ":
                    raise Malformed("junk after quoted value")
            else:
                end = line.find(" ", pos)
                if end == -1:
                    end = n
                value = line[pos:end]
                pos = end
                if '"' in value or "=" in value:
                    raise Malformed("bad bare value")
        else:
            raise Malformed("bad character after key")
        if key in pairs:
            raise Malformed("duplicate key")
        pairs[key] = value


def format_avg(total, n):
    """total / n rounded to 2 places, half away from zero."""
    scaled = (2 * abs(total) * 100 + n) // (2 * n)  # round(|total|*100/n)
    sign = "-" if total < 0 and scaled else ""
    return f"{sign}{scaled // 100}.{scaled % 100:02d}"


class Group:
    def __init__(self):
        self.count = 0
        self.values = []


def main(argv):
    if not 1 <= len(argv) <= 2 or not all(KEY_RE.fullmatch(a) for a in argv):
        print("usage: lfagg BY [FIELD]", file=sys.stderr)
        return 2
    by = argv[0]
    field = argv[1] if len(argv) == 2 else None

    data = sys.stdin.buffer.read().decode("latin-1")
    lines = data.split("\n")
    if lines[-1] == "":
        lines.pop()

    groups = {}
    valid = malformed = nokey = 0
    for line in lines:
        if line.endswith("\r"):
            line = line[:-1]
        if line.strip(" ") == "":
            continue
        try:
            pairs = parse_line(line)
        except Malformed:
            malformed += 1
            continue
        valid += 1
        if by not in pairs:
            nokey += 1
            continue
        group = groups.setdefault(pairs[by], Group())
        group.count += 1
        if field is not None:
            value = pairs.get(field)
            if value is not None and NUMBER_RE.fullmatch(value):
                group.values.append(int(value))

    out = []
    for name, group in sorted(groups.items(), key=lambda kv: (-kv[1].count, kv[0])):
        label = name if name != "" else '""'
        text = f"{label} count={group.count}"
        if field is not None:
            vals = group.values
            if vals:
                total = sum(vals)
                text += (f" n={len(vals)} sum={total} min={min(vals)} max={max(vals)}"
                         f" avg={format_avg(total, len(vals))}")
            else:
                text += " n=0 sum=0 min=- max=- avg=-"
        out.append(text + "\n")
    out.append(f"lines={valid} malformed={malformed} nokey={nokey}\n")
    sys.stdout.buffer.write("".join(out).encode("latin-1"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
