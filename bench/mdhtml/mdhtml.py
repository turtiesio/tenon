# mdhtml: Markdown subset to HTML, stdin to stdout.
import re
import sys
import threading

WS = " \t\n\r\f"
SPACE = " \t\n\r"
SPECIAL = re.compile(r"[`*\[]")
ESC = re.compile(r'[&<>"]')
ESC_MAP = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}


def esc(s):
    return ESC.sub(lambda m: ESC_MAP[m.group()], s)


# ---- inline ----

def code_span(s, i):
    j = s.find("`", i + 1)
    if j < 0 or j == i + 1:
        return None
    return "<code>" + esc(s[i + 1:j]) + "</code>", j + 1


def bold(s, i):
    n = len(s)
    start = i + 2
    if start >= n or s[start] in SPACE:
        return None
    j = start + 1
    while j + 1 < n:
        if s[j] == "*" and s[j + 1] == "*" and s[j - 1] not in SPACE:
            while j + 2 < n and s[j + 2] == "*":
                j += 1
            return "<strong>" + inline(s[start:j]) + "</strong>", j + 2
        j += 1
    return None


def em(s, i):
    n = len(s)
    start = i + 1
    if start >= n or s[start] in SPACE:
        return None
    j = start + 1
    while j < n:
        if s[j] == "*":
            if j + 1 < n and s[j + 1] == "*":
                j += 2
                continue
            if s[j - 1] not in SPACE:
                return "<em>" + inline(s[start:j]) + "</em>", j + 1
        j += 1
    return None


def link(s, i):
    n = len(s)
    j = s.find("]", i + 1)
    if j < 0:
        j = n
    if j == i + 1 or j + 1 >= n or s[j + 1] != "(":
        return None
    k = j + 2
    while k < n and s[k] != ")" and s[k] not in SPACE:
        k += 1
    if k >= n or k == j + 2 or s[k] != ")":
        return None
    href = esc(s[j + 2:k])
    return '<a href="' + href + '">' + inline(s[i + 1:j]) + "</a>", k + 1


def try_inline(s, i):
    b = s[i]
    if b == "`":
        return code_span(s, i)
    if b == "[":
        return link(s, i)
    if b == "*":
        if i + 1 < len(s) and s[i + 1] == "*":
            return bold(s, i)
        return em(s, i)
    return None


def inline(s):
    n = len(s)
    out = []
    run = 0
    i = 0
    while i < n:
        m = SPECIAL.search(s, i)
        if m is None:
            break
        i = m.start()
        r = try_inline(s, i)
        if r is not None:
            html, stop = r
            out.append(esc(s[run:i]))
            out.append(html)
            i = stop
            run = stop
        elif s[i] == "*" and i + 1 < n and s[i + 1] == "*":
            i += 2   # an unclosed "**" is literal as a pair
        else:
            i += 1
    out.append(esc(s[run:n]))
    return "".join(out)


# ---- blocks ----

def heading_level(line):
    k = 0
    while k < len(line) and line[k] == "#":
        k += 1
    return k if 1 <= k <= 6 and (k == len(line) or line[k] == " ") else 0


# (kind, marker length); kind 0 = not an item, 1 = bullet, 2 = ordered
def item_marker(line):
    if line.startswith("- ") or line.startswith("* "):
        return 1, 2
    k = 0
    while k < len(line) and "0" <= line[k] <= "9":
        k += 1
    if k >= 1 and k + 1 < len(line) and line[k] == "." and line[k + 1] == " ":
        return 2, k + 2
    return 0, 0


def is_fence(line):
    return line.startswith("```") and "`" not in line[3:]


def starts_block(line):
    return is_fence(line) or heading_level(line) > 0 or line == "---" or line.startswith(">") or item_marker(line)[0] > 0


def render(lines):
    n = len(lines)
    out = []
    i = 0
    while i < n:
        line = lines[i].strip(WS)
        if not line:
            i += 1
        elif is_fence(line):
            lang = line[3:].strip(WS).split(" ")[0]
            body = []
            i += 1
            while i < n and lines[i].strip(WS) != "```":
                body.append(esc(lines[i]) + "\n")
                i += 1
            if i < n:
                i += 1
            attr = ' class="language-' + esc(lang) + '"' if lang else ""
            out.append("<pre><code" + attr + ">" + "".join(body) + "</code></pre>\n")
        elif heading_level(line) > 0:
            lvl = heading_level(line)
            out.append("<h%d>%s</h%d>\n" % (lvl, inline(line[lvl:].strip(WS)), lvl))
            i += 1
        elif line == "---":
            out.append("<hr>\n")
            i += 1
        elif line.startswith(">"):
            inner = []
            while i < n and lines[i].strip(WS).startswith(">"):
                rest = lines[i].strip(WS)[1:]
                inner.append(rest[1:] if rest.startswith(" ") else rest)
                i += 1
            out.append("<blockquote>\n" + render(inner) + "</blockquote>\n")
        elif item_marker(line)[0] > 0:
            kind = item_marker(line)[0]
            items = []
            while i < n:
                t = lines[i].strip(WS)
                k, m = item_marker(t)
                if k != kind:
                    break
                items.append("<li>" + inline(t[m:].strip(WS)) + "</li>\n")
                i += 1
            tag = "ul" if kind == 1 else "ol"
            out.append("<%s>\n%s</%s>\n" % (tag, "".join(items), tag))
        else:
            parts = [line]
            i += 1
            while i < n:
                t = lines[i].strip(WS)
                if not t or starts_block(t):
                    break
                parts.append(t)
                i += 1
            out.append("<p>" + inline("\n".join(parts)) + "</p>\n")
    return "".join(out)


def main():
    text = sys.stdin.buffer.read().decode("utf-8")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    lines = [l[:-1] if l.endswith("\r") else l for l in lines]
    sys.stdout.buffer.write(render(lines).encode("utf-8"))


if __name__ == "__main__":
    sys.setrecursionlimit(100000)
    threading.stack_size(256 * 1024 * 1024)
    t = threading.Thread(target=main)
    t.start()
    t.join()
