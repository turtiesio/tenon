#!/usr/bin/env python3
"""Differential mutation testing of the self-hosted checker: corpus programs
are mutated at the token level (deleted/duplicated/swapped tokens, renamed
identifiers and types, flipped let/var, mut/ref, literals ...) and both
`tenon-seed check` and `tenon check` (compiler/tenon.tn) must report the same
first line; when both accept a mutant, `tenon-seed emit` and `tenon emit` must
print the same C (and exit with the same status).

Three kinds of difference are by design and reported separately, not as
disagreements: tenon rejects with a rule added after the seed froze while the
seed accepts (STRICTER), the seed stops at syntax that only tenon reads
(V2_SYNTAX), and tenon's diagnostic is the seed's with a reason appended
(REASONS). Every other difference is a disagreement: tenon accepts what the
seed rejects, other diagnostics, a crash or timeout, different C.

Usage: ops/evidence/checkfuzz.py [COUNT] [SEED] [-v]   (-v: histogram of outcomes)
The binaries are $SEED and $TENON (ops/corpus.py; ./check and ops/evidence/evidence.sh build them).
Disagreements are kept in .evidence/checkfuzz/ (mutant + both outputs), the
differences by design as by-design-*; the totals go to .evidence/checkfuzz.json."""
import os, random, re, shutil, subprocess, sys, tempfile, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ops/: corpus.py
import corpus as corpus_

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEED = corpus_.SEED
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|->|=>|==|!=|<=|>=|\+=|-=|\.\.|\S')
TYPES = ["Int", "Str", "Bool", "Float", "Unit", "List[Int]", "Map[Str, Int]", "Option[Int]", "Result[Int, Str]",
         "(Int, Str)", "fn(Int) -> Int", "Fs", "Console", "List[T]", "T", "Option[T]", "Sys", "Conn"]
SNIPPETS = ["mut ", "ref ", "?", ".0", ".len()", ".unwrap()", "not ", "-", "_", "None", "Some(1)", "Ok(())", "Err(\"e\")",
            "[]", "[:]", "()", "1.5", "\"s\"", "true", "return", "break", "self", "panic(\"x\")", "x", "encode(", "decode(",
            ".to_str()", "+ 1", "== 1", "{ }", "let _ = ", "var ", "let ", "const ", "pub ", "linear ", "unique "]
# Rules tenon's checker has and the frozen seed's lacks: the start of tenon's diagnostic (the text
# after "error: ") when the seed accepts. Each with the change that added it and where
# docs/reference.md states it; add one only together with its rule.
STRICTER = [
    (r"this linear value would be lost if another part of the expression leaves early",
     "linear value in flight next to an early exit: 06027af, reference §12"),
    (r"'[^']+' has 'ref' parameters, so it can only be called, not used as a value",
     "function with ref parameters used as a value: ed34e7d, reference §12"),
    (r"constant '[^']+' has the (linear|unique) type .*: every use would copy it",
     "linear or unique constant: d2de63f, reference §12"),
    (r"cannot (encode|decode) \S+: \S+ is private to its module", "private type encoded or decoded: a35a3f5, reference §13, §14"),
    (r"variant '[^']+' of \S+ is private to its module", "pattern naming a private enum's variant: a35a3f5, reference §13"),
    (r"'[^']+' was already used: a (linear|unique) value cannot be used after it is moved",
     "use after move: bdbca07, reference §12"),
    (r"'self' was already used: a (linear|unique) value cannot be copied", "copy of a unique or linear self: c33c7cf, reference §12"),
    (r"'self' is a 'ref' parameter: it can be inspected but not consumed", "move of a 'mut self': c33c7cf, reference §12"),
]
# Syntax only tenon reads: the seed's diagnostic, and the mutant's text before the
# position it names (a regex on that line up to the column, then the rest of the line).
V2_SYNTAX = [
    (r"expected ',', found ':'", r"\[\s*[A-Za-z_]\w*\s*$", r":",
     "a bound in a type-parameter list, [T: Show]: reference §17 (Bounds)"),
]

# Reasons tenon appends to a diagnostic the seed gives (the same location and
# text, then ": REASON"); each with the change that added it.
REASONS = [
    (r": '[^']+' is a builtin type and cannot be hidden \(rename yours\)$",
     "why a builtin type cannot be hidden: issue #20, reference §13"),
]


