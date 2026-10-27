import re
import sys

OFFSET_RE = re.compile(r"[+-]?[0-9]{1,9}")
INDEX_RE = re.compile(r"[0-9]{1,9}")
TIME = r"([0-9]{2}):([0-5][0-9]):([0-5][0-9]),([0-9]{3})"
TIMING_RE = re.compile(TIME + " --> " + TIME)
BLANK_RE = re.compile(r"[ \t]*")


class InputError(Exception):
    pass


def read_lines():
    text = sys.stdin.buffer.read().decode("utf-8")
    if not text:
        return []
    lines = text.split("\n")
    if text.endswith("\n"):
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def blocks(lines):
    """Yield (first line number, lines) for each maximal run of non-blank lines."""
    current = []
    start = 0
    for lineno, line in enumerate(lines, start=1):
        if BLANK_RE.fullmatch(line):
            if current:
                yield start, current
                current = []
        else:
            if not current:
                start = lineno
            current.append(line)
    if current:
        yield start, current


def to_ms(h, m, s, ms):
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def parse_cue(lineno, block):
    if len(block) < 3:
        raise InputError(f"line {lineno}: a cue needs an index, a timing and text")
    if not INDEX_RE.fullmatch(block[0]):
        raise InputError(f"line {lineno}: malformed index line {block[0]!r}")
    match = TIMING_RE.fullmatch(block[1])
    if not match:
        raise InputError(f"line {lineno + 1}: malformed timing line {block[1]!r}")
    groups = match.groups()
    start, end = to_ms(*groups[:4]), to_ms(*groups[4:])
    if end <= start:
        raise InputError(f"line {lineno + 1}: end is not after start")
    return start, end, block[2:]


def format_time(ms):
    seconds, ms = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


def main():
    args = sys.argv[1:]
    if len(args) != 1 or not OFFSET_RE.fullmatch(args[0]):
        print("usage: srtfix OFFSET  (milliseconds, e.g. +1500 or -250)", file=sys.stderr)
        sys.exit(2)
    offset = int(args[0])

    try:
        cues = [parse_cue(lineno, block) for lineno, block in blocks(read_lines())]
    except InputError as e:
        print(f"srtfix: {e}", file=sys.stderr)
        sys.exit(1)

    shifted = []
    for start, end, text in cues:
        start, end = start + offset, end + offset
        if end <= 0:
            continue
        shifted.append((max(start, 0), end, text))
    shifted.sort(key=lambda cue: cue[0])  # stable: ties keep input order

    out = []
    for number, (start, end, text) in enumerate(shifted, start=1):
        out.append(f"{number}\n{format_time(start)} --> {format_time(end)}\n")
        out.extend(line + "\n" for line in text)
        out.append("\n")
    sys.stdout.buffer.write("".join(out).encode("utf-8"))


if __name__ == "__main__":
    main()
