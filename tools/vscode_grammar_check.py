#!/usr/bin/env python3
"""Check the VS Code grammar (editors/vscode) without npm or VS Code.

1. The extension's JSON files parse; package.json points at files that exist.
2. The grammar's keyword rules (repository.keywords, each `\\b(a|b|...)\\b`)
   name exactly the bootstrap lexer's KEYWORDS: none missing, none invented.
3. Every regex compiles with Python's `re`. The grammar is kept to the subset
   that Oniguruma (VS Code) and Python agree on; the few Oniguruma spellings
   that have a Python equivalent are translated first (TRANSLATE), and
   Oniguruma-only constructs with no equivalent are rejected (FORBIDDEN).
4. A small TextMate interpreter (match, begin/end, include, captures; earliest
   match wins, ties go to the end pattern and then to pattern order, as in
   vscode-textmate) tokenizes every .tn file in the repository line by line.
   Tenon strings, raw strings and interpolations cannot span lines, so the
   grammar closes them at the end of a line as a fallback. A scope still open
   at the end of a line is a leak; a scope closed only by that fallback means
   the grammar thinks a string is unterminated, which is a leak too unless the
   real lexer (`target/release/tenon tokens`) rejects the file on that line.
   A few pinned lines (SAMPLES) also check the scopes given to tricky tokens.

Usage: tools/vscode_grammar_check.py [FILE.tn...]   (default: the whole repo)
Exit status 1 on any finding.
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(ROOT, "editors", "vscode")
GRAMMAR = os.path.join(EXT, "syntaxes", "tenon.tmLanguage.json")
TENON = os.environ.get("TENON") or os.path.join(ROOT, "target", "release", "tenon")  # ./check: tenonc
LEXERS = ["bootstrap/src/lexer.rs", "src/lexer.rs"]

# Oniguruma spelling -> Python spelling.
TRANSLATE = [
    (re.compile(r"\(\?<(?![=!])([A-Za-z_]\w*)>"), r"(?P<\1>"),  # named group
    (re.compile(r"(?<!\\)\\h"), "[0-9A-Fa-f]"),                  # hex digit
    (re.compile(r"(?<!\\)\\z"), r"\\Z"),                          # end of string
]
# Oniguruma-only, no Python equivalent: keep them out of the grammar.
FORBIDDEN = [r"\G", r"\K", r"\p{", r"\k<", r"(?~", r"\H"]

# (line, text inside it, scope that text must have, scope it must not have)
SAMPLES = [
    ('fn Int.abs(self) -> Int {', "abs", "entity.name.function.tenon", None),
    ('fn Int.abs(self) -> Int {', "Int", "entity.name.type.tenon", None),
    ('pub fn main(sys: Sys) {', "main", "entity.name.function.tenon", None),
    ('linear struct Tx { id: Int }', "linear", "storage.modifier.tenon", None),
    ('linear struct Tx { id: Int }', "Tx", "entity.name.type.tenon", None),
    ('import journal', "journal", "entity.name.namespace.tenon", None),
    ('let c: Console = sys.console', "Console", "support.type.capability.tenon", None),
    ('let s = "a {x:>8} b"', ">8", "constant.other.format-spec.tenon", None),
    ('let s = "a {x:>8} b"', "x", "meta.embedded.expression.tenon", "constant.other.format-spec.tenon"),
    ('let s = "{(fn(x: Int) => x * 2)(p):4}"', "Int", "support.type.builtin.tenon", "constant.other.format-spec.tenon"),
    ('let s = "{(fn(x: Int) => x * 2)(p):4}"', "4", "constant.other.format-spec.tenon", None),
    ('let s = "{m.get("k").unwrap_or(0)} done"', "done", "string.quoted.double.tenon", "meta.interpolation.tenon"),
    ('let s = "\\{x} {y}"', "\\{", "constant.character.escape.tenon", None),
    ('let s = "\\{x} {y}"', "x", "string.quoted.double.tenon", "meta.interpolation.tenon"),
    ('let s = "\\{x} {y}"', "y", "meta.interpolation.tenon", None),
    ('let p = r"(\\d{4})" + x', "{4}", "string.quoted.double.raw.tenon", "meta.interpolation.tenon"),
    ('let p = r"(\\d{4})" + x', "x", "source.tenon", "string.quoted.double.raw.tenon"),
    ("let q = '\\'' + 'a'", "\\'", "constant.character.escape.tenon", None),
    ("let q = '\\'' + 'a'", "+", "keyword.operator.arithmetic.tenon", "string.quoted.single.char.tenon"),
    ('let n = 0xFF_FF + 1_000 + 1e-9 + 3.14', "0xFF_FF", "constant.numeric.hex.tenon", None),
    ('let n = 0xFF_FF + 1_000 + 1e-9 + 3.14', "1e-9", "constant.numeric.float.tenon", None),
    ('let n = 0xFF_FF + 1_000 + 1e-9 + 3.14', "1_000", "constant.numeric.integer.tenon", None),
    ('for i in 0..10 { t.0 }', "10", "constant.numeric.integer.tenon", None),
    ('for i in 0..10 { t.0 }', "..", "keyword.operator.range.tenon", None),
    ('let v = f(x)?', "?", "keyword.operator.question.tenon", None),
    ('Some(x) => x, None => 0', "None", "variable.other.enummember.tenon", None),
    ('Shape.Circle(r) => r', "Circle", "variable.other.enummember.tenon", None),
    ('// "not a string', '"', "comment.line.double-slash.tenon", "string.quoted.double.tenon"),
    ('let u = "url // not a comment"', "not", "string.quoted.double.tenon", "comment.line.double-slash.tenon"),
]


class Grammar:
    def __init__(self, g):
        self.g = g
        self.repo = g.get("repository", {})
        self.compiled = {}  # id(rule) -> compiled pattern for its match/begin
        self.contexts = {}  # id(rule or None) -> (combined regex, [leaf rules])
        self.errors = []

    def rx(self, src, where):
        for bad in FORBIDDEN:
            if bad in src:
                self.errors.append(f"{where}: Oniguruma-only construct {bad!r} in {src!r}")
        for pat, rep in TRANSLATE:
            src = pat.sub(rep, src)
        try:
            return re.compile(src), src
        except re.error as e:
            self.errors.append(f"{where}: regex does not compile ({e}): {src!r}")
            return None, src

    def leaves(self, patterns, seen=()):
        out = []
        for p in patterns:
            if "include" in p:
                inc = p["include"]
                if inc == "$self" or inc == "$base":
                    out += self.leaves(self.g["patterns"], seen)
                elif inc.startswith("#"):
                    key = inc[1:]
                    if key not in self.repo:
                        self.errors.append(f"include {inc} names no repository entry")
                    elif key not in seen:
                        out += self.leaves([self.repo[key]], seen + (key,))
                else:
                    self.errors.append(f"include {inc}: external grammars are not supported")
            elif "match" in p or "begin" in p:
                out.append(p)
            elif "patterns" in p:
                out += self.leaves(p["patterns"], seen)
        return out

    def context(self, rule):
        key = id(rule) if rule is not None else None
        if key in self.contexts:
            return self.contexts[key]
        pats = self.g["patterns"] if rule is None else rule.get("patterns", [])
        leaves = self.leaves(pats)
        parts = []
        if rule is not None:
            _, src = self.rx(rule["end"], f"end of {rule.get('name', rule['begin'])}")
            parts.append(f"(?P<e>{src})")
        for i, leaf in enumerate(leaves):
            if id(leaf) not in self.compiled:
                c, src = self.rx(leaf.get("match", leaf.get("begin")), leaf.get("name", "rule"))
                self.compiled[id(leaf)] = (c, src)
            src = self.compiled[id(leaf)][1]
            parts.append(f"(?P<p{i}>{src})")
        try:
            combined = re.compile("|".join(parts))
        except re.error as e:
            self.errors.append(f"combined context regex does not compile ({e})")
            combined = re.compile(r"(?!)")
        self.contexts[key] = (combined, leaves)
        return self.contexts[key]

    def compile_all(self):
        """Compile every regex in the grammar, reachable or not."""
        def walk(node, where):
            if isinstance(node, dict):
                for k in ("match", "begin", "end"):
                    if k in node:
                        self.rx(node[k], f"{where}.{k}")
                for k, v in node.items():
                    walk(v, f"{where}.{k}")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{where}[{i}]")
        walk(self.g, "grammar")

    def tokenize_line(self, line, stack, spans=None):
        """Advance `stack` (list of (rule, start, content start)) over one line. Returns
        (fallbacks, leaked): scopes closed only by the end of the line, and
        whether a scope is still open after it."""
        s = line + "\n"
        n = len(line)
        pos = 0
        fallbacks = []
        while pos <= n:
            rule = stack[-1][0] if stack else None
            combined, leaves = self.context(rule)
            m = combined.search(s, pos)
            if not m or m.start() > n:
                break
            which = m.lastgroup
            if which == "e":
                if m.start() == m.end() == n:
                    fallbacks.append((rule.get("name") or rule["begin"], stack[-1][1]))
                if spans is not None:
                    self.span_region(spans, stack[-1], m)
                stack.pop()
                pos = m.end()
                continue
            leaf = leaves[int(which[1:])]
            sub = self.compiled[id(leaf)][0].match(s, m.start())
            if "begin" in leaf:
                stack.append((leaf, m.start(), sub.end()))
                if spans is not None:
                    self.span_caps(spans, leaf.get("beginCaptures", leaf.get("captures", {})), sub)
            else:
                if spans is not None:
                    if leaf.get("name"):
                        spans.append((sub.start(), sub.end(), leaf["name"]))
                    self.span_caps(spans, leaf.get("captures", {}), sub)
            pos = sub.end() if sub.end() > pos else pos + 1
        if spans is not None:
            for entry in stack:
                self.span_region(spans, entry, None, n)
        return fallbacks, bool(stack)

    def span_caps(self, spans, caps, m):
        for k, v in caps.items():
            i = int(k)
            if i <= (m.re.groups) and m.start(i) >= 0 and "name" in v:
                spans.append((m.start(i), m.end(i), v["name"]))

    def span_region(self, spans, entry, m, n=None):
        rule, start, content_start = entry
        end = m.end() if m else n
        if rule.get("name"):
            spans.append((start, end, rule["name"]))
        if rule.get("contentName"):
            spans.append((content_start, m.start() if m else n, rule["contentName"]))
        if m is not None:
            sub = re.compile(self.rx(rule["end"], "end")[1]).match(m.string, m.start())
            self.span_caps(spans, rule.get("endCaptures", rule.get("captures", {})), sub)


def lexer_keywords():
    for rel in LEXERS:
        path = os.path.join(ROOT, rel)
        if os.path.exists(path):
            src = open(path, encoding="utf-8").read()
            m = re.search(r"const KEYWORDS: &\[&str\] = &\[(.*?)\];", src, re.S)
            if m:
                return rel, set(re.findall(r'"(\w+)"', m.group(1)))
    return None, None


def corpus():
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.tn"],
            cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        return sorted(set(os.path.join(ROOT, p) for p in out if os.path.exists(os.path.join(ROOT, p))))
    except (OSError, subprocess.CalledProcessError):
        found = []
        for d, dirs, files in os.walk(ROOT):
            dirs[:] = [x for x in dirs if x not in (".git", "target", ".claude")]
            found += [os.path.join(d, f) for f in files if f.endswith(".tn")]
        return sorted(found)


def lexer_error_line(path):
    """The line of the real lexer's error for this file, or None if it lexes."""
    if not os.path.exists(TENON):
        return None
    r = subprocess.run([TENON, "tokens", path], capture_output=True, text=True)
    m = re.match(r"error (\d+):\d+ ", r.stdout)
    return int(m.group(1)) if m else None


