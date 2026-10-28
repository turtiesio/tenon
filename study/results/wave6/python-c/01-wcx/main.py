"""wcx: count lines, words, characters and bytes."""
import sys

OPTIONS = {"-l": "lines", "-w": "words", "-m": "chars", "-c": "bytes"}
ORDER = ["lines", "words", "chars", "bytes"]


def count(data: bytes) -> dict:
    return {
        "lines": data.count(b"\n"),
        "words": len(data.split()),  # bytes.split() splits on ASCII whitespace
        "chars": len(data.decode("utf-8", errors="replace")),
        "bytes": len(data),
    }


def main(argv: list[str]) -> int:
    selected = set()
    files = []
    for arg in argv:
        if arg in OPTIONS:
            selected.add(OPTIONS[arg])
        elif arg.startswith("-"):
            print(f"wcx: invalid argument: {arg}", file=sys.stderr)
            print("usage: wcx [-l] [-w] [-m] [-c] [FILE...]", file=sys.stderr)
            return 2
        else:
            files.append(arg)
    if not selected:
        selected = {"lines", "words", "bytes"}
    columns = [c for c in ORDER if c in selected]

    rows = []  # (counts, label or None)
    status = 0
    if not files:
        rows.append((count(sys.stdin.buffer.read()), None))
    else:
        total = dict.fromkeys(ORDER, 0)
        for name in files:
            try:
                with open(name, "rb") as f:
                    data = f.read()
            except OSError as e:
                print(f"wcx: {name}: {e.strerror or e}", file=sys.stderr)
                status = 1
                continue
            counts = count(data)
            for key in ORDER:
                total[key] += counts[key]
            rows.append((counts, name))
        if len(files) >= 2:
            rows.append((total, "total"))

    width = max((len(str(r[0][c])) for r in rows for c in columns), default=1)
    out = []
    for counts, label in rows:
        line = " ".join(str(counts[c]).rjust(width) for c in columns)
        if label is not None:
            line += " " + label
        out.append(line + "\n")
    sys.stdout.write("".join(out))
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
