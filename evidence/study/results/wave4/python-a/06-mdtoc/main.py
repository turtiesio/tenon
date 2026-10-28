import re
import sys

HEADING_RE = re.compile(r"(#{1,6}) (.*)", re.DOTALL)
SLUG_KEEP_RE = re.compile(r"[^a-z0-9_-]")
FENCE = "```"


def usage(msg):
    print(f"mdtoc: {msg}", file=sys.stderr)
    sys.exit(2)


def parse_args(argv):
    if not argv:
        return 6
    if len(argv) == 2 and argv[0] == "-l" and argv[1] in ("1", "2", "3", "4", "5", "6"):
        return int(argv[1])
    usage("usage: mdtoc [-l LEVEL]  (LEVEL is 1-6)")


def headings(text):
    """Yield (level, text) for every heading outside code fences."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    in_code = False
    for line in lines:
        if line.endswith("\r"):
            line = line[:-1]
        if line.startswith(FENCE):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = HEADING_RE.fullmatch(line)
        if not m:
            continue
        title = m.group(2).strip(" ")
        if title:
            yield len(m.group(1)), title


def base_slug(title):
    ascii_lower = "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in title)
    slug = SLUG_KEEP_RE.sub("", ascii_lower.replace(" ", "-"))
    return slug or "section"


def unique_slug(base, used):
    slug = base
    n = 0
    while slug in used:
        n += 1
        slug = f"{base}-{n}"
    used.add(slug)
    return slug


def main():
    max_level = parse_args(sys.argv[1:])
    text = sys.stdin.buffer.read().decode("latin-1")

    used = set()
    entries = []
    for level, title in headings(text):
        slug = unique_slug(base_slug(title), used)
        if level <= max_level:
            entries.append((level, title, slug))

    if not entries:
        return
    min_level = min(level for level, _, _ in entries)
    out = [f"{'  ' * (level - min_level)}- [{title}](#{slug})\n" for level, title, slug in entries]
    sys.stdout.write("".join(out))


if __name__ == "__main__":
    main()
