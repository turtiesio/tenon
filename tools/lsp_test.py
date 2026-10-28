#!/usr/bin/env python3
"""Language server test: builds selfhost/tenonlsp.tn and drives it over stdio.

    tools/lsp_test.py [-v]

Scripted sessions against the fixtures in tests/lsp/ assert exact responses:
the lifecycle (initialize, shutdown, exit status), protocol errors,
diagnostics (equal to `tenon check` on the same text, parse errors too, from
unsaved buffers), hover, go to definition (locals, functions, types, fields,
variants, an imported module, the prelude) and completion (after `.` and at
the start of a statement), and a file in a package (docs/packages.md):
imports resolved through tenon.lock, a missing lock as the diagnostic. Also runs the JSON tests (selfhost/jsontest.tn)
and the VS Code client (editors/vscode/extension.js: `node --check`, then
tools/lsp_client_test.js against the server; skipped without node), and
reports how long the server takes to check selfhost/tenonc.tn.
Exit status 1 on the first failure.
"""
import json, os, shutil, subprocess, sys, tempfile, threading, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TENON = os.path.join(ROOT, "target", "release", "tenon")
LSP = os.path.join(ROOT, "tests", "lsp")
VERBOSE = "-v" in sys.argv


def fail(msg):
    print("FAIL lsp:", msg)
    sys.exit(1)


def uri(path):
    return "file://" + path


class Server:
    def __init__(self, exe):
        self.p = subprocess.Popen([exe, "--root", ROOT], stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd=ROOT)
        self.next_id = 1
        self.pending = []  # notifications received while waiting for a response
        self.timer = threading.Timer(30, self.p.kill)
        self.timer.start()

    def send_raw(self, body):
        self.p.stdin.write(b"Content-Length: %d\r\n\r\n" % len(body) + body)
        self.p.stdin.flush()

    def send(self, msg):
        msg = dict(msg, jsonrpc="2.0")
        self.send_raw(json.dumps(msg).encode())

    def recv(self):
        length = None
        while True:
            line = self.p.stdout.readline()
            if not line:
                fail("server closed its output")
            line = line.rstrip(b"\r\n")
            if not line:
                break
            k, _, v = line.partition(b":")
            if k.strip().lower() == b"content-length":
                length = int(v)
        body = self.p.stdout.read(length)
        msg = json.loads(body)
        if VERBOSE:
            print("<-", json.dumps(msg)[:300])
        return msg

    def request(self, method, params=None):
        i = self.next_id
        self.next_id += 1
        self.send({"id": i, "method": method, "params": params or {}})
        while True:
            m = self.recv()
            if m.get("id") == i and "method" not in m:
                return m
            self.pending.append(m)

    def notify(self, method, params):
        self.send({"method": method, "params": params})

    def diagnostics(self, u):
        """The next publishDiagnostics for URI u."""
        while True:
            m = self.pending.pop(0) if self.pending else self.recv()
            if m.get("method") == "textDocument/publishDiagnostics" and m["params"]["uri"] == u:
                return m["params"]["diagnostics"]

    def close(self):
        self.p.stdin.close()
        status = self.p.wait()
        self.timer.cancel()
        return status


def expect(what, got, want):
    if got != want:
        fail("%s:\n  got  %s\n  want %s" % (what, json.dumps(got), json.dumps(want)))


