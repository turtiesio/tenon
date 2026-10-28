#!/usr/bin/env python3
"""Differential mutation testing of the self-hosted checker: corpus programs
are mutated at the token level (deleted/duplicated/swapped tokens, renamed
identifiers and types, flipped let/var, mut/ref, literals ...) and both
`tenon check` and `tenonc check` (selfhost/tenonc.tn) must report the same
first line; when both accept a mutant, `tenon emit` and `tenonc emit` must
print the same C (and exit with the same status).

Usage: selfhost/checkfuzz.py [COUNT] [SEED] [-v]   (-v: histogram of outcomes)
Disagreements are kept in .evidence/checkfuzz/ (mutant + both outputs)."""
import os, random, re, shutil, subprocess, sys, tempfile, concurrent.futures as cf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TENON = os.path.join(ROOT, "target", "release", "tenon")
DIRS = ["bootstrap", "lib", "tests", "programs", "selfhost", "bench", "study"]
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|->|=>|==|!=|<=|>=|\+=|-=|\.\.|\S')
TYPES = ["Int", "Str", "Bool", "Float", "Unit", "List[Int]", "Map[Str, Int]", "Option[Int]", "Result[Int, Str]",
         "(Int, Str)", "fn(Int) -> Int", "Fs", "Console", "List[T]", "T", "Option[T]", "Sys", "Conn"]
SNIPPETS = ["mut ", "ref ", "?", ".0", ".len()", ".unwrap()", "not ", "-", "_", "None", "Some(1)", "Ok(())", "Err(\"e\")",
            "[]", "[:]", "()", "1.5", "\"s\"", "true", "return", "break", "self", "panic(\"x\")", "x", "encode(", "decode(",
            ".to_str()", "+ 1", "== 1", "{ }", "let _ = ", "var ", "let ", "const ", "pub ", "linear ", "unique "]


def corpus():
    files = []
    for d in DIRS:
        for dp, _, fs in os.walk(os.path.join(ROOT, d)):
            for f in fs:
                if f.endswith(".tn"):
                    files.append(os.path.relpath(os.path.join(dp, f), ROOT))
    return sorted(files)


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
            a = subprocess.run([TENON, "check", rel], cwd=tmp, capture_output=True, text=True, timeout=20)
            want = first_line(a)
        except subprocess.TimeoutExpired:
            want = "<bootstrap timeout>"
        try:
            b = subprocess.run([ck, "check", rel, ROOT], cwd=tmp, capture_output=True, text=True, timeout=20)
            got = (b.stdout.splitlines() or [b.stderr.strip() or "<no output, exit %d>" % b.returncode])[0]
        except subprocess.TimeoutExpired:
            got = "<selfhost timeout>"
        if want != got:
            return (rel, mut, want, got)
        if want == "ok":
            try:
                a = subprocess.run([TENON, "emit", rel], cwd=tmp, capture_output=True, timeout=20)
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
    ck = os.path.join(tempfile.mkdtemp(), "tenonc")
    subprocess.run([TENON, "build", os.path.join(ROOT, "selfhost", "tenonc.tn"), "-o", ck], check=True)
    files = corpus()
    # Mostly mutate programs the bootstrap accepts: their mutants reach the checker.
    good = [f for f in files if subprocess.run([TENON, "check", f], cwd=ROOT, capture_output=True).returncode == 0]
    r = random.Random(seed)
    jobs = [(n, seed, r.choice(good if r.random() < 0.85 else files), ck) for n in range(count)]
    out = os.path.join(ROOT, ".evidence", "checkfuzz")
    os.makedirs(out, exist_ok=True)
    bad = 0
    kinds = {}
    with cf.ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as ex:
        for res in ex.map(run_one, jobs):
            if res is None:
                continue
            if res[0] == "agree":
                k = re.sub(r"'[^']*'|\b[A-Z]\w*(\[.*?\])?|\d+", "_", res[1].split(": error: ")[-1])[:60]
                kinds[k] = kinds.get(k, 0) + 1
                continue
            bad += 1
            rel, mut, want, got = res
            name = os.path.join(out, "%d-%s" % (bad, os.path.basename(rel)))
            open(name, "w", encoding="utf-8").write(mut)
            open(name + ".diff", "w", encoding="utf-8").write("bootstrap: %s\nselfhost:  %s\n" % (want, got))
            print("DISAGREE %s\n  bootstrap: %s\n  selfhost:  %s" % (name, want, got))
    if "-v" in sys.argv:
        for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]):
            print("%6d  %s" % (v, k))
    print("checkfuzz: %d mutants, %d disagreements, %d distinct outcomes" % (count, bad, len(kinds)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
