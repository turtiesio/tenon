import re
import sys

OFFSET_RE = re.compile(r"[+-]?[0-9]{1,9}")
INDEX_RE = re.compile(r"[0-9]{1,9}")
TIME = r"([0-9]{2}):([0-5][0-9]):([0-5][0-9]),([0-9]{3})"
TIMING_RE = re.compile(TIME + " --> " + TIME)
BLANK_RE = re.compile(r"[ \t]*")


class InvalidInput(Exception):
    pass


def to_ms(h, m, s, ms):
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def format_ms(total):
    total, ms = divmod(total, 1000)
    total, s = divmod(total, 60)
    h, m = divmod(total, 60)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def split_blocks(lines):
    blocks = []
    current = []
    for line in lines:
        if BLANK_RE.fullmatch(line):
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def parse_cue(block):
    if len(block) < 3:
        raise InvalidInput("cue needs an index, a timing line and text")
    if not INDEX_RE.fullmatch(block[0]):
        raise InvalidInput("bad index line: " + block[0])
    m = TIMING_RE.fullmatch(block[1])
    if not m:
        raise InvalidInput("bad timing line: " + block[1])
    start = to_ms(*m.group(1, 2, 3, 4))
    end = to_ms(*m.group(5, 6, 7, 8))
    if end <= start:
        raise InvalidInput("end must be after start: " + block[1])
    return start, end, block[2:]


def main():
    args = sys.argv[1:]
    if len(args) != 1 or not OFFSET_RE.fullmatch(args[0]):
        print("usage: srtfix OFFSET", file=sys.stderr)
        return 2
    offset = int(args[0])

    text = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    lines = [line[:-1] if line.endswith("\r") else line for line in lines]

    try:
        cues = [parse_cue(b) for b in split_blocks(lines)]
    except InvalidInput as e:
        print("srtfix: " + str(e), file=sys.stderr)
        return 1

    shifted = []
    for start, end, body in cues:
        start += offset
        end += offset
        if end <= 0:
            continue
        shifted.append((max(start, 0), end, body))
    shifted.sort(key=lambda cue: cue[0])  # stable

    out = []
    for number, (start, end, body) in enumerate(shifted, 1):
        out.append(str(number))
        out.append(format_ms(start) + " --> " + format_ms(end))
        out.extend(body)
        out.append("")
    if out:
        sys.stdout.write("\n".join(out) + "\n")
    return 0


sys.exit(main())
