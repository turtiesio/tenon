// Tenon language-server client for VS Code. No dependencies: only the `vscode`
// API and Node built-ins. It starts `tenon lsp` (selfhost/lsp.tn), speaks
// JSON-RPC 2.0 with Content-Length framing over the server's stdio, keeps the
// server's view of open .tn buffers in sync (full text on every change), and
// forwards diagnostics, hover, go to definition and completion.
"use strict";

const vscode = require("vscode");
const cp = require("child_process");
const fs = require("fs");
const path = require("path");

const SELECTOR = { language: "tenon" };
const MAX_RESTARTS = 5;

class Client {
  constructor(output, diagnostics) {
    this.output = output;
    this.diagnostics = diagnostics;
    this.proc = null;
    this.buffer = Buffer.alloc(0);
    this.nextId = 1;
    this.pending = new Map(); // id -> {resolve, reject}
    this.ready = null; // promise: initialize answered
    this.stopping = false;
    this.restarts = 0;
  }

  // ---- process and framing ----

  start() {
    const cfg = vscode.workspace.getConfiguration("tenon");
    const exe = cfg.get("serverPath") || "tenon";
    const root = toolchainRoot(cfg.get("root"));
    const args = root ? ["lsp", "--root", root] : ["lsp"];
    this.output.appendLine(`starting ${exe} ${args.join(" ")}`);
    this.buffer = Buffer.alloc(0);
    this.stopping = false;
    let proc;
    try {
      proc = cp.spawn(exe, args, { stdio: ["pipe", "pipe", "pipe"], cwd: root || undefined });
    } catch (e) {
      this.failed(exe, e);
      return;
    }
    this.proc = proc;
    proc.on("error", (e) => this.failed(exe, e));
    proc.stdin.on("error", (e) => this.output.appendLine(`cannot write to the server: ${e.message}`));
    proc.stdout.on("data", (chunk) => this.receive(chunk));
    proc.stderr.on("data", (chunk) => this.output.append(chunk.toString()));
    proc.on("exit", (code, signal) => this.exited(proc, code, signal));
    this.ready = this.request("initialize", {
      processId: process.pid,
      clientInfo: { name: "vscode-tenon" },
      rootUri: workspaceUri(),
      capabilities: {
        textDocument: {
          synchronization: { didSave: true },
          hover: { contentFormat: ["markdown", "plaintext"] },
          completion: { completionItem: { snippetSupport: false } },
          publishDiagnostics: {},
        },
      },
    }).then(() => {
      this.notify("initialized", {});
      for (const doc of vscode.workspace.textDocuments) this.didOpen(doc);
    });
    this.ready.catch((e) => this.output.appendLine(`initialize failed: ${e.message}`));
  }

  failed(exe, e) {
    const msg = e && e.code === "ENOENT"
      ? `Tenon: cannot start the language server '${exe}'. Install 'tenon' (tools/install.sh; see the extension's README) or set "tenon.serverPath".`
      : `Tenon: language server error: ${e && e.message}`;
    this.output.appendLine(msg);
    this.restarts = MAX_RESTARTS; // do not retry a server that cannot start
    this.proc = null;
    for (const p of this.pending.values()) p.reject(new Error(msg));
    this.pending.clear();
    vscode.window.showErrorMessage(msg);
  }

  exited(proc, code, signal) {
    if (proc !== this.proc) return;
    this.proc = null;
    for (const p of this.pending.values()) p.reject(new Error("the language server exited"));
    this.pending.clear();
    this.diagnostics.clear();
    this.output.appendLine(`server exited (status ${code}, signal ${signal})`);
    if (!this.stopping && this.restarts < MAX_RESTARTS) {
      this.restarts += 1;
      setTimeout(() => this.start(), 500);
    }
  }

  send(msg) {
    if (!this.proc) return;
    const body = Buffer.from(JSON.stringify(Object.assign({ jsonrpc: "2.0" }, msg)), "utf8");
    this.proc.stdin.write(`Content-Length: ${body.length}\r\n\r\n`);
    this.proc.stdin.write(body);
  }

  receive(chunk) {
    this.buffer = Buffer.concat([this.buffer, chunk]);
    for (;;) {
      const end = this.buffer.indexOf("\r\n\r\n");
      if (end < 0) return;
      const header = this.buffer.slice(0, end).toString("ascii");
      const m = /content-length:\s*(\d+)/i.exec(header);
      if (!m) {
        this.output.appendLine(`bad header from the server: ${header}`);
        this.buffer = this.buffer.slice(end + 4);
        continue;
      }
      const len = parseInt(m[1], 10);
      if (this.buffer.length < end + 4 + len) return;
      const body = this.buffer.slice(end + 4, end + 4 + len).toString("utf8");
      this.buffer = this.buffer.slice(end + 4 + len);
      let msg;
      try {
        msg = JSON.parse(body);
      } catch (e) {
        this.output.appendLine(`bad JSON from the server: ${body}`);
        continue;
      }
      this.dispatch(msg);
    }
  }

  dispatch(msg) {
    if (msg.method === undefined) {
      const p = this.pending.get(msg.id);
      if (!p) return;
      this.pending.delete(msg.id);
      if (msg.error) p.reject(new Error(msg.error.message));
      else p.resolve(msg.result);
    } else if (msg.id !== undefined) {
      this.send({ id: msg.id, error: { code: -32601, message: `not supported: ${msg.method}` } });
    } else if (msg.method === "textDocument/publishDiagnostics") {
      this.publish(msg.params);
    }
  }

