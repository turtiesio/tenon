import { writeSync } from "node:fs";

interface DirNode {
  kind: "dir";
  name: string;
  parent: DirNode | null; // null only for the root
  children: Map<string, Node>;
}

interface FileNode {
  kind: "file";
  name: string;
  parent: DirNode;
  text: string;
}

type Node = DirNode | FileNode;

type Resolved =
  | { type: "found"; node: Node }
  | { type: "missing"; parent: DirNode; name: string }
  | { type: "error"; message: string };

const root: DirNode = { kind: "dir", name: "", parent: null, children: new Map() };
let cwd: DirNode = root;

const COMPONENT = /^[A-Za-z0-9._-]{1,32}$/; // also matches "." and ".."
const TEXT = /^[\x20-\x7E]{1,100}$/;

function isValidPath(path: string): boolean {
  if (path === "/") return true;
  const body = path.startsWith("/") ? path.slice(1) : path;
  return body.split("/").every((c) => COMPONENT.test(c));
}

function resolve(path: string): Resolved {
  const components = path === "/" ? [] : (path.startsWith("/") ? path.slice(1) : path).split("/");
  let current: Node = path.startsWith("/") ? root : cwd;
  for (let i = 0; i < components.length; i++) {
    if (current.kind === "file") return { type: "error", message: "ERR not a directory" };
    const c = components[i];
    if (c === ".") continue;
    if (c === "..") {
      current = current.parent ?? current;
      continue;
    }
    const child: Node | undefined = current.children.get(c);
    if (child !== undefined) {
      current = child;
    } else if (i === components.length - 1) {
      return { type: "missing", parent: current, name: c };
    } else {
      return { type: "error", message: "ERR not found" };
    }
  }
  return { type: "found", node: current };
}

function absolutePath(dir: DirNode): string {
  const names: string[] = [];
  for (let n: DirNode | null = dir; n !== null && n.parent !== null; n = n.parent) names.unshift(n.name);
  return "/" + names.join("/");
}

// True if `ancestor` is `node` or contains it at any depth.
function contains(ancestor: Node, node: Node): boolean {
  for (let n: Node | null = node; n !== null; n = n.parent) {
    if (n === ancestor) return true;
  }
  return false;
}

function usage(node: Node): { bytes: number; files: number; dirs: number } {
  if (node.kind === "file") return { bytes: node.text.length, files: 1, dirs: 0 };
  const total = { bytes: 0, files: 0, dirs: 0 };
  for (const child of node.children.values()) {
    const u = usage(child);
    total.bytes += u.bytes;
    total.files += u.files;
    total.dirs += u.dirs + (child.kind === "dir" ? 1 : 0);
  }
  return total;
}

function listing(dir: DirNode): string {
  if (dir.children.size === 0) return "-";
  return [...dir.children.values()]
    .map((n) => (n.kind === "dir" ? n.name + "/" : n.name))
    .sort()
    .join(" ");
}

function move(srcPath: string, dstPath: string): string {
  const src = resolve(srcPath);
  if (src.type === "error") return src.message;
  if (src.type === "missing") return "ERR not found";
  const node = src.node;
  if (node === root) return "ERR invalid";

  const dst = resolve(dstPath);
  if (dst.type === "error") return dst.message;
  let targetParent: DirNode;
  let targetName: string;
  if (dst.type === "missing") {
    targetParent = dst.parent;
    targetName = dst.name;
  } else if (dst.node.kind === "dir") {
    targetParent = dst.node;
    targetName = node.name;
    if (targetParent.children.has(targetName)) return "ERR exists";
  } else {
    return "ERR exists";
  }

  if (node.kind === "dir" && contains(node, targetParent)) return "ERR invalid";

  node.parent!.children.delete(node.name);
  node.name = targetName;
  node.parent = targetParent;
  targetParent.children.set(targetName, node);
  return "OK";
}

