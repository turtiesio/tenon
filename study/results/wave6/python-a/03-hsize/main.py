import re
import sys

SIZE_RE = re.compile(r"[0-9]{1,16}")
BINARY_UNITS = ["KiB", "MiB", "GiB", "TiB", "PiB"]
DECIMAL_UNITS = ["kB", "MB", "GB", "TB", "PB"]


class UsageError(Exception):
    pass


def parse_args(argv):
    decimal = False
    places = 1
    sizes = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "-s":
            decimal = True
        elif arg == "-p":
            i += 1
            if i >= len(argv) or argv[i] not in ("0", "1", "2"):
                raise UsageError("-p needs 0, 1 or 2")
            places = int(argv[i])
        elif SIZE_RE.fullmatch(arg):
            sizes.append(int(arg))
        else:
            raise UsageError(f"bad argument: {arg}")
        i += 1
    return decimal, places, sizes


def format_size(value, decimal, places):
    base = 1000 if decimal else 1024
    units = DECIMAL_UNITS if decimal else BINARY_UNITS
    if value < base:
        return f"{value} B"
    k = 1
    while k < 5 and value >= base ** (k + 1):
        k += 1
    scale = 10 ** places
    while True:
        divisor = base ** k
        rounded = (2 * value * scale + divisor) // (2 * divisor)
        if rounded >= base * scale and k < 5:
            k += 1
            continue
        break
    text = str(rounded // scale)
    if places > 0:
        text += "." + str(rounded % scale).zfill(places)
    return f"{text} {units[k - 1]}"


def main(argv):
    try:
        decimal, places, sizes = parse_args(argv)
    except UsageError as e:
        print(f"hsize: {e}", file=sys.stderr)
        return 2

    bad = False
    out = []
    if sizes:
        out = [format_size(v, decimal, places) for v in sizes]
    else:
        text = sys.stdin.buffer.read().decode("latin-1")
        lines = text.split("\n")
        if lines[-1] == "":
            lines.pop()
        for line in lines:
            if line.endswith("\r"):
                line = line[:-1]
            if SIZE_RE.fullmatch(line):
                out.append(format_size(int(line), decimal, places))
            else:
                out.append("?")
                bad = True
    for line in out:
        print(line)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
