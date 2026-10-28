"""numlines: number the lines of a text."""
import re
import sys


class UsageError(Exception):
    pass


OPTION_RULES = {
    "-b": re.compile(r"[atn]"),
    "-w": re.compile(r"[1-9][0-9]?"),
    "-s": None,
    "-v": re.compile(r"-?[0-9]{1,9}"),
    "-i": re.compile(r"-?[0-9]{1,9}"),
    "-f": re.compile(r"ln|rn|rz"),
}


def parse_args(args):
    opts = {"-b": "t", "-w": "6", "-s": "\t", "-v": "1", "-i": "1", "-f": "rn"}
    path = None
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("-"):
            if arg not in OPTION_RULES:
                raise UsageError(f"unknown option: {arg}")
            if i + 1 >= len(args):
                raise UsageError(f"option {arg} needs a value")
            value = args[i + 1]
            rule = OPTION_RULES[arg]
            if rule is not None and not rule.fullmatch(value):
                raise UsageError(f"invalid value for {arg}: {value!r}")
            opts[arg] = value
            i += 2
        else:
            if path is not None:
                raise UsageError("at most one FILE may be given")
            path = arg
            i += 1
    width = int(opts["-w"])
    if width > 20:
        raise UsageError("width must be at most 20")
    return {
        "style": opts["-b"],
        "width": width,
        "sep": opts["-s"].encode("utf-8", "surrogateescape"),
        "start": int(opts["-v"]),
        "step": int(opts["-i"]),
        "format": opts["-f"],
        "path": path,
    }


def format_number(n, width, fmt):
    if fmt == "rn":
        return str(n).rjust(width)
    if fmt == "ln":
        return str(n).ljust(width)
    digits = str(abs(n))
    if n < 0:
        return "-" + digits.rjust(width - 1, "0")
    return digits.rjust(width, "0")


def split_lines(data):
    if not data:
        return []
    lines = data.split(b"\n")
    if data.endswith(b"\n"):
        lines.pop()
    return lines


def main(argv):
    try:
        cfg = parse_args(argv)
    except UsageError as e:
        print(f"numlines: {e}", file=sys.stderr)
        print("usage: numlines [-b STYLE] [-w WIDTH] [-s SEP] [-v START] [-i STEP] [-f FORMAT] [FILE]",
              file=sys.stderr)
        return 2

    if cfg["path"] is not None:
        try:
            with open(cfg["path"], "rb") as f:
                data = f.read()
        except OSError as e:
            print(f"numlines: {cfg['path']}: {e.strerror}", file=sys.stderr)
            return 1
    else:
        data = sys.stdin.buffer.read()

    out = []
    number = cfg["start"]
    for line in split_lines(data):
        numbered = cfg["style"] == "a" or (cfg["style"] == "t" and line != b"")
        if numbered:
            field = format_number(number, cfg["width"], cfg["format"]).encode("ascii")
            out.append(field + cfg["sep"] + line + b"\n")
            number += cfg["step"]
        else:
            out.append(line + b"\n")
    sys.stdout.buffer.write(b"".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