function handle(line: string): string {
  const bad = "ERR bad command";

  if (line.startsWith("WRITE ")) {
    const rest = line.slice("WRITE ".length);
    const space = rest.indexOf(" ");
    if (space === -1) return bad;
    const path = rest.slice(0, space);
    const text = rest.slice(space + 1);
    if (!isValidPath(path) || !TEXT.test(text)) return bad;
    const r = resolve(path);
    if (r.type === "error") return r.message;
    if (r.type === "missing") {
      r.parent.children.set(r.name, { kind: "file", name: r.name, parent: r.parent, text });
      return "OK";
    }
    if (r.node.kind === "dir") return "ERR is a directory";
    r.node.text = text;
    return "OK";
  }

  const t = line.split(" ");
  const argc = t.length - 1;
  const pathsOk = t.slice(1).every(isValidPath);
  switch (t[0]) {
    case "PWD":
      return argc === 0 ? absolutePath(cwd) : bad;
    case "CD": {
      if (argc !== 1 || !pathsOk) return bad;
      const r = resolve(t[1]);
      if (r.type === "error") return r.message;
      if (r.type === "missing") return "ERR not found";
      if (r.node.kind === "file") return "ERR not a directory";
      cwd = r.node;
      return "OK";
    }
    case "MKDIR": {
      if (argc !== 1 || !pathsOk) return bad;
      const r = resolve(t[1]);
      if (r.type === "error") return r.message;
      if (r.type === "found") return "ERR exists";
      r.parent.children.set(r.name, { kind: "dir", name: r.name, parent: r.parent, children: new Map() });
      return "OK";
    }
    case "CAT": {
      if (argc !== 1 || !pathsOk) return bad;
      const r = resolve(t[1]);
      if (r.type === "error") return r.message;
      if (r.type === "missing") return "ERR not found";
      return r.node.kind === "dir" ? "ERR is a directory" : r.node.text;
    }
    case "LS": {
      if (argc > 1 || !pathsOk) return bad;
      const r = argc === 0 ? ({ type: "found", node: cwd } as Resolved) : resolve(t[1]);
      if (r.type === "error") return r.message;
      if (r.type === "missing") return "ERR not found";
      return r.node.kind === "dir" ? listing(r.node) : r.node.name;
    }
    case "RM": {
      if (argc !== 1 || !pathsOk) return bad;
      const r = resolve(t[1]);
      if (r.type === "error") return r.message;
      if (r.type === "missing") return "ERR not found";
      const node = r.node;
      if (node === root || contains(node, cwd)) return "ERR busy";
      if (node.kind === "dir" && node.children.size > 0) return "ERR not empty";
      node.parent!.children.delete(node.name);
      return "OK";
    }
    case "MV":
      if (argc !== 2 || !pathsOk) return bad;
      return move(t[1], t[2]);
    case "DU": {
      if (argc > 1 || !pathsOk) return bad;
      const r = argc === 0 ? ({ type: "found", node: cwd } as Resolved) : resolve(t[1]);
      if (r.type === "error") return r.message;
      if (r.type === "missing") return "ERR not found";
      const u = usage(r.node);
      return `${u.bytes} ${u.files} ${u.dirs}`;
    }
    default:
      return bad;
  }
}

// Synchronous write so every response is flushed immediately.
function writeLine(text: string): void {
  const buf = Buffer.from(text + "\n", "latin1");
  let offset = 0;
  while (offset < buf.length) {
    try {
      offset += writeSync(1, buf, offset);
    } catch (e) {
      if ((e as NodeJS.ErrnoException).code !== "EAGAIN") throw e;
    }
  }
}

function processLine(raw: string): void {
  writeLine(handle(raw.endsWith("\r") ? raw.slice(0, -1) : raw));
}

function main(): void {
  if (process.argv.length > 2) {
    process.stderr.write("usage: vfs (commands on stdin)\n");
    process.exitCode = 2;
    return;
  }
  // Split on "\n" only (readline would also split on a lone "\r").
  let pending = "";
  process.stdin.setEncoding("latin1");
  process.stdin.on("data", (chunk: string) => {
    pending += chunk;
    let newline: number;
    while ((newline = pending.indexOf("\n")) !== -1) {
      processLine(pending.slice(0, newline));
      pending = pending.slice(newline + 1);
    }
  });
  process.stdin.on("end", () => {
    if (pending !== "") processLine(pending);
  });
}

main();
