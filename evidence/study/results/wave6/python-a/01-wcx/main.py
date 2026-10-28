import sys

OPTIONS = {"-l", "-w", "-m", "-c"}


def count(data, selected):
    values = {
        "-l": data.count(b"\n"),
        "-w": len(data.split()),
        "-m": len(data.decode("utf-8", errors="replace")),
        "-c": len(data),
    }
    return [values[opt] for opt in ("-l", "-w", "-m", "-c") if opt in selected]


def main(argv):
    selected = set()
    names = []
    for arg in argv:
        if arg in OPTIONS:
            selected.add(arg)
        elif arg.startswith("-"):
            print(f"wcx: invalid option: {arg}", file=sys.stderr)
            return 2
        else:
            names.append(arg)
    if not selected:
        selected = {"-l", "-w", "-c"}

    rows = []  # (counts, label or None)
    failed = False
    if not names:
        rows.append((count(sys.stdin.buffer.read(), selected), None))
    else:
        for name in names:
            try:
                with open(name, "rb") as f:
                    data = f.read()
            except OSError as e:
                print(f"wcx: {name}: {e.strerror or e}", file=sys.stderr)
                failed = True
                continue
            rows.append((count(data, selected), name))
        if len(names) >= 2:
            totals = [sum(col) for col in zip(*(c for c, _ in rows))] or [0] * len(selected)
            rows.append((totals, "total"))

    width = max((len(str(n)) for counts, _ in rows for n in counts), default=1)
    for counts, label in rows:
        line = " ".join(str(n).rjust(width) for n in counts)
        if label is not None:
            line += " " + label
        print(line)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
