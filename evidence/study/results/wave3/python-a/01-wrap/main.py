import re
import sys

DEFAULT_WIDTH = 72
NUMBER = re.compile(r"[0-9]{1,4}")


class UsageError(Exception):
    pass


def parse_number(text):
    if not NUMBER.fullmatch(text):
        raise UsageError(f"malformed number: {text!r}")
    return int(text)


def parse_args(argv):
    width = None
    indent = None
    justify = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-w", "-i"):
            if i + 1 >= len(argv):
                raise UsageError(f"{arg} needs a value")
            value = parse_number(argv[i + 1])
            i += 2
            if arg == "-w":
                if width is not None:
                    raise UsageError("-w given more than once")
                width = value
            else:
                if indent is not None:
                    raise UsageError("-i given more than once")
                indent = value
        elif arg == "-j":
            if justify:
                raise UsageError("-j given more than once")
            justify = True
            i += 1
        else:
            raise UsageError(f"unknown argument: {arg!r}")
    if width is None:
        width = DEFAULT_WIDTH
    if indent is None:
        indent = 0
    if not 1 <= width <= 1000:
        raise UsageError("width out of range")
    if indent >= width:
        raise UsageError("indent must be smaller than width")
    return width, indent, justify


def read_lines(data):
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    result = []
    for raw in lines:
        if raw.endswith(b"\r"):
            raw = raw[:-1]
        if any(b != 0x20 and not 0x21 <= b <= 0x7E for b in raw):
            return None
        result.append(raw.decode("ascii"))
    return result


def paragraphs(lines):
    current = []
    for line in lines:
        if line.strip(" "):
            current.extend(line.split())
        elif current:
            yield current
            current = []
    if current:
        yield current


def fill(words, width, indent):
    """Greedy fill; returns a list of (indent, words) lines."""
    lines = []
    line = [words[0]]
    length = indent + len(words[0])
    line_indent = indent
    for word in words[1:]:
        if length + 1 + len(word) <= width:
            line.append(word)
            length += 1 + len(word)
        else:
            lines.append((line_indent, line))
            line = [word]
            line_indent = 0
            length = len(word)
    lines.append((line_indent, line))
    return lines


def justify_line(line_indent, words, width):
    gaps = len(words) - 1
    spaces = width - line_indent - sum(len(w) for w in words)
    each, extra = divmod(spaces, gaps)
    out = [words[0]]
    for n, word in enumerate(words[1:]):
        out.append(" " * (each + (1 if n < extra else 0)))
        out.append(word)
    return " " * line_indent + "".join(out)


def format_paragraph(words, width, indent, justify):
    lines = fill(words, width, indent)
    out = []
    for n, (line_indent, line_words) in enumerate(lines):
        is_last = n == len(lines) - 1
        if justify and not is_last and len(line_words) >= 2:
            out.append(justify_line(line_indent, line_words, width))
        else:
            out.append(" " * line_indent + " ".join(line_words))
    return out


def main():
    try:
        width, indent, justify = parse_args(sys.argv[1:])
    except UsageError as e:
        print(f"wrap: {e}", file=sys.stderr)
        print("usage: wrap [-w WIDTH] [-i INDENT] [-j]", file=sys.stderr)
        return 2

    lines = read_lines(sys.stdin.buffer.read())
    if lines is None:
        print("wrap: invalid character in input", file=sys.stderr)
        return 1

    blocks = ["\n".join(format_paragraph(p, width, indent, justify) ) + "\n"
              for p in paragraphs(lines)]
    sys.stdout.write("\n".join(blocks))
    return 0


sys.exit(main())
