#!/usr/bin/env python3
"""Generative differential testing of `tenon` ($TENON, default target/tenon,
the compiler in use): random well-typed Tenon programs are run by its
reference interpreter (`tenon run`) and its C backend (`tenon build -O0`),
and by the seed's interpreter ($SEED run) as a third opinion;
both checkers must give the same verdict. Any difference in stdout, stderr or
exit code is a bug in one of them (or in the checker, if a program is
rejected). Usage: tools/fuzz.py [COUNT] [SEED]. Failing programs are kept in
.evidence/fuzz-failures/. Adds to .evidence/fuzz.json."""
import json, os, random, subprocess, sys, tempfile, concurrent.futures as cf
import corpus

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = corpus.SEED
TENON = corpus.TENON
os.environ.setdefault("TENON_ROOT", ROOT)

PRELUDE = """
struct Pt { a: Int, b: Str, xs: List[Int] }
enum En { A(Int), B(Str), C, D(En, Int) }
"""

TYPES = ["Int", "Bool", "Str", "List[Int]", "Map[Str, Int]", "Option[Int]", "Pt", "En", "(Int, Str)", "List[Str]"]


class Gen:
    def __init__(self, seed):
        self.r = random.Random(seed)
        self.n = 0
        self.funcs = []  # (name, [param types], ret type)

    def fresh(self, p="v"):
        self.n += 1
        return f"{p}{self.n}"

    def pick(self, xs):
        return self.r.choice(xs)

    # ---- expressions of a given type ----
    def expr(self, t, env, d=0):
        r = self.r
        vars_ = [n for n, (vt, _) in env.items() if vt == t]
        if vars_ and r.random() < 0.45:
            return self.pick(vars_)
        if d > 3:
            return self.leaf(t, env)
        if t == "Int":
            c = r.randrange(12)
            if c == 0: return f"({self.expr('Int', env, d+1)} + {self.expr('Int', env, d+1)})"
            if c == 1: return f"({self.expr('Int', env, d+1)} - {self.expr('Int', env, d+1)})"
            if c == 2: return f"({self.expr('Int', env, d+1)} * {r.randrange(-3, 4)})"
            if c == 3: return f"({self.expr('Int', env, d+1)} % {self.pick([2, 3, 7, -5])})"
            if c == 4: return f"({self.expr('Int', env, d+1)} / {self.pick([1, 2, -3, 10])})"
            if c == 5: return f"{self.expr('Str', env, d+1)}.len()"
            if c == 6: return f"{self.expr('List[Int]', env, d+1)}.len()"
            if c == 7: return f"{self.expr('List[Int]', env, d+1)}.get({self.expr('Int', env, d+1)}).unwrap_or({r.randrange(9)})"
            if c == 8: return f"{self.expr('Map[Str, Int]', env, d+1)}.get_or({self.expr('Str', env, d+1)}, 0)"
            if c == 9: return f"{self.expr('Pt', env, d+1)}.a"
            if c == 10: return f"{self.expr('Option[Int]', env, d+1)}.unwrap_or(-1)"
            if self.funcs and r.random() < 0.7:
                return self.call("Int", env, d)
            return f"{self.expr('(Int, Str)', env, d+1)}.0"
        if t == "Bool":
            c = r.randrange(7)
            if c == 0: return f"({self.expr('Int', env, d+1)} < {self.expr('Int', env, d+1)})"
            if c == 1: return f"({self.expr('Str', env, d+1)} == {self.expr('Str', env, d+1)})"
            if c == 2: return f"({self.expr('Bool', env, d+1)} and {self.expr('Bool', env, d+1)})"
            if c == 3: return f"(not {self.expr('Bool', env, d+1)})"
            if c == 4: return f"{self.expr('List[Int]', env, d+1)}.contains({self.expr('Int', env, d+1)})"
            if c == 5: return f"({self.expr('En', env, d+1)} == {self.expr('En', env, d+1)})"
            return f"({self.expr('Pt', env, d+1)} < {self.expr('Pt', env, d+1)})"
        if t == "Str":
            c = r.randrange(9)
            if c == 0: return f"({self.expr('Str', env, d+1)} + {self.expr('Str', env, d+1)})"
            if c == 1: return f'"<{{{self.expr(self.pick(TYPES), env, d+1)}}}>"'
            if c == 2: return f"{self.expr('Str', env, d+1)}.upper()"
            if c == 3: return f"{self.expr('List[Str]', env, d+1)}.join(\"{self.pick([',', '', ' - '])}\")"
            if c == 4: return f"{self.expr('Pt', env, d+1)}.b"
            if c == 5: return f"{self.expr('Int', env, d+1)}.to_str()"
            if c == 6: return f"{self.expr('Str', env, d+1)}.trim()"
            if c == 7: return f"{self.expr('(Int, Str)', env, d+1)}.1"
            return f"{self.expr('Str', env, d+1)}.replace(\"a\", \"xy\")"
        if t == "List[Int]":
            c = r.randrange(7)
            if c == 0: return "[" + ", ".join(self.expr("Int", env, d+1) for _ in range(r.randrange(4))) + "]"
            if c == 1: return f"{self.expr('List[Int]', env, d+1)}.sorted()"
            if c == 2: return f"({self.expr('List[Int]', env, d+1)} + {self.expr('List[Int]', env, d+1)})"
            if c == 3: return f"{self.expr('List[Int]', env, d+1)}.map(fn({(x:=self.fresh("x"))}) => {x} * 2 + {self.expr('Int', env, d+1)})"
            if c == 4: return f"{self.expr('List[Int]', env, d+1)}.filter(fn({(y:=self.fresh("y"))}) => {y} % 2 == 0)"
            if c == 5: return f"{self.expr('Map[Str, Int]', env, d+1)}.values()"
            return f"{self.expr('Pt', env, d+1)}.xs"
        if t == "List[Str]":
            c = r.randrange(4)
            if c == 0: return "[" + ", ".join(self.expr("Str", env, d+1) for _ in range(r.randrange(3))) + "]"
            if c == 1: return f"{self.expr('Str', env, d+1)}.split(\"{self.pick(['a', ' ', ','])}\")"
            if c == 2: return f"{self.expr('Map[Str, Int]', env, d+1)}.keys()"
            return f"{self.expr('List[Int]', env, d+1)}.map(fn({(z:=self.fresh("z"))}) => \"n{{{z}}}\")"
        if t == "Map[Str, Int]":
            if r.random() < 0.6:
                return "[" + ", ".join(f"{self.expr('Str', env, d+1)}: {self.expr('Int', env, d+1)}" for _ in range(1 + r.randrange(3))) + "]"
            return "[:]" if r.random() < 0.5 else self.leaf(t, env)
        if t == "Option[Int]":
            c = r.randrange(4)
            if c == 0: return f"Some({self.expr('Int', env, d+1)})"
            if c == 1: return f"{self.expr('List[Int]', env, d+1)}.first()"
            if c == 2: return f"{self.expr('Str', env, d+1)}.to_int()"
            return f"{self.expr('Map[Str, Int]', env, d+1)}.get({self.expr('Str', env, d+1)})"
        if t == "Pt":
            if r.random() < 0.2 and vars_:
                return f"Pt {{ a: {self.expr('Int', env, d+1)}, ..{self.pick(vars_)} }}"
            return f"Pt {{ a: {self.expr('Int', env, d+1)}, b: {self.expr('Str', env, d+1)}, xs: {self.expr('List[Int]', env, d+1)} }}"
        if t == "En":
            c = r.randrange(4)
            if c == 0: return f"A({self.expr('Int', env, d+1)})"
            if c == 1: return f"B({self.expr('Str', env, d+1)})"
            if c == 2: return "C"
            return f"D({self.expr('En', env, d+1)}, {self.expr('Int', env, d+1)})"
        if t == "(Int, Str)":
            return f"({self.expr('Int', env, d+1)}, {self.expr('Str', env, d+1)})"
        raise ValueError(t)

    def leaf(self, t, env):
        r = self.r
        return {
            "Int": str(r.randrange(-20, 100)),
            "Bool": self.pick(["true", "false"]),
            "Str": self.pick(['"a"', '""', '"hello world"', '"b,a,c"', '"  x "', '"ä"', '"42"', '"Q\\"q"']),
            "List[Int]": self.pick(["[]", "[1, 2, 3]", "[5, -1]"]),
            "List[Str]": self.pick(["[]", '["x", "y"]']),
            "Map[Str, Int]": self.pick(["[:]", '["k": 1]']),
            "Option[Int]": self.pick(["None", "Some(0)"]),
            "Pt": 'Pt { a: 1, b: "p", xs: [] }',
            "En": self.pick(["C", "A(7)", 'B("e")']),
            "(Int, Str)": '(0, "t")',
        }[t]

    def call(self, t, env, d):
        cands = [f for f in self.funcs if f[2] == t]
        if not cands:
            return self.leaf(t, env)
        name, ps, _ = self.pick(cands)
        return f"{name}(" + ", ".join(self.expr(p, env, d + 1) for p in ps) + ")"

    # ---- statements ----
    def block(self, env, depth, n, loop=False):
        env = dict(env)
        out = []
        for _ in range(n):
            out.extend(self.stmt(env, depth, loop))
        return out

    def stmt(self, env, depth, loop):
        r = self.r
        c = r.randrange(14)
        mutables = [n for n, (t, m) in env.items() if m]
        if c <= 2 or not env:
            t = self.pick(TYPES)
            name = self.fresh()
            mut = r.random() < 0.5
            line = f"{'var' if mut else 'let'} {name}: {t} = {self.expr(t, env)}"
            env[name] = (t, mut)
            return [line]
        if c == 3 and mutables:
            v = self.pick(mutables)
            t = env[v][0]
            if t == "Int" and r.random() < 0.5:
                return [f"{v} {self.pick(['+=', '-=', '*='])} {self.expr('Int', env, 2)}"]
            return [f"{v} = {self.expr(t, env)}"]
        if c == 4:
            lists = [n for n in mutables if env[n][0] == "List[Int]"]
            if lists:
                v = self.pick(lists)
                op = r.randrange(4)
                if op == 0: return [f"{v}.push({self.expr('Int', env)})"]
                if op == 1: return [f"let _ = {v}.pop()"]
                if op == 2: return [f"{v}.sort()"]
                return [f"if {v}.len() > 0 {{ {v}[{v}.len() - 1] = {self.expr('Int', env, 2)} }}"]
            maps = [n for n in mutables if env[n][0] == "Map[Str, Int]"]
            if maps:
                v = self.pick(maps)
                if r.random() < 0.7:
                    return [f"{v}[{self.expr('Str', env, 2)}] = {self.expr('Int', env, 2)}"]
                return [f"let _ = {v}.remove({self.expr('Str', env, 2)})"]
            ps = [n for n in mutables if env[n][0] == "Pt"]
            if ps:
                v = self.pick(ps)
                return [f"{v}.xs.push({self.expr('Int', env, 2)})", f"{v}.a += 1"]
        if c == 5 and r.random() < 0.4:
            t = self.pick([x for x in TYPES])
            v = self.fresh("rt")
            return [f"let {v}: Result[{t}, Str] = decode(encode({self.expr(t, env)}))",
                    f'con.println("rt {{{v}}}")']
        if c in (5, 6, 7):
            return [f"con.println({self.expr(self.pick(TYPES), env)}.to_str())" if r.random() < 0.3
                    else f'con.println("{self.fresh("L")}: {{{self.expr(self.pick(TYPES), env)}}}")']
        if depth > 2:
            return [f'con.println("{{{self.expr("Int", env)}}}")']
        if c == 8:
            body = self.block(env, depth + 1, r.randrange(1, 4), loop)
            els = self.block(env, depth + 1, r.randrange(0, 3), loop)
            return [f"if ({self.expr('Bool', env)}) {{"] + ["    " + l for l in body] + ["} else {"] + ["    " + l for l in els] + ["}"]
        if c == 9:
            i = self.fresh("i")
            env2 = dict(env); env2[i] = ("Int", False)
            body = self.block(env2, depth + 1, r.randrange(1, 4), True)
            return [f"for {i} in 0..{r.randrange(0, 5)} {{"] + ["    " + l for l in body] + ["}"]
        if c == 10:
            x = self.fresh("x")
            env2 = dict(env); env2[x] = ("Int", False)
            body = self.block(env2, depth + 1, r.randrange(1, 3), True)
            return [f"for {x} in ({self.expr('List[Int]', env)}) {{"] + ["    " + l for l in body] + ["}"]
        if c == 11:
            e = self.expr("En", env)
            n, s, k = self.fresh("n"), self.fresh("s"), self.fresh("k")
            arms = [
                f"A({n}) if {n} > 3 => con.println(\"big {{{n}}}\"),",
                f"A({n}) => con.println(\"a {{{n}}}\"),",
                f"B({s}) => con.println(\"b {{{s}.len()}}\"),",
                f"D(C, {k}) => con.println(\"dc {{{k}}}\"),",
                f"D(_, {k}) => con.println(\"d {{{k}}}\"),",
                "C => con.println(\"c\"),",
            ]
            return [f"match ({e}) {{"] + ["    " + a for a in arms] + ["}"]
        if c == 12 and loop:
            return [self.pick(["break", "continue"]) if r.random() < 0.3 else f'con.println("{{{self.expr("Bool", env)}}}")']
        if c == 13:
            o = self.expr("Option[Int]", env)
            v = self.fresh("o")
            return [f"match ({o}) {{", f"    Some({v}) => con.println(\"some {{{v}}}\"),", "    None => con.println(\"none\"),", "}"]
        return [f'con.println("{{{self.expr("Str", env)}}}")']

    def function(self):
        name = self.fresh("f")
        ps = [self.pick(TYPES) for _ in range(self.r.randrange(0, 3))]
        ret = self.pick(["Int", "Str", "List[Int]", "Bool"])
        env = {f"p{i}": (t, False) for i, t in enumerate(ps)}
        body = []
        # no `con` here: helpers are pure
        for _ in range(self.r.randrange(0, 3)):
            t = self.pick(TYPES)
            v = self.fresh()
            body.append(f"let {v}: {t} = {self.expr(t, env)}")
            env[v] = (t, False)
        body.append(self.expr(ret, env))
        src = f"fn {name}(" + ", ".join(f"p{i}: {t}" for i, t in enumerate(ps)) + f") -> {ret} {{\n" + \
              "\n".join("    " + l for l in body) + "\n}\n"
        self.funcs.append((name, ps, ret))
        return src

    def program(self):
        fns = [self.function() for _ in range(self.r.randrange(0, 4))]
        body = self.block({}, 0, self.r.randrange(5, 25))
        return PRELUDE + "\n".join(fns) + "\nfn main(sys: Sys) {\n    let con = sys.console\n" + \
            "\n".join("    " + l for l in body) + "\n}\n"


