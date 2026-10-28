import * as fs from "node:fs";

interface Dir {
  kind: "dir";
  name: string;
  parent: Dir; // the root is its own parent
  children: Map<string, Node>;
}

interface File {
  kind: "file";
  name: string;
  parent: Dir;
  text: string;
}

type Node = Dir | File;

type Resolved =
  | { kind: "node"; node: Node }
  | { kind: "missing"; dir: Dir; name: string }
  | { kind: "error"; message: string };

const PATH = /^(\/|\/?[A-Za-z0-9._-]{1,32}(\/[A-Za-z0-9._-]{1,32})*)$/;
const TEXT = /^[\x20-\x7e]{1,100}$/;
const BAD = "ERR bad command";

class FileSystem {
  readonly root: Dir;
  private cwd: Dir;

  constructor() {
    const root = { kind: "dir", name: "", children: new Map() } as unknown as Dir;
    root.parent = root;
    this.root = root;
    this.cwd = root;
  }

  private resolve(path: string): Resolved {
    const components = path.split("/");
    let node: Node = this.cwd;
    if (path.startsWith("/")) {
      node = this.root;
      components.shift();
    }
    if (path === "/") return { kind: "node", node: this.root };
    for (let i = 0; i < components.length; i++) {
      const component = components[i];
      if (node.kind === "file") return { kind: "error", message: "ERR not a directory" };
      if (component === ".") continue;
      if (component === "..") {
        node = node.parent;
        continue;
      }
      const child = node.children.get(component);
      if (child === undefined) {
        if (i === components.length - 1) return { kind: "missing", dir: node, name: component };
        return { kind: "error", message: "ERR not found" };
      }
      node = child;
    }
    return { kind: "node", node };
  }

  /** True if `node` is `ancestor` or lies anywhere below it. */
  private isWithin(node: Node, ancestor: Dir): boolean {
    let current: Node = node;
    for (;;) {
      if (current === ancestor) return true;
      if (current === this.root) return false;
      current = current.parent;
    }
  }

  private absolutePath(dir: Dir): string {
    const names: string[] = [];
    for (let d = dir; d !== this.root; d = d.parent) names.unshift(d.name);
    return "/" + names.join("/");
  }

  private resolveExisting(path: string): Node | string {
    const r = this.resolve(path);
    if (r.kind === "error") return r.message;
    if (r.kind === "missing") return "ERR not found";
    return r.node;
  }

  execute(line: string): string {
    const writeMatch = /^WRITE ([^ ]+) (.*)$/.exec(line);
    if (writeMatch !== null) {
      const [, path, text] = writeMatch;
      if (!PATH.test(path) || !TEXT.test(text)) return BAD;
      return this.write(path, text);
    }

    const tokens = line.split(" ");
    const [command, ...args] = tokens;
    if (args.some((a) => !PATH.test(a))) return BAD;
    switch (command) {
      case "PWD":
        return args.length === 0 ? this.absolutePath(this.cwd) : BAD;
      case "CD":
        return args.length === 1 ? this.cd(args[0]) : BAD;
      case "MKDIR":
        return args.length === 1 ? this.mkdir(args[0]) : BAD;
      case "CAT":
        return args.length === 1 ? this.cat(args[0]) : BAD;
      case "LS":
        return args.length <= 1 ? this.ls(args[0] ?? ".") : BAD;
      case "RM":
        return args.length === 1 ? this.rm(args[0]) : BAD;
      case "MV":
        return args.length === 2 ? this.mv(args[0], args[1]) : BAD;
      case "DU":
        return args.length <= 1 ? this.du(args[0] ?? ".") : BAD;
      default:
        return BAD;
    }
  }

  private cd(path: string): string {
    const node = this.resolveExisting(path);
    if (typeof node === "string") return node;
    if (node.kind === "file") return "ERR not a directory";
    this.cwd = node;
    return "OK";
  }

  private mkdir(path: string): string {
    const r = this.resolve(path);
    if (r.kind === "error") return r.message;
    if (r.kind === "node") return "ERR exists";
    r.dir.children.set(r.name, { kind: "dir", name: r.name, parent: r.dir, children: new Map() });
    return "OK";
  }

  private write(path: string, text: string): string {
    const r = this.resolve(path);
    if (r.kind === "error") return r.message;
    if (r.kind === "missing") {
      r.dir.children.set(r.name, { kind: "file", name: r.name, parent: r.dir, text });
      return "OK";
    }
    if (r.node.kind === "dir") return "ERR is a directory";
    r.node.text = text;
    return "OK";
  }

  private cat(path: string): string {
    const node = this.resolveExisting(path);
    if (typeof node === "string") return node;
    return node.kind === "file" ? node.text : "ERR is a directory";
  }

  private ls(path: string): string {
    const node = this.resolveExisting(path);
    if (typeof node === "string") return node;
    if (node.kind === "file") return node.name;
    const names = [...node.children.keys()].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
    if (names.length === 0) return "-";
    return names.map((name) => (node.children.get(name)!.kind === "dir" ? name + "/" : name)).join(" ");
  }

  private rm(path: string): string {
    const node = this.resolveExisting(path);
    if (typeof node === "string") return node;
    if (node.kind === "dir") {
      if (node === this.root || this.isWithin(this.cwd, node)) return "ERR busy";
      if (node.children.size > 0) return "ERR not empty";
    }
    node.parent.children.delete(node.name);
    return "OK";
  }

  private mv(srcPath: string, dstPath: string): string {
    const source = this.resolveExisting(srcPath);
    if (typeof source === "string") return source;
    if (source === this.root) return "ERR invalid";

    const r = this.resolve(dstPath);
    if (r.kind === "error") return r.message;
    let targetDir: Dir;
    let targetName: string;
    if (r.kind === "node") {
      if (r.node.kind === "file" || r.node.children.has(source.name)) return "ERR exists";
      targetDir = r.node;
      targetName = source.name;
    } else {
      targetDir = r.dir;
      targetName = r.name;
    }
    if (source.kind === "dir" && this.isWithin(targetDir, source)) return "ERR invalid";

    source.parent.children.delete(source.name);
    source.name = targetName;
    source.parent = targetDir;
    targetDir.children.set(targetName, source);
    return "OK";
  }

  private du(path: string): string {
    const node = this.resolveExisting(path);
    if (typeof node === "string") return node;
    let bytes = 0;
    let files = 0;
    let dirs = 0;
    const visit = (n: Node) => {
      if (n.kind === "file") {
        bytes += n.text.length;
        files++;
      } else {
        for (const child of n.children.values()) {
          if (child.kind === "dir") dirs++;
          visit(child);
        }
      }
    };
    visit(node);
    return `${bytes} ${files} ${dirs}`;
  }
}

function main(): void {
  if (process.argv.length > 2) {
    process.stderr.write("usage: vfs (commands on stdin)\n");
    process.exit(2);
  }

  const vfs = new FileSystem();
  const respond = (raw: string) => {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    fs.writeSync(1, vfs.execute(line) + "\n");
  };

  // Lines are split on "\n" only (readline would also split on a lone "\r").
  let pending = "";
  process.stdin.setEncoding("latin1");
  process.stdin.on("data", (chunk: string) => {
    pending += chunk;
    let nl: number;
    while ((nl = pending.indexOf("\n")) !== -1) {
      respond(pending.slice(0, nl));
      pending = pending.slice(nl + 1);
    }
  });
  process.stdin.on("end", () => {
    if (pending !== "") respond(pending);
  });
}

main();
