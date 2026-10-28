// The VS Code client (editors/vscode/extension.js) against the real server,
// with a stand-in for the `vscode` module: activation starts the server,
// open buffers are sent, and diagnostics, hover, definition and completion
// come back through the registered providers; deactivation shuts it down.
// Run by tools/lsp_test.py: node tools/lsp_client_test.js ROOT SERVER
"use strict";
const Module = require("module");
const assert = require("assert");
const fs = require("fs");
const path = require("path");

const [ROOT, SERVER] = process.argv.slice(2);
const file = path.join(ROOT, "tests", "lsp", "main.tn");
const text = fs.readFileSync(file, "utf8");
const providers = {};
const published = [];
let opened = null;

class Range {
  constructor(a, b, c, d) { this.span = [a, b, c, d]; }
}
const docUri = { toString: () => "file://" + file, scheme: "file", fsPath: file };
const doc = { languageId: "tenon", uri: docUri, version: 1, getText: () => text };
const vscode = {
  Range,
  Hover: class { constructor(md, r) { this.md = md; this.range = r; } },
  MarkdownString: class { constructor(v) { this.value = v; } },
  Location: class { constructor(u, r) { this.uri = u; this.range = r; } },
  CompletionItem: class { constructor(l, k) { this.label = l; this.kind = k; } },
  Diagnostic: class { constructor(r, m, s) { this.range = r; this.message = m; this.severity = s; } },
  DiagnosticSeverity: { Error: 0, Warning: 1, Information: 2, Hint: 3 },
  Uri: { parse: (s) => ({ parsed: s }) },
  window: {
    createOutputChannel: () => ({ appendLine() {}, append() {}, dispose() {} }),
    showErrorMessage: (m) => assert.fail(m),
  },
  languages: {
    createDiagnosticCollection: () => ({ set: (u, d) => published.push([u.parsed, d]), delete() {}, clear() {}, dispose() {} }),
    registerHoverProvider: (s, p) => (providers.hover = p),
    registerDefinitionProvider: (s, p) => (providers.definition = p),
    registerCompletionItemProvider: (s, p, ...triggers) => {
      assert.deepStrictEqual(triggers, ["."]);
      providers.completion = p;
    },
  },
  workspace: {
    getConfiguration: () => ({ get: (k) => ({ serverPath: SERVER, root: ROOT })[k] }),
    workspaceFolders: [],
    textDocuments: [doc],
    onDidOpenTextDocument: () => ({}),
    onDidChangeTextDocument: () => ({}),
    onDidSaveTextDocument: () => ({}),
    onDidCloseTextDocument: () => ({}),
    onDidChangeConfiguration: () => ({}),
  },
  commands: { registerCommand: () => ({}) },
};
const load = Module._load;
Module._load = function (req, ...rest) {
  return req === "vscode" ? vscode : load.call(this, req, ...rest);
};

(async () => {
  const ext = require(path.join(ROOT, "editors", "vscode", "extension.js"));
  ext.activate({ subscriptions: [] });
  const line = text.split("\n").findIndex((l) => l.includes("total([pt])"));
  const ch = text.split("\n")[line].indexOf("[pt]") + 1;
  const h = await providers.hover.provideHover(doc, { line, character: ch });
  assert.strictEqual(h.md.value, "```tenon\npt: Point\n```");
  assert.deepStrictEqual(h.range.span, [line, ch, line, ch + 2]);
  const d = await providers.definition.provideDefinition(doc, { line, character: ch });
  assert.strictEqual(d.length, 1);
  assert.strictEqual(d[0].uri.parsed, "file://" + file);
  const decl = text.split("\n").findIndex((l) => l.includes("let pt"));
  assert.deepStrictEqual(d[0].range.span, [decl, 8, decl, 10]);
  const items = await providers.completion.provideCompletionItems(doc, { line, character: 4 });
  const pt = items.find((i) => i.label === "pt");
  assert.ok(pt && pt.kind === 5 && pt.detail === "Point", "completion of a local (vscode kind Variable = 5)");
  assert.ok(items.some((i) => i.label === "total" && i.kind === 2), "completion of a function (vscode kind Function = 2)");
  assert.deepStrictEqual(published, [["file://" + file, []]]);
  await ext.deactivate();
  console.log("vscode client: ok");
})().catch((e) => {
  console.log("FAIL vscode client: " + e.message);
  process.exit(1);
});