def show(name, r):
    return f"--- {name} ({r.returncode})\n{r.stdout.decode()[-800:]}{r.stderr.decode()}\n"


def run_one(seed, tmp):
    src = Gen(seed).program()
    path = os.path.join(tmp, f"p{seed}.tn")
    open(path, "w").write(src)
    chk = subprocess.run([TENON, "check", path], capture_output=True, text=True)
    seed_chk = subprocess.run([SEED, "check", path], capture_output=True, text=True)
    if (chk.returncode, chk.stderr.split("\n")[0]) != (seed_chk.returncode, seed_chk.stderr.split("\n")[0]):
        return seed, "disagree", src, f"check: tenon {chk.returncode} {chk.stderr.strip()[:300]}\n  seed {seed_chk.returncode} {seed_chk.stderr.strip()[:300]}"
    if chk.returncode != 0:
        return seed, "rejected", src, chk.stderr
    a = subprocess.run([TENON, "run", path], capture_output=True, timeout=30)
    exe = os.path.join(tmp, f"p{seed}")
    b = subprocess.run([TENON, "build", path, "-o", exe, "-O0"], capture_output=True, text=True)
    if b.returncode != 0:
        return seed, "build", src, b.stderr
    c = subprocess.run([exe], capture_output=True, timeout=30)
    os.remove(exe)
    d = subprocess.run([SEED, "run", path], capture_output=True, timeout=30)
    out = lambda r: (r.stdout, r.stderr, r.returncode)
    if not out(a) == out(c) == out(d):
        return seed, "disagree", src, show("tenon run", a) + show("tenon build", c) + show("seed run", d)
    return seed, "ok", None, None


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    base = int(sys.argv[2]) if len(sys.argv) > 2 else random.randrange(1 << 30)
    fails = os.path.join(ROOT, ".evidence", "fuzz-failures")
    os.makedirs(fails, exist_ok=True)
    stats = {}
    with tempfile.TemporaryDirectory() as tmp, cf.ThreadPoolExecutor(max_workers=corpus.JOBS) as ex:
        for seed, kind, src, msg in ex.map(lambda s: run_one(s, tmp), range(base, base + count)):
            stats[kind] = stats.get(kind, 0) + 1
            if kind != "ok":
                open(os.path.join(fails, f"{kind}-{seed}.tn"), "w").write(src + "\n/*\n" + msg + "\n*/\n")
                print(f"{kind}: seed {seed}: {msg.strip().splitlines()[0] if msg.strip() else ''}")
    print(f"fuzz: {count} programs from seed {base}: {stats}")
    path = os.path.join(ROOT, ".evidence", "fuzz.json")
    old = json.load(open(path)) if os.path.exists(path) else {}
    if old.get("compiler") != "tenonc":  # the self-hosted compiler's tag (it was called tenonc); totals from when the seed was fuzzed are not carried over
        old = {"compiler": "tenonc"}
    old["programs"] = old.get("programs", 0) + count
    old["disagreements"] = old.get("disagreements", 0) + stats.get("disagree", 0) + stats.get("build", 0)
    old["rejected"] = old.get("rejected", 0) + stats.get("rejected", 0)
    bad = stats.get("disagree", 0) + stats.get("build", 0)
    old["last"] = {"programs": count, "seed": base, "disagreements": bad, "rejected": stats.get("rejected", 0)}
    corpus.record("fuzz", old)
    return 0 if not (stats.get("disagree") or stats.get("build")) else 1


if __name__ == "__main__":
    sys.exit(main())