  request(method, params) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      if (!this.proc) return reject(new Error("the language server is not running"));
      this.pending.set(id, { resolve, reject });
      this.send({ id, method, params });
    });
  }

  notify(method, params) {
    this.send({ method, params });
  }

  async stop() {
    this.stopping = true;
    const proc = this.proc;
    if (!proc) return;
    const timer = setTimeout(() => proc.kill(), 2000);
    try {
      await this.request("shutdown", null);
      this.notify("exit", null);
    } catch (e) {
      proc.kill();
    }
    await new Promise((resolve) => (proc.exitCode !== null ? resolve() : proc.on("exit", resolve)));
    clearTimeout(timer);
  }

  // ---- documents ----

  didOpen(doc) {
    if (doc.languageId !== "tenon") return;
    this.notify("textDocument/didOpen", {
      textDocument: { uri: doc.uri.toString(), languageId: "tenon", version: doc.version, text: doc.getText() },
    });
  }

  didChange(e) {
    if (e.document.languageId !== "tenon" || e.contentChanges.length === 0) return;
    this.notify("textDocument/didChange", {
      textDocument: { uri: e.document.uri.toString(), version: e.document.version },
      contentChanges: [{ text: e.document.getText() }],
    });
  }

  didSave(doc) {
    if (doc.languageId === "tenon") this.notify("textDocument/didSave", { textDocument: { uri: doc.uri.toString() } });
  }

  didClose(doc) {
    if (doc.languageId !== "tenon") return;
    this.notify("textDocument/didClose", { textDocument: { uri: doc.uri.toString() } });
    this.diagnostics.delete(doc.uri);
  }

  publish(params) {
    const diags = params.diagnostics.map((d) => {
      const x = new vscode.Diagnostic(range(d.range), d.message, severity(d.severity));
      x.source = d.source || "tenon";
      return x;
    });
    this.diagnostics.set(vscode.Uri.parse(params.uri), diags);
  }

  // ---- requests at a position ----

  // The server's answer, or null if it is not running.
  async at(method, doc, pos) {
    try {
      await this.ready;
      return await this.request(method, {
        textDocument: { uri: doc.uri.toString() },
        position: { line: pos.line, character: pos.character },
      });
    } catch (e) {
      return null;
    }
  }
}

function range(r) {
  return new vscode.Range(r.start.line, r.start.character, r.end.line, r.end.character);
}

function severity(s) {
  switch (s) {
    case 2: return vscode.DiagnosticSeverity.Warning;
    case 3: return vscode.DiagnosticSeverity.Information;
    case 4: return vscode.DiagnosticSeverity.Hint;
    default: return vscode.DiagnosticSeverity.Error;
  }
}

function workspaceUri() {
  const f = vscode.workspace.workspaceFolders;
  return f && f.length ? f[0].uri.toString() : null;
}

// The toolchain root (holding lib/prelude.tn): the setting, else a workspace
// folder that is a Tenon repository, else none (the server then uses
// $TENON_ROOT, else the root next to its executable: docs/tools.md).
function toolchainRoot(setting) {
  if (setting) return setting;
  for (const f of vscode.workspace.workspaceFolders || []) {
    if (f.uri.scheme === "file" && fs.existsSync(path.join(f.uri.fsPath, "lib", "prelude.tn"))) return f.uri.fsPath;
  }
  return process.env.TENON_ROOT || null;
}

let client = null;

function activate(context) {
  const output = vscode.window.createOutputChannel("Tenon");
  const diagnostics = vscode.languages.createDiagnosticCollection("tenon");
  client = new Client(output, diagnostics);
  const c = client;
  context.subscriptions.push(
    output,
    diagnostics,
    vscode.workspace.onDidOpenTextDocument((d) => c.didOpen(d)),
    vscode.workspace.onDidChangeTextDocument((e) => c.didChange(e)),
    vscode.workspace.onDidSaveTextDocument((d) => c.didSave(d)),
    vscode.workspace.onDidCloseTextDocument((d) => c.didClose(d)),
    vscode.languages.registerHoverProvider(SELECTOR, {
      async provideHover(doc, pos) {
        const r = await c.at("textDocument/hover", doc, pos);
        if (!r) return null;
        const value = typeof r.contents === "string" ? r.contents : r.contents.value;
        return new vscode.Hover(new vscode.MarkdownString(value), r.range ? range(r.range) : undefined);
      },
    }),
    vscode.languages.registerDefinitionProvider(SELECTOR, {
      async provideDefinition(doc, pos) {
        const r = await c.at("textDocument/definition", doc, pos);
        if (!r) return null;
        const locs = Array.isArray(r) ? r : [r];
        return locs.map((l) => new vscode.Location(vscode.Uri.parse(l.uri), range(l.range)));
      },
    }),
    vscode.languages.registerCompletionItemProvider(SELECTOR, {
      async provideCompletionItems(doc, pos) {
        const r = await c.at("textDocument/completion", doc, pos);
        if (!r) return [];
        const items = Array.isArray(r) ? r : r.items;
        return items.map((i) => {
          // LSP CompletionItemKind numbers start at 1, vscode.CompletionItemKind at 0
          const x = new vscode.CompletionItem(i.label, i.kind ? i.kind - 1 : undefined);
          if (i.detail) x.detail = i.detail;
          return x;
        });
      },
    }, "."),
    vscode.commands.registerCommand("tenon.restartServer", async () => {
      await c.stop();
      c.restarts = 0;
      c.start();
    }),
    vscode.workspace.onDidChangeConfiguration(async (e) => {
      if (e.affectsConfiguration("tenon")) {
        await c.stop();
        c.restarts = 0;
        c.start();
      }
    }),
  );
  c.start();
}

function deactivate() {
  return client ? client.stop() : undefined;
}

module.exports = { activate, deactivate };
