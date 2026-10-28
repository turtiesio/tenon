"""hsize: print byte counts as human-readable sizes."""
import re
import sys

SIZE_RE = re.compile(r"[0-9]{1,16}")
UNITS = {
    1024: ["KiB", "MiB", "GiB", "TiB", "PiB"],
    1000: ["kB", "MB", "GB", "TB", "PB"],
}


class UsageError(Exception):
    pass


def human(value: int, base: int, places: int) -> str:
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
    whole, frac = divmod(rounded, scale)
    number = f"{whole}.{frac:0{places}d}" if places > 0 else str(whole)
    return f"{number} {UNITS[base][k - 1]}"


def parse_args(argv: list[str]) -> tuple[int, int, list[int]]:
    base, places, sizes = 1024, 1, []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "-s":
            base = 1000
        elif arg == "-p":
            if i + 1 >= len(argv) or argv[i + 1] not in ("0", "1", "2"):
                raise UsageError("-p needs a value of 0, 1 or 2")
            places = int(argv[i + 1])
            i += 1
        elif SIZE_RE.fullmatch(arg):
            sizes.append(int(arg))
        else:
            raise UsageError(f"invalid argument: {arg}")
        i += 1
    return base, places, sizes


def stdin_lines() -> list[str]:
    text = sys.stdin.buffer.read().decode("ascii", errors="replace")
    lines = text.split("\n")
    if text.endswith("\n"):
        lines.pop()
    elif text == "":
        lines = []
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def main(argv: list[str]) -> int:
    try:
        base, places, sizes = parse_args(argv)
    except UsageError as e:
        print(f"hsize: {e}", file=sys.stderr)
        print("usage: hsize [-s] [-p N] [SIZE...]", file=sys.stderr)
        return 2

    out = []
    status = 0
    if sizes:
        out = [human(v, base, places) for v in sizes]
    else:
        for line in stdin_lines():
            if SIZE_RE.fullmatch(line):
                out.append(human(int(line), base, places))
            else:
                out.append("?")
                status = 1
    sys.stdout.write("".join(line + "\n" for line in out))
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
