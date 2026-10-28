import re
import sys

NUM = re.compile(r"[0-9]{1,9}")
WIDTH_RE = re.compile(r"[0-9]{1,2}")


def usage(msg):
    print(f"hexdump: {msg}", file=sys.stderr)
    sys.exit(2)


def parse_args(argv):
    skip, length, width, path = 0, None, 16, None
    have_file = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-s", "-n", "-w"):
            if i + 1 >= len(argv):
                usage(f"option {arg} needs a value")
            value = argv[i + 1]
            i += 2
            if arg == "-w":
                if not WIDTH_RE.fullmatch(value) or not 1 <= int(value) <= 32:
                    usage(f"bad width: {value!r}")
                width = int(value)
            else:
                if not NUM.fullmatch(value):
                    usage(f"bad value for {arg}: {value!r}")
                if arg == "-s":
                    skip = int(value)
                else:
                    length = int(value)
            continue
        if arg != "-" and arg.startswith("-"):
            usage(f"unknown option: {arg}")
        if have_file:
            usage("more than one FILE")
        have_file = True
        path = None if arg == "-" else arg
        i += 1
    return skip, length, width, path


def format_line(offset, chunk, width):
    hex_area = " ".join(f"{b:02x}" for b in chunk)
    hex_area = hex_area.ljust(3 * width - 1)
    text = "".join(chr(b) if 0x20 <= b <= 0x7E else "." for b in chunk)
    return f"{offset:08x}  {hex_area}  |{text}|"


def main():
    skip, length, width, path = parse_args(sys.argv[1:])
    try:
        if path is None:
            data = sys.stdin.buffer.read()
        else:
            with open(path, "rb") as f:
                data = f.read()
    except OSError as e:
        print(f"hexdump: cannot read {path}: {e}", file=sys.stderr)
        sys.exit(1)

    selected = data[skip:]
    if length is not None:
        selected = selected[:length]

    out = []
    for start in range(0, len(selected), width):
        out.append(format_line(skip + start, selected[start:start + width], width))
    out.append(f"{skip + len(selected):08x}")
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
