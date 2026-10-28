"""wrap: paragraph filler and justifier."""
import re
import sys

NUMBER = re.compile(r"[0-9]{1,4}")


class UsageError(Exception):
    pass


def parse_args(argv):
    values = {}
    justify = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-w", "-i"):
            if arg in values:
                raise UsageError(f"option {arg} given more than once")
            if i + 1 >= len(argv):
                raise UsageError(f"option {arg} needs a value")
            value = argv[i + 1]
            if not NUMBER.fullmatch(value):
                raise UsageError(f"bad value for {arg}: {value!r}")
            values[arg] = int(value)
            i += 2
        elif arg == "-j":
            if justify:
                raise UsageError("option -j given more than once")
            justify = True
            i += 1
        else:
            raise UsageError(f"unknown argument: {arg!r}")
    width = values.get("-w", 72)
    indent = values.get("-i", 0)
    if not 1 <= width <= 1000:
        raise UsageError(f"width out of range: {width}")
    if indent >= width:
        raise UsageError("indent must be smaller than width")
    return width, indent, justify


def read_lines(data):
    if not data:
        return []
    lines = data.split(b"\n")
    if lines[-1] == b"":
        lines.pop()
    result = []
    for line in lines:
        if line.endswith(b"\r"):
            line = line[:-1]
        if any(b < 0x20 or b > 0x7E for b in line):
            raise ValueError("input contains a non-printable byte")
        result.append(line.decode("ascii"))
    return result


def paragraphs(lines):
    words = []
    for line in lines:
        if line.strip(" "):
            words.extend(line.split())
        elif words:
            yield words
            words = []
    if words:
        yield words


def fill(words, width, indent):
    """Greedy fill; returns a list of (indent, words) per line."""
    lines = []
    pos = 0
    while pos < len(words):
        pad = indent if not lines else 0
        current = [words[pos]]
        length = pad + len(words[pos])
        pos += 1
        while pos < len(words) and length + 1 + len(words[pos]) <= width:
            length += 1 + len(words[pos])
            current.append(words[pos])
            pos += 1
        lines.append((pad, current))
    return lines


def render(pad, words, width, justify):
    if not justify or len(words) < 2:
        return " " * pad + " ".join(words)
    gaps = len(words) - 1
    spaces = width - pad - sum(len(w) for w in words)
    base, extra = divmod(spaces, gaps)
    parts = [" " * pad]
    for k, word in enumerate(words):
        parts.append(word)
        if k < gaps:
            parts.append(" " * (base + (1 if k < extra else 0)))
    return "".join(parts)


def main():
    try:
        width, indent, justify = parse_args(sys.argv[1:])
    except UsageError as e:
        print(f"wrap: {e}", file=sys.stderr)
        return 2
    try:
        lines = read_lines(sys.stdin.buffer.read())
    except ValueError as e:
        print(f"wrap: {e}", file=sys.stderr)
        return 1

    out = []
    for words in paragraphs(lines):
        if out:
            out.append("")
        filled = fill(words, width, indent)
        for n, (pad, line_words) in enumerate(filled):
            last = n == len(filled) - 1
            out.append(render(pad, line_words, width, justify and not last))
    sys.stdout.write("".join(line + "\n" for line in out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
