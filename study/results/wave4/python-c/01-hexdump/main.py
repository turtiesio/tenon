"""hexdump: canonical hex and ASCII dump of a file or stdin."""
import re
import sys

USAGE = "usage: hexdump [-s SKIP] [-n LENGTH] [-w WIDTH] [FILE]"


class UsageError(Exception):
    pass


def parse_args(argv):
    skip, length, width, path = 0, None, 16, None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-s", "-n", "-w"):
            if i + 1 >= len(argv):
                raise UsageError(f"option {arg} requires a value")
            value = argv[i + 1]
            i += 2
            if arg == "-w":
                if not re.fullmatch(r"[0-9]{1,2}", value) or not 1 <= int(value) <= 32:
                    raise UsageError(f"invalid width: {value!r}")
                width = int(value)
            else:
                if not re.fullmatch(r"[0-9]{1,9}", value):
                    raise UsageError(f"invalid value for {arg}: {value!r}")
                if arg == "-s":
                    skip = int(value)
                else:
                    length = int(value)
            continue
        if arg.startswith("-") and arg != "-":
            raise UsageError(f"unknown option: {arg}")
        if path is not None:
            raise UsageError("more than one FILE given")
        path = arg
        i += 1
    return skip, length, width, path


def format_line(offset, chunk, width):
    fields = [f"{b:02x}" for b in chunk] + ["  "] * (width - len(chunk))
    text = "".join(chr(b) if 0x20 <= b <= 0x7E else "." for b in chunk)
    return f"{offset:08x}  {' '.join(fields)}  |{text}|\n"


def main(argv):
    try:
        skip, length, width, path = parse_args(argv)
    except UsageError as e:
        print(f"hexdump: {e}\n{USAGE}", file=sys.stderr)
        return 2

    if path is None or path == "-":
        data = sys.stdin.buffer.read()
    else:
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:
            print(f"hexdump: {path}: {e.strerror}", file=sys.stderr)
            return 1

    selected = data[skip:] if length is None else data[skip:skip + length]
    out = []
    for start in range(0, len(selected), width):
        out.append(format_line(skip + start, selected[start:start + width], width))
    out.append(f"{skip + len(selected):08x}\n")
    sys.stdout.write("".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
