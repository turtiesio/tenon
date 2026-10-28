if (process.argv.length > 2) { console.error('No arguments allowed'); process.exit(2); }
type Directory = { kind: 'directory'; name: string; parent: Directory; entries: Map<string, Node> };
type File = { kind: 'file'; name: string; parent: Directory; text: string };
type Node = Directory | File;
const root = { kind: 'directory', name: '', entries: new Map() } as Directory;
root.parent = root;
let cwd = root;
type Resolution = { node: Node; parent?: never; name?: never } | { node?: never; parent: Directory; name: string };
function validPath(path: string): boolean {
  return path.length <= 200 && (path === '/' || /^\/?[A-Za-z0-9._-]{1,32}(\/[A-Za-z0-9._-]{1,32})*$/.test(path));
}
function resolve(path: string): Resolution {
  let node: Node = path.startsWith('/') ? root : cwd;
  if (path === '/') return { node };
  const parts = (path.startsWith('/') ? path.slice(1) : path).split('/');
  for (let i = 0; i < parts.length; i++) {
    if (node.kind === 'file') throw Error('not a directory');
    const part = parts[i];
    if (part === '.') continue;
    if (part === '..') { node = node.parent; continue; }
    const child = node.entries.get(part);
    if (!child) {
      if (i === parts.length - 1) return { parent: node, name: part };
      throw Error('not found');
    }
    node = child;
  }
  return { node };
}
function within(node: Directory, ancestor: Directory): boolean {
  for (;;) { if (node === ancestor) return true; if (node === root) return false; node = node.parent; }
}
function usage(node: Node): string {
  let bytes = 0, files = 0, dirs = 0;
  const stack: Node[] = [node];
  while (stack.length) {
    const current = stack.pop()!;
    if (current.kind === 'file') { bytes += current.text.length; files++; }
    else { if (current !== node) dirs++; stack.push(...current.entries.values()); }
  }
  return `${bytes} ${files} ${dirs}`;
}
function execute(line: string): string {
  if (line === 'PWD') {
    const parts: string[] = [];
    for (let node = cwd; node !== root; node = node.parent) parts.push(node.name);
    return '/' + parts.reverse().join('/');
  }
  let command: string, paths: string[], text = '';
  const write = /^WRITE (\S+) ([\x20-\x7e]{1,100})$/.exec(line);
  if (write) { command = 'WRITE'; paths = [write[1]]; text = write[2]; }
  else {
    const tokens = line.split(' '); command = tokens[0]; paths = tokens.slice(1);
    const count = command === 'MV' ? 2 : ['CD', 'MKDIR', 'CAT', 'RM'].includes(command) ? 1 : ['LS', 'DU'].includes(command) ? -1 : -2;
    if ((count >= 0 && paths.length !== count) || (count === -1 && paths.length > 1) || count === -2) return 'ERR bad command';
  }
  if (!paths.every(validPath)) return 'ERR bad command';
  const result = paths.length ? resolve(paths[0]) : { node: cwd };
  if (command === 'MKDIR') {
    if (result.node) return 'ERR exists';
    const node: Directory = { kind: 'directory', name: result.name, parent: result.parent, entries: new Map() };
    result.parent.entries.set(result.name, node); return 'OK';
  }
  if (command === 'WRITE') {
    if (result.node?.kind === 'directory') return 'ERR is a directory';
    if (result.node) result.node.text = text;
    else result.parent.entries.set(result.name, { kind: 'file', name: result.name, parent: result.parent, text });
    return 'OK';
  }
  const node = result.node;
  if (!node) return 'ERR not found';
  if (command === 'CD') { if (node.kind === 'file') return 'ERR not a directory'; cwd = node; return 'OK'; }
  if (command === 'CAT') return node.kind === 'file' ? node.text : 'ERR is a directory';
  if (command === 'LS') {
    if (node.kind === 'file') return node.name;
    return [...node.entries.keys()].sort().map(name => name + (node.entries.get(name)!.kind === 'directory' ? '/' : '')).join(' ') || '-';
  }
  if (command === 'DU') return usage(node);
  if (command === 'RM') {
    if (node.kind === 'directory' && within(cwd, node)) return 'ERR busy';
    if (node.kind === 'directory' && node.entries.size) return 'ERR not empty';
    node.parent.entries.delete(node.name); return 'OK';
  }
  if (node === root) return 'ERR invalid';
  const destination = resolve(paths[1]);
  let parent: Directory, name: string;
  if (destination.node) {
    if (destination.node.kind === 'file') return 'ERR exists';
    parent = destination.node; name = node.name;
    if (parent.entries.has(name)) return 'ERR exists';
  } else { parent = destination.parent; name = destination.name; }
  if (node.kind === 'directory' && within(parent, node)) return 'ERR invalid';
  node.parent.entries.delete(node.name);
  node.parent = parent; node.name = name; parent.entries.set(name, node); return 'OK';
}
function respond(line: string): void {
  let response: string;
  try { response = execute(line.replace(/\r$/, '')); }
  catch (error) { response = 'ERR ' + (error as Error).message; }
  process.stdout.write(response + '\n');
}
process.stdin.setEncoding('utf8');
let pending = '';
for await (const chunk of process.stdin) {
  pending += chunk;
  let end: number;
  while ((end = pending.indexOf('\n')) >= 0) { respond(pending.slice(0, end)); pending = pending.slice(end + 1); }
}
if (pending.length) respond(pending);
