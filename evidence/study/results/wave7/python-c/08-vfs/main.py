"""vfs: an in-memory file system shell."""
import re
import sys

# A component is a name, "." or ".."; all of them fit this pattern.
COMPONENT = r"[A-Za-z0-9._-]{1,32}"
PATH = re.compile(rf"/|/?{COMPONENT}(?:/{COMPONENT})*")
TEXT = re.compile(r"[ -~]{1,100}")


class VfsError(Exception):
    """A command failure; the message is the response without 'ERR '."""


class Node:
    def __init__(self, name, parent, text=None):
        self.name = name
        self.parent = parent
        self.text = text  # None for a directory
        self.children = {} if text is None else None

    @property
    def is_dir(self):
        return self.children is not None

    def ancestors(self):
        """Yield this node and every node above it, up to the root."""
        node = self
        while node is not None:
            yield node
            node = node.parent


class Missing:
    """A path whose final component does not exist in an existing directory."""

    def __init__(self, parent, name):
        self.parent = parent
        self.name = name


class FileSystem:
    def __init__(self):
        self.root = Node("", None)
        self.cwd = self.root

    # --- paths -----------------------------------------------------------

    def resolve(self, path):
        """Return an existing Node or a Missing; raise VfsError on walk failure."""
        node = self.root if path.startswith("/") else self.cwd
        components = [c for c in path.split("/") if c] if path != "/" else []
        for i, comp in enumerate(components):
            if not node.is_dir:
                raise VfsError("not a directory")
            if comp == ".":
                continue
            if comp == "..":
                node = node.parent or self.root
                continue
            child = node.children.get(comp)
            if child is None:
                if i == len(components) - 1:
                    return Missing(node, comp)
                raise VfsError("not found")
            node = child
        return node

    def existing(self, path):
        node = self.resolve(path)
        if isinstance(node, Missing):
            raise VfsError("not found")
        return node

    def absolute(self, node):
        names = [n.name for n in node.ancestors() if n is not self.root]
        return "/" + "/".join(reversed(names))

    # --- commands --------------------------------------------------------

    def pwd(self):
        return self.absolute(self.cwd)

    def cd(self, path):
        node = self.existing(path)
        if not node.is_dir:
            raise VfsError("not a directory")
        self.cwd = node
        return "OK"

    def mkdir(self, path):
        target = self.resolve(path)
        if not isinstance(target, Missing):
            raise VfsError("exists")
        target.parent.children[target.name] = Node(target.name, target.parent)
        return "OK"

    def write(self, path, text):
        target = self.resolve(path)
        if isinstance(target, Missing):
            target.parent.children[target.name] = Node(target.name, target.parent, text)
        elif target.is_dir:
            raise VfsError("is a directory")
        else:
            target.text = text
        return "OK"

    def cat(self, path):
        node = self.existing(path)
        if node.is_dir:
            raise VfsError("is a directory")
        return node.text

    def ls(self, path="."):
        node = self.existing(path)
        if not node.is_dir:
            return node.name
        names = [name + ("/" if child.is_dir else "")
                 for name, child in sorted(node.children.items(),
                                           key=lambda item: item[0].encode())]
        return " ".join(names) if names else "-"

    def rm(self, path):
        node = self.existing(path)
        if node is self.root or node in self.cwd.ancestors():
            raise VfsError("busy")
        if node.is_dir and node.children:
            raise VfsError("not empty")
        del node.parent.children[node.name]
        return "OK"

    def mv(self, src_path, dst_path):
        src = self.existing(src_path)
        if src is self.root:
            raise VfsError("invalid")
        dst = self.resolve(dst_path)
        if isinstance(dst, Missing):
            parent, name = dst.parent, dst.name
        elif dst.is_dir:
            parent, name = dst, src.name
            if name in parent.children:
                raise VfsError("exists")
        else:
            raise VfsError("exists")
        if src.is_dir and src in parent.ancestors():
            raise VfsError("invalid")
        del src.parent.children[src.name]
        src.name = name
        src.parent = parent
        parent.children[name] = src
        return "OK"

    def du(self, path="."):
        node = self.existing(path)
        if not node.is_dir:
            return f"{len(node.text)} 1 0"
        size = files = dirs = 0
        stack = list(node.children.values())
        while stack:
            child = stack.pop()
            if child.is_dir:
                dirs += 1
                stack.extend(child.children.values())
            else:
                files += 1
                size += len(child.text)
        return f"{size} {files} {dirs}"


# command name -> (handler name, allowed argument counts)
SIMPLE_COMMANDS = {
    "PWD": ("pwd", {0}),
    "CD": ("cd", {1}),
    "MKDIR": ("mkdir", {1}),
    "CAT": ("cat", {1}),
    "LS": ("ls", {0, 1}),
    "RM": ("rm", {1}),
    "MV": ("mv", {2}),
    "DU": ("du", {0, 1}),
}


def parse(line):
    """Return (method name, args) or None for a malformed line."""
    if line.startswith("WRITE "):
        path, sep, text = line[len("WRITE "):].partition(" ")
        if sep and PATH.fullmatch(path) and TEXT.fullmatch(text):
            return "write", [path, text]
        return None
    tokens = line.split(" ")
    entry = SIMPLE_COMMANDS.get(tokens[0])
    if entry is None:
        return None
    method, counts = entry
    args = tokens[1:]
    if len(args) not in counts or not all(PATH.fullmatch(a) for a in args):
        return None
    return method, args


def main(argv):
    if argv:
        print("usage: vfs < commands", file=sys.stderr)
        return 2
    fs = FileSystem()
    for raw in sys.stdin.buffer:
        line = raw.decode("latin-1")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        parsed = parse(line)
        if parsed is None:
            response = "ERR bad command"
        else:
            method, args = parsed
            try:
                response = getattr(fs, method)(*args)
            except VfsError as e:
                response = f"ERR {e}"
        sys.stdout.write(response + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
