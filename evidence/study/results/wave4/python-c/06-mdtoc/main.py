"""mdtoc: print a table of contents for a Markdown document."""
import re
import sys

HEADING_RE = re.compile(r"(#{1,6}) (.*)")
SLUG_KEEP = set("abcdefghijklmnopqrstuvwxyz0123456789-_")
ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def parse_args(argv):
    if not argv:
        return 6
    if len(argv) == 2 and argv[0] == "-l" and re.fullmatch(r"[1-6]", argv[1]):
        return int(argv[1])
    return None


def read_lines(data):
    text = data.decode("latin-1")
    if not text:
        return []
    lines = text.split("\n")
    if text.endswith("\n"):
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def headings(lines):
    """Yield (level, text) for each heading outside fenced code blocks."""
    in_code = False
    for line in lines:
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = HEADING_RE.fullmatch(line)
        if m:
            text = m.group(2).strip(" ")
            if text:
                yield len(m.group(1)), text


def base_slug(text):
    slug = "".join(ch for ch in text.translate(ASCII_LOWER).replace(" ", "-") if ch in SLUG_KEEP)
    return slug or "section"


def unique_slug(base, used):
    slug, n = base, 0
    while slug in used:
        n += 1
        slug = f"{base}-{n}"
    used.add(slug)
    return slug


def main(argv):
    max_level = parse_args(argv)
    if max_level is None:
        print("usage: mdtoc [-l LEVEL]  (LEVEL 1-6)", file=sys.stderr)
        return 2

    used = set()
    listed = []
    for level, text in headings(read_lines(sys.stdin.buffer.read())):
        slug = unique_slug(base_slug(text), used)
        if level <= max_level:
            listed.append((level, text, slug))

    if listed:
        top = min(level for level, _, _ in listed)
        out = [f"{'  ' * (level - top)}- [{text}](#{slug})\n" for level, text, slug in listed]
        sys.stdout.buffer.write("".join(out).encode("latin-1"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
