import os
import re
import sys

OPTIONS = {"-b", "-w", "-s", "-v", "-i", "-f"}
INT_RE = re.compile(r"-?[0-9]{1,9}")
WIDTH_RE = re.compile(r"[1-9][0-9]?")


class UsageError(Exception):
    pass


def parse_args(argv):
    opts = {"-b": "t", "-w": "6", "-s": "\t", "-v": "1", "-i": "1", "-f": "rn"}
    path = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in OPTIONS:
            if i + 1 >= len(argv):
                raise UsageError(f"option {arg} needs a value")
            opts[arg] = argv[i + 1]
            i += 2
        elif arg.startswith("-"):
            raise UsageError(f"unknown argument: {arg}")
        else:
            if path is not None:
                raise UsageError("more than one FILE")
            path = arg
            i += 1

    if opts["-b"] not in ("a", "t", "n"):
        raise UsageError("bad -b value")
    if not WIDTH_RE.fullmatch(opts["-w"]) or int(opts["-w"]) > 20:
        raise UsageError("bad -w value")
    for name in ("-v", "-i"):
        if not INT_RE.fullmatch(opts[name]):
            raise UsageError(f"bad {name} value")
    if opts["-f"] not in ("ln", "rn", "rz"):
        raise UsageError("bad -f value")

    return {
        "style": opts["-b"],
        "width": int(opts["-w"]),
        "sep": os.fsencode(opts["-s"]),
        "start": int(opts["-v"]),
        "step": int(opts["-i"]),
        "format": opts["-f"],
        "path": path,
    }


def field(n, width, fmt):
    if fmt == "ln":
        return str(n).ljust(width)
    if fmt == "rn":
        return str(n).rjust(width)
    if n < 0:
        return "-" + str(-n).rjust(width - 1, "0")
    return str(n).rjust(width, "0")


def main():
    try:
        cfg = parse_args(sys.argv[1:])
    except UsageError as e:
        print(f"numlines: {e}", file=sys.stderr)
        return 2

    try:
        if cfg["path"] is None:
            data = sys.stdin.buffer.read()
        else:
            with open(cfg["path"], "rb") as f:
                data = f.read()
    except OSError as e:
        print(f"numlines: cannot read input: {e}", file=sys.stderr)
        return 1

    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()

    out = []
    number = cfg["start"]
    style = cfg["style"]
    for line in lines:
        if style == "a" or (style == "t" and line):
            out.append(field(number, cfg["width"], cfg["format"]).encode("ascii"))
            out.append(cfg["sep"])
            number += cfg["step"]
        out.append(line)
        out.append(b"\n")

    sys.stdout.buffer.write(b"".join(out))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
