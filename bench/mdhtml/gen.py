# Deterministic input: a ~12 MB Markdown document using every supported construct.
import random
r = random.Random(11)
words = ("alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma "
         "tau upsilon phi chi psi omega parser tokens stream buffer cache index vector matrix kernel "
         "socket thread signal memory region lifetime borrow module crate package linker loader").split()
specials = ["a & b", "x < y", "p > q", 'say "hi"', "café", "naïve", "日本語", "snow☃"]


def w():
    return r.choice(specials) if r.random() < 0.05 else r.choice(words)


def text(n):
    return " ".join(w() for _ in range(n))


def inline(depth=0):
    k = r.randrange(14)
    if k == 0:
        return "`%s`" % text(r.randint(1, 3))
    if k == 1:
        return "**%s**" % text(r.randint(1, 3))
    if k == 2:
        return "*%s*" % text(r.randint(1, 3))
    if k == 3:
        return "[%s](http://example.com/%s?q=%d&r=%d)" % (text(r.randint(1, 3)), w().replace(" ", "_"), r.randint(1, 99), r.randint(1, 99))
    if k == 4 and depth < 2:
        return "**%s *%s* %s**" % (text(1), text(2), text(1))
    if k == 5 and depth < 2:
        return "*%s **%s** %s*" % (text(1), text(2), text(1))
    if k == 6:
        return "[**%s**](%s)" % (text(1), "u%d" % r.randint(1, 999))
    if k == 7:
        return r.choice(["2 * 3 * 4", "** a **", "**open", "*open", "`open", "[open](", "[a](b c)", "***both***", "`` ****"])
    return w()


def line(n):
    parts = []
    for _ in range(n):
        parts.append(inline() if r.random() < 0.4 else text(r.randint(1, 4)))
    return " ".join(parts)


def block(depth=0):
    k = r.randrange(100)
    if k < 10:
        return "#" * r.randint(1, 6) + " " + line(r.randint(1, 3)) + "\n"
    if k < 45:
        return "\n".join(line(r.randint(2, 6)) for _ in range(r.randint(1, 4))) + "\n"
    if k < 57:
        mark = r.choice(["-", "*"]) if r.random() < 0.7 else None
        n = r.randint(2, 7)
        if mark:
            return "\n".join("%s %s" % (mark, line(r.randint(1, 3))) for _ in range(n)) + "\n"
        return "\n".join("%d. %s" % (i + 1, line(r.randint(1, 3))) for i in range(n)) + "\n"
    if k < 67:
        lang = r.choice(["", "rust", "python", "c", "sh extra words", 'a"b'])
        body = "\n".join(r.choice(["fn main() { println!(\"%s\"); }" % w(), "  indented <b>&amp;</b> " + w(),
                                   "# not a heading", "- not a list", "**not bold** `x` [a](b)", "", "if a < b && c > d {"])
                         for _ in range(r.randint(1, 8)))
        return "```%s\n%s\n```\n" % (lang, body)
    if k < 77 and depth < 2:
        inner = "\n".join(block(depth + 1) for _ in range(r.randint(1, 3)))
        return "\n".join(("> " + l) if l else ">" for l in inner.rstrip("\n").split("\n")) + "\n"
    if k < 82:
        return "---\n"
    return line(r.randint(3, 8)) + "\n"


out = []
size = 0
while size < 12_000_000:
    b = block()
    out.append(b)
    size += len(b) + 1
open("input.txt", "w").write("\n".join(out))