def main():
    problems = []
    loaded = {}
    for rel in ["package.json", "language-configuration.json", "syntaxes/tenon.tmLanguage.json"]:
        try:
            loaded[rel] = json.load(open(os.path.join(EXT, rel), encoding="utf-8"))
        except (OSError, ValueError) as e:
            problems.append(f"editors/vscode/{rel}: {e}")
    if problems:
        print("\n".join(problems))
        return 1
    pkg = loaded["package.json"]["contributes"]
    for entry in pkg["languages"] + pkg["grammars"]:
        for k in ("configuration", "path"):
            if k in entry and not os.path.exists(os.path.join(EXT, entry[k])):
                problems.append(f"package.json: {entry[k]} does not exist")
    lc = loaded["language-configuration.json"]
    for k in ("wordPattern",):
        try:
            re.compile(lc[k])
        except re.error as e:
            problems.append(f"language-configuration.json {k}: {e}")
    for k, v in lc.get("indentationRules", {}).items():
        try:
            re.compile(v)
        except re.error as e:
            problems.append(f"language-configuration.json indentationRules.{k}: {e}")

    g = Grammar(loaded["syntaxes/tenon.tmLanguage.json"])
    g.compile_all()

    rel, kws = lexer_keywords()
    if kws is None:
        problems.append(f"no KEYWORDS list found in {' or '.join(LEXERS)}")
    else:
        gkw = set()
        for p in g.repo["keywords"]["patterns"]:
            m = re.fullmatch(r"\\b\(([\w|]+)\)\\b", p["match"])
            if not m:
                problems.append(f"keyword rule not of the form \\b(a|b)\\b: {p['match']}")
                continue
            gkw |= set(m.group(1).split("|"))
        for k in sorted(kws - gkw):
            problems.append(f"keyword {k!r} ({rel}) is not highlighted by repository.keywords")
        for k in sorted(gkw - kws):
            problems.append(f"repository.keywords highlights {k!r}, which is not a keyword in {rel}")

    for line, text, want, avoid in SAMPLES:
        spans = []
        g.tokenize_line(line, [], spans)
        col = line.index(text)
        have = {"source.tenon"} | {sc for a, b, sc in spans if a <= col < b and a < b}
        if want not in have:
            problems.append(f"sample {line!r}: {text!r} should be {want}, has {sorted(have)}")
        if avoid and avoid in have:
            problems.append(f"sample {line!r}: {text!r} should not be {avoid}")

    files = [os.path.abspath(a) for a in sys.argv[1:]] or corpus()
    # Every line starts at the root (no Tenon literal spans lines). A line in
    # which no root-level begin pattern matches anywhere cannot open a scope,
    # so it cannot leak: skip it (this keeps the check well under a second).
    opener = re.compile("|".join(g.compiled[id(r)][1] for r in g.context(None)[1] if "begin" in r) or r"(?!)")
    leaks = 0
    lines_total = 0
    expected = 0
    for path in files:
        first = None
        with open(path, encoding="utf-8", errors="replace") as f:
            for no, line in enumerate(f.read().split("\n"), 1):
                lines_total += 1
                if not opener.search(line):
                    continue
                stack = []
                fallbacks, leaked = g.tokenize_line(line.rstrip("\r"), stack)
                if leaked:
                    first = (no, f"scope {stack[-1][0].get('name') or stack[-1][0]['begin']!r} runs past the end of the line")
                elif fallbacks:
                    first = (no, f"{fallbacks[0][0]} opened at column {fallbacks[0][1] + 1} is closed only by the end of the line")
                if first:
                    break
        if first is None:
            continue
        rp = os.path.relpath(path, ROOT)
        if lexer_error_line(path) == first[0]:
            expected += 1  # the lexer rejects the same line: an unterminated literal on purpose
            continue
        leaks += 1
        problems.append(f"{rp}:{first[0]}: {first[1]}")

    problems = g.errors + problems
    for p in problems:
        print("vscode grammar:", p)
    status = "FAIL" if problems else "ok"
    print(f"vscode grammar: {status}: {len(files)} files, {lines_total} lines, {leaks} leaks, "
          f"{expected} files with unterminated literals the lexer also rejects, {len(SAMPLES)} samples")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