def by_design(mut, want, got):
    """The STRICTER, V2_SYNTAX or REASONS entry that explains this difference, or None."""
    msg = lambda line: line.split(": error: ", 1)[1] if ": error: " in line else None
    if want != "ok" and got.startswith(want):
        for pat, why in REASONS:
            if re.match(pat, got[len(want):]):
                return "a reason added to the seed's diagnostic (" + why + ")"
    if want == "ok" and msg(got):
        for pat, why in STRICTER:
            if re.match(pat, msg(got)):
                return "stricter by design (" + why + ")"
    m = re.match(r".*?:(\d+):(\d+): error: (.*)$", want)
    if m and got != "ok" and msg(got) is not None:
        lines = mut.split("\n")
        ln, col = int(m.group(1)) - 1, int(m.group(2)) - 1
        if ln < len(lines):
            for diag, before, at, why in V2_SYNTAX:
                if re.match(diag, m.group(3)) and re.search(before, lines[ln][:col]) and re.match(at, lines[ln][col:]):
                    return "v2 syntax the seed cannot read (" + why + ")"
    return None


def mutate(src, r):
    toks = [(m.start(), m.end(), m.group()) for m in TOKEN.finditer(src)]
    if not toks:
        return src
    idents = sorted({t for _, _, t in toks if re.match(r"[a-z_][A-Za-z0-9_]*$", t)})
    upper = sorted({t for _, _, t in toks if re.match(r"[A-Z][A-Za-z0-9_]*$", t)})
    i = r.randrange(len(toks))
    s, e, t = toks[i]
    kind = r.choice([0, 1, 1, 1, 2, 2, 2, 3, 4, 5, 5, 6, 6, 6, 7, 7, 7, 8, 9, 10, 10, 11, 11])
    if kind == 0:  # delete a token
        return src[:s] + src[e:]
    if kind == 1 and idents:  # rename an identifier occurrence
        return src[:s] + r.choice(idents) + src[e:]
    if kind == 2 and upper:  # rename a capitalized name
        return src[:s] + r.choice(upper) + src[e:]
    if kind == 3:  # duplicate a token
        return src[:e] + " " + t + src[e:]
    if kind == 4:  # swap with the next token
        if i + 1 < len(toks):
            s2, e2, t2 = toks[i + 1]
            return src[:s] + t2 + src[e:s2] + t + src[e2:]
    if kind == 5:  # insert a snippet
        return src[:s] + r.choice(SNIPPETS) + src[s:]
    if kind == 6:  # replace a type-looking token
        if re.match(r"[A-Z]", t):
            return src[:s] + r.choice(TYPES) + src[e:]
    if kind == 7:  # flip common keyword pairs
        flips = {"let": "var", "var": "let", "self": "mut self", "Ok": "Err", "Some": "None", "true": "1",
                 "and": "or", "+": "-", "==": "<", "ref": "mut", "mut": "ref", "pub": "", "linear": "unique",
                 "unique": "linear", "if": "while", "List": "Map", "Int": "Float", "Str": "Int", "return": "break"}
        if t in flips:
            return src[:s] + flips[t] + src[e:]
    if kind == 8:  # delete a line
        lines = src.split("\n")
        k = r.randrange(len(lines))
        return "\n".join(lines[:k] + lines[k + 1:])
    if kind == 9:  # duplicate a line
        lines = src.split("\n")
        k = r.randrange(len(lines))
        return "\n".join(lines[:k + 1] + lines[k:])
    if kind == 10:  # replace a literal
        if re.match(r'\d|"', t):
            return src[:s] + r.choice(["1", "1.0", '"a"', "true", "()", "[1]", "-1", "0"]) + src[e:]
    # replace a token with another token from the file
    return src[:s] + r.choice(toks)[2] + src[e:]


def first_line(p):
    if p.returncode == 0:
        return "ok"
    return (p.stderr.splitlines() or [""])[0]