class Doc:
    """A fixture: its text, URI and positions found by searching the text."""

    def __init__(self, path, text=None):
        self.path = path
        self.uri = uri(path)
        self.text = text if text is not None else open(path, encoding="utf-8").read()

    def pos(self, context, word, nth=0):
        """Position of `word` inside the nth occurrence of `context` (0-based line and UTF-16 character)."""
        at = -1
        for _ in range(nth + 1):
            at = self.text.index(context, at + 1)
        at += context.index(word)
        line = self.text.count("\n", 0, at)
        col = at - (self.text.rfind("\n", 0, at) + 1)
        return {"line": line, "character": len(self.text[at - col:at].encode("utf-16-le")) // 2}

    def range(self, context, word, nth=0):
        p = self.pos(context, word, nth)
        return {"start": p, "end": {"line": p["line"], "character": p["character"] + len(word)}}


def tenon_check(text):
    """`tenon check` on text: None if accepted, else (line, col, message)."""
    with tempfile.NamedTemporaryFile("w", suffix=".tn", dir=LSP, delete=False) as f:
        f.write(text)
    try:
        r = subprocess.run([TENON, "check", f.name], capture_output=True, text=True)
    finally:
        os.unlink(f.name)
    if r.returncode == 0:
        return None
    first = r.stderr.splitlines()[0]
    _, line, col, rest = first.split(":", 3)
    return int(line), int(col), rest.split("error: ", 1)[1]


def check_diags(srv, doc, what):
    """The server's diagnostics for doc equal tenon check's on the same text."""
    got = srv.diagnostics(doc.uri)
    c = tenon_check(doc.text)
    if c is None:
        expect(what, got, [])
        return got
    line, col, msg = c
    if len(got) != 1:
        fail("%s: want one diagnostic, got %s" % (what, json.dumps(got)))
    d = got[0]
    expect(what + " (message)", d["message"], msg)
    # tenon counts bytes, the protocol UTF-16 code units
    prefix = doc.text.split("\n")[line - 1].encode()[:col - 1].decode()
    expect(what + " (start)", d["range"]["start"], {"line": line - 1, "character": len(prefix.encode("utf-16-le")) // 2})
    expect(what + " (severity)", d["severity"], 1)
    return got


def hover(srv, doc, context, word, nth=0):
    r = srv.request("textDocument/hover", {"textDocument": {"uri": doc.uri}, "position": doc.pos(context, word, nth)})
    res = r.get("result")
    if res is None:
        return None
    expect("hover range of %r" % word, res["range"], doc.range(context, word, nth))
    v = res["contents"]["value"]
    if not v.startswith("```tenon\n"):
        fail("hover of %r is not a tenon code block: %r" % (word, v))
    return v[len("```tenon\n"):]


def definition(srv, doc, context, word, nth=0):
    r = srv.request("textDocument/definition", {"textDocument": {"uri": doc.uri}, "position": doc.pos(context, word, nth)})
    return r.get("result")


def completion(srv, doc, line, character):
    r = srv.request("textDocument/completion", {"textDocument": {"uri": doc.uri}, "position": {"line": line, "character": character}})
    return {i["label"]: i for i in r["result"]["items"]}


def location(path, context, word, nth=0):
    d = Doc(path)
    return {"uri": uri(path), "range": d.range(context, word, nth)}


def lifecycle(exe):
    srv = Server(exe)
    r = srv.request("textDocument/hover", {})
    expect("request before initialize", r.get("error", {}).get("code"), -32002)
    r = srv.request("initialize", {"processId": None, "rootUri": None, "capabilities": {}})
    caps = r["result"]["capabilities"]
    expect("capabilities", caps, {
        "textDocumentSync": {"openClose": True, "change": 1, "save": {"includeText": False}},
        "hoverProvider": True, "definitionProvider": True,
        "completionProvider": {"triggerCharacters": ["."]},
    })
    srv.notify("initialized", {})
    r = srv.request("workspace/symbol", {"query": ""})
    expect("unknown method", r.get("error", {}).get("code"), -32601)
    srv.send_raw(b'{"jsonrpc": "2.0", "id": 99, "method": ')
    m = srv.recv()
    expect("invalid JSON", (m.get("id"), m.get("error", {}).get("code")), (None, -32700))
    srv.send_raw(b'{"jsonrpc":"2.0","id":7,"method":"shutdown","params":null}')
    m = srv.recv()
    expect("shutdown", m, {"jsonrpc": "2.0", "id": 7, "result": None})
    r = srv.request("textDocument/hover", {})
    expect("request after shutdown", r.get("error", {}).get("code"), -32600)
    srv.notify("exit", {})
    expect("exit status after shutdown", srv.close(), 0)
    srv = Server(exe)
    srv.request("initialize", {"capabilities": {}})
    srv.notify("exit", {})
    expect("exit status without shutdown", srv.close(), 1)


def diagnostics(srv):
    broken = Doc(os.path.join(LSP, "broken.tn"))
    srv.notify("textDocument/didOpen", {"textDocument": {"uri": broken.uri, "languageId": "tenon", "version": 1, "text": broken.text}})
    d = check_diags(srv, broken, "diagnostic of broken.tn")
    expect("diagnostic range", d[0]["range"], broken.range("label(2)", "("))
    # unsaved edits are checked from the buffer: fixed, a parse error, an error in a lambda, a non-ASCII line
    edits = [
        broken.text.replace("label(2)", "label(2).len()"),
        broken.text.replace("let count", "let count ="),
        broken.text.replace("sys.console.println(\"{count}\")", "let f = fn(x: Int) => x + \"s\""),
        broken.text.replace("let count", "let s = \"é😀\"; let count"),
        broken.text.replace("let count", "let é = 1; let count"),
        broken.text.replace("fn label", "fn Label"),
    ]
    for v, text in enumerate(edits):
        doc = Doc(broken.path, text)
        srv.notify("textDocument/didChange", {"textDocument": {"uri": broken.uri, "version": v + 2}, "contentChanges": [{"text": text}]})
        check_diags(srv, doc, "diagnostic after edit %d" % (v + 1))
    # an error in an imported module is shown at the start of the importer
    srv.notify("textDocument/didChange", {"textDocument": {"uri": broken.uri, "version": 9},
                                          "contentChanges": [{"text": "import nosuch\nfn main() {}\n"}]})
    d = srv.diagnostics(broken.uri)
    expect("missing module", [x["message"] for x in d], ["cannot find module 'nosuch' (%s/nosuch.tn or the standard library)" % LSP])
    srv.notify("textDocument/didClose", {"textDocument": {"uri": broken.uri}})
    expect("diagnostics cleared on close", srv.diagnostics(broken.uri), [])


def hovers(srv, main):
    cases = [
        (("total([pt])", "pt"), "pt: Point"),
        (("let pt", "pt"), "pt: Point"),
        (("p.norm1()", "norm1"), "fn Point.norm1(self) -> Int"),
        (("fn Point.norm1", "norm1"), "fn Point.norm1(self) -> Int"),
        (("self.x.abs", "x"), "x: Int  // field of Point"),
        (("self.x.abs", "abs"), "fn Int.abs(self) -> Int"),
        (("shapes.area(", "area"), "fn shapes.area(s: shapes.Shape) -> Int\n```\n\nThe area, rounded down."),
        (("Square(2)", "Square"), "Square(Int)  // enum shapes.Shape { Square(Int), Circle(Int) }\n```\n\nhere: `shapes.Shape`"),
        (("= North", "North"), "North  // enum Dir { North, South }\n```\n\nhere: `Dir`"),
        (("\"a b\".split", "split"), "fn Str.split(self, sep: Str) -> List[Str]"),
        (("words.join", "words"), "words: List[Str]"),
        (("words.join", "join"), "fn List[Str].join(self, sep: Str) -> Str"),
        (("sys.console", "console"), "console: Console  // field of Sys"),
        (("fn main(sys", "sys"), "sys: Sys"),
        (("ps: List[Point]", "Point"), "struct Point { x: Int, y: Int }"),
        (("ps: List[Point]", "List"), "List\n```\n\nbuiltin type"),
        (("for p in", "p"), "p: Point"),
        (("sum += ", "sum"), "sum: Int"),
        (("{total(", "total"), "fn total(ps: List[Point]) -> Int"),
        (("import shapes", "shapes"), "import shapes\n```\n\n" + os.path.join(LSP, "shapes.tn")),
    ]
    for (ctx, word), want in cases:
        got = hover(srv, main, ctx, word)
        if got is None or not got.startswith(want):
            fail("hover of %r in %r:\n  got  %r\n  want %r..." % (word, ctx, got, want))
    expect("hover on a keyword", hover(srv, main, "let con", "let"), None)


def degraded(srv, main):
    """Answers while the buffer is broken."""
    def edit(v, text):
        srv.notify("textDocument/didChange", {"textDocument": {"uri": main.uri, "version": v}, "contentChanges": [{"text": text}]})
        doc = Doc(main.path, text)
        check_diags(srv, doc, "diagnostic of edit %d" % v)
        return doc

    # a type error in one function: the others keep their tables, and it keeps them up to the error
    doc = edit(30, main.text.replace("    sum\n}", "    sum + \"x\"\n}"))
    expect("hover beside a type error", hover(srv, doc, "total([pt])", "pt"), "pt: Point\n```")
    expect("hover before a type error", hover(srv, doc, "sum + ", "sum"), "sum: Int\n```")
    # a parse error: lines above it are answered from the last analysis, lines below it not
    edit(31, main.text)
    doc = edit(32, main.text.replace("    let words", "    let = )\n    let words"))
    expect("hover above a parse error", hover(srv, doc, "total([pt])", "pt"), "pt: Point\n```")
    expect("hover below a parse error", hover(srv, doc, "words.join", "words"), None)
    edit(33, main.text)


def definitions(srv, main):
    shapes = os.path.join(LSP, "shapes.tn")
    prelude = os.path.join(ROOT, "lib", "prelude.tn")
    cases = [
        (("total([pt])", "pt"), location(main.path, "let pt", "pt")),
        (("total([pt])", "total"), location(main.path, "fn total", "total")),
        (("p.norm1()", "norm1"), location(main.path, "fn Point.norm1", "norm1")),
        (("self.x.abs", "x"), location(main.path, "x: Int", "x")),
        (("self.y.abs", "y"), location(main.path, "y: Int", "y")),
        (("ps: List[Point]", "Point"), location(main.path, "struct Point", "Point")),
        (("= North", "North"), location(main.path, "{ North", "North")),
        (("for p in ps", "ps"), location(main.path, "fn total(ps", "ps")),
        (("sum += p", "p"), location(main.path, "for p in", "p")),
        (("shapes.area(", "area"), location(shapes, "pub fn area", "area")),
        (("Square(2)", "Square"), location(shapes, "Square(Int)", "Square")),
        (("import shapes", "shapes"), {"uri": uri(shapes), "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 1}}}),
        (("\"a b\".split", "split"), location(prelude, "extern fn Str.split", "split")),
        (("words.join", "join"), location(prelude, "extern fn List[Str].join", "join")),
        (("sys.console", "console"), location(prelude, "pub console", "console")),
        (("fn main(sys: Sys", "Sys"), location(prelude, "pub struct Sys", "Sys")),
    ]
    for (ctx, word), want in cases:
        expect("definition of %r in %r" % (word, ctx), definition(srv, main, ctx, word), want)
    expect("definition of a literal", definition(srv, main, "x: 3", "3"), None)


def completions(srv, main):
    def edit(v, text):
        srv.notify("textDocument/didChange", {"textDocument": {"uri": main.uri, "version": v}, "contentChanges": [{"text": text}]})
        srv.diagnostics(main.uri)
        return Doc(main.path, text)

    def has(what, items, labels):
        missing = [l for l in labels if l not in items]
        if missing:
            fail("completion %s: missing %s (got %s)" % (what, missing, sorted(items)[:40]))

    def lacks(what, items, labels):
        extra = [l for l in labels if l in items]
        if extra:
            fail("completion %s: unexpected %s" % (what, extra))

    anchor = "    con.println(words.join(\",\"))\n"
    line = main.text[:main.text.index(anchor)].count("\n")
    # after `.` with nothing typed yet (the buffer does not parse)
    for v, (recv, want, not_want) in enumerate([
        ("pt", ["x", "y", "norm1", "to_str"], ["abs", "len"]),
        ("words", ["len", "push", "join", "map", "is_empty"], ["x", "norm1"]),
        ("con", ["println", "print", "read_line", "read_bytes"], ["x"]),
        ("shapes", ["area", "Shape"], ["main", "x"]),
        ("Dir", ["North", "South"], ["x"]),
        ("pt.x", ["abs", "max", "to_str"], ["y"]),
    ]):
        doc = edit(v + 2, main.text.replace(anchor, anchor + "    " + recv + ".\n"))
        items = completion(srv, doc, line + 1, 4 + len(recv) + 1)
        has("after %r." % recv, items, want)
        lacks("after %r." % recv, items, not_want)
    expect("kind of a field", items["abs"]["kind"], 2)
    # after `.` with a prefix typed (the buffer parses, the checker rejects it)
    doc = edit(20, main.text.replace(anchor, anchor + "    pt.no\n"))
    items = completion(srv, doc, line + 1, len("    pt.no"))
    has("after 'pt.no'", items, ["norm1", "x"])
    # at the start of a statement
    doc = edit(21, main.text.replace(anchor, anchor + "    \n"))
    items = completion(srv, doc, line + 1, 4)
    has("at statement start", items, ["pt", "con", "words", "area", "dir", "sys", "total", "main", "Point", "Dir",
                                      "North", "Square", "shapes", "Some", "Option", "Int", "List", "let", "while",
                                      "match", "rev_range", "path_join"])
    lacks("at statement start", items, ["sum", "ps", "p", "norm1", "Point.norm1", "shapes.area"])
    expect("kind of a local", (items["pt"]["kind"], items["pt"]["detail"]), (6, "Point"))
    expect("kind of a function", (items["total"]["kind"], items["total"]["detail"]), (3, "fn total(ps: List[Point]) -> Int"))
    expect("kind of a keyword", items["let"]["kind"], 14)
    # inside a block of another function: its own locals only
    items = completion(srv, doc, main.text[:main.text.index("    sum\n")].count("\n"), 4)
    has("in total", items, ["sum", "ps", "total"])
    lacks("in total", items, ["pt", "con", "p"])
    edit(22, main.text)


def packages(srv, tmp):
    """A file in a package imports a path dependency (after `tenonc fetch`)."""
    ws = os.path.realpath(tmp)
    app, util = os.path.join(ws, "app"), os.path.join(ws, "util")
    for d in (app, util):
        os.makedirs(os.path.join(d, "src"))
    with open(os.path.join(app, "tenon.toml"), "w") as f:
        f.write('[package]\nname = "app"\nversion = "0.1.0"\n\n[dependencies]\nutil = { path = "../util" }\n')
    with open(os.path.join(util, "tenon.toml"), "w") as f:
        f.write('[package]\nname = "util"\nversion = "1.0.0"\n')
    with open(os.path.join(util, "src", "util.tn"), "w") as f:
        f.write("pub fn double(n: Int) -> Int { n * 2 }\n")
    doc = Doc(os.path.join(app, "src", "main.tn"), "import util\n\nfn main(sys: Sys) { sys.console.println(\"{util.double(2)}\") }\n")
    srv.notify("textDocument/didOpen", {"textDocument": {"uri": doc.uri, "languageId": "tenon", "version": 1, "text": doc.text}})
    expect("package file without tenon.lock", [x["message"] for x in srv.diagnostics(doc.uri)],
           ["no %s/tenon.lock for %s/tenon.toml; run `tenonc fetch`" % (app, app)])
    tenonc = os.environ.get("TENONC") or os.path.join(ROOT, "target", "tenonc")
    r = subprocess.run([tenonc, "fetch", app], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        fail("tenonc fetch: " + r.stdout + r.stderr)
    srv.notify("textDocument/didSave", {"textDocument": {"uri": doc.uri}})
    expect("package file after tenonc fetch", srv.diagnostics(doc.uri), [])
    expect("definition in a dependency", definition(srv, doc, "util.double", "double"),
           location(os.path.join(util, "src", "util.tn"), "pub fn double", "double"))
    srv.notify("textDocument/didClose", {"textDocument": {"uri": doc.uri}})
    srv.diagnostics(doc.uri)


def latency(srv):
    path = os.path.join(ROOT, "selfhost", "tenonc.tn")
    doc = Doc(path)
    t = time.time()
    srv.notify("textDocument/didOpen", {"textDocument": {"uri": doc.uri, "languageId": "tenon", "version": 1, "text": doc.text}})
    expect("diagnostics of selfhost/tenonc.tn", srv.diagnostics(doc.uri), [])
    open_ms = (time.time() - t) * 1000
    t = time.time()
    r = srv.request("textDocument/hover", {"textDocument": {"uri": doc.uri}, "position": doc.pos("front.load_in(sys.fs", "load_in")})
    hover_ms = (time.time() - t) * 1000
    if "front.load" not in r["result"]["contents"]["value"]:
        fail("hover in tenonc.tn: %s" % r)
    return open_ms, hover_ms


def main():
    t0 = time.time()
    tmp = tempfile.mkdtemp()
    exe = os.path.join(tmp, "tenonlsp")
    r = subprocess.run([TENON, "build", "selfhost/tenonlsp.tn", "-o", exe, "-O0"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        fail("cannot build selfhost/tenonlsp.tn:\n" + r.stderr)
    r = subprocess.run([TENON, "run", "selfhost/jsontest.tn"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        fail(r.stdout + r.stderr)
    json_result = r.stdout.strip()
    lifecycle(exe)
    srv = Server(exe)
    srv.request("initialize", {"capabilities": {}})
    srv.notify("initialized", {})
    diagnostics(srv)
    main_doc = Doc(os.path.join(LSP, "main.tn"))
    srv.notify("textDocument/didOpen", {"textDocument": {"uri": main_doc.uri, "languageId": "tenon", "version": 1, "text": main_doc.text}})
    expect("diagnostics of main.tn", srv.diagnostics(main_doc.uri), [])
    hovers(srv, main_doc)
    degraded(srv, main_doc)
    definitions(srv, main_doc)
    completions(srv, main_doc)
    packages(srv, tmp)
    open_ms, hover_ms = latency(srv)
    expect("shutdown", srv.request("shutdown").get("result", "missing"), None)
    srv.notify("exit", {})
    expect("exit status", srv.close(), 0)
    client = "vscode client: skipped (no node)"
    if shutil.which("node"):
        for cmd in (["node", "--check", "editors/vscode/extension.js"], ["node", "tools/lsp_client_test.js", ROOT, exe]):
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                fail(" ".join(cmd[:2]) + ":\n" + r.stdout + r.stderr)
        client = r.stdout.strip()
    shutil.rmtree(tmp)
    print("lsp: ok (%s; %s; check of selfhost/tenonc.tn through the server %.0f ms, hover %.0f ms, -O0 build; %.1fs)"
          % (json_result, client, open_ms, hover_ms, time.time() - t0))


if __name__ == "__main__":
    main()