def run_one(args):
    n, seed, rel, ck = args
    r = random.Random(seed * 1000003 + n)
    src = open(os.path.join(ROOT, rel), encoding="utf-8").read()
    mut = src
    for _ in range(r.choice([1, 1, 1, 2, 3])):
        mut = mutate(mut, r)
    if mut == src:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, os.path.dirname(rel))
        os.makedirs(d, exist_ok=True)
        srcdir = os.path.join(ROOT, os.path.dirname(rel))
        for f in os.listdir(srcdir):  # sibling modules
            if f.endswith(".tn"):
                shutil.copy(os.path.join(srcdir, f), d)
        target = os.path.join(d, os.path.basename(rel))
        open(target, "w", encoding="utf-8").write(mut)
        try:
            a = subprocess.run([SEED, "check", rel], cwd=tmp, capture_output=True, text=True, timeout=20)
            want = first_line(a)
        except subprocess.TimeoutExpired:
            want = "<bootstrap timeout>"
        try:
            b = subprocess.run([ck, "check", rel, "--root", ROOT], cwd=tmp, capture_output=True, text=True, timeout=20)
            got = first_line(b)
        except subprocess.TimeoutExpired:
            got = "<selfhost timeout>"
        if want != got:
            why = by_design(mut, want, got)
            return ("by design", why, rel, mut, want, got) if why else (rel, mut, want, got)
        if want == "ok":
            try:
                a = subprocess.run([SEED, "emit", rel], cwd=tmp, capture_output=True, timeout=20)
                b = subprocess.run([ck, "emit", rel, "--root", ROOT], cwd=tmp, capture_output=True, timeout=20)
                if (a.returncode, a.stdout) != (b.returncode, b.stdout):
                    return (rel, mut, "emit: exit %d, %d bytes of C" % (a.returncode, len(a.stdout)),
                            "emit: exit %d, %d bytes of C (different)" % (b.returncode, len(b.stdout)))
            except subprocess.TimeoutExpired:
                return (rel, mut, "emit", "<emit timeout>")
    return ("agree", want)


def main():
    pos = [a for a in sys.argv[1:] if not a.startswith("-")]
    count = int(pos[0]) if len(pos) > 0 else 500
    seed = int(pos[1]) if len(pos) > 1 else 1
    ck = corpus_.TENON
    if not os.path.exists(ck):
        raise SystemExit(f"checkfuzz: no tenon at {ck} (./check builds it)")
    files = corpus_.files(no_v2=True)  # v2/: syntax the seed cannot read
    # Mostly mutate programs the bootstrap accepts: their mutants reach the checker.
    good = [f for f in files if subprocess.run([SEED, "check", f], cwd=ROOT, capture_output=True).returncode == 0]
    r = random.Random(seed)
    jobs = [(n, seed, r.choice(good if r.random() < 0.85 else files), ck) for n in range(count)]
    out = os.path.join(ROOT, ".evidence", "checkfuzz")
    os.makedirs(out, exist_ok=True)
    bad = designed = 0
    kinds = {}
    with cf.ThreadPoolExecutor(max_workers=corpus_.JOBS) as ex:
        for res in ex.map(run_one, jobs):
            if res is None:
                continue
            if res[0] == "agree":
                k = re.sub(r"'[^']*'|\b[A-Z]\w*(\[.*?\])?|\d+", "_", res[1].split(": error: ")[-1])[:60]
                kinds[k] = kinds.get(k, 0) + 1
                continue
            if res[0] == "by design":
                designed += 1
                why, (rel, mut, want, got) = res[1], res[2:]
                name = os.path.join(out, "by-design-%d-%s" % (designed, os.path.basename(rel)))
                label = "BY DESIGN %s: %s" % (name, why)
            else:
                bad += 1
                rel, mut, want, got = res
                name = os.path.join(out, "%d-%s" % (bad, os.path.basename(rel)))
                label = "DISAGREE %s" % name
            open(name, "w", encoding="utf-8").write(mut)
            open(name + ".diff", "w", encoding="utf-8").write("bootstrap: %s\nselfhost:  %s\n" % (want, got))
            print("%s\n  bootstrap: %s\n  selfhost:  %s" % (label, want, got))
    if "-v" in sys.argv:
        for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]):
            print("%6d  %s" % (v, k))
    print("checkfuzz: %d mutants, %d disagreements, %d by design (STRICTER, V2_SYNTAX, REASONS), %d distinct outcomes" % (count, bad, designed, len(kinds)))
    corpus_.record("checkfuzz", {"mutants": count, "seed": seed, "disagreements": bad, "by_design": designed, "outcomes": len(kinds)})
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
