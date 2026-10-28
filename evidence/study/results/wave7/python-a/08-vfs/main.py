import re
import sys

NAME_RE = r"[A-Za-z0-9._-]{1,32}"
PATH_RE = re.compile(rf"/|/?{NAME_RE}(/{NAME_RE})*")
TEXT_RE = re.compile(r"[ -~]{1,100}")

BAD = "ERR bad command"


class FsError(Exception):
    """A command failed with the given response line."""


class Node:
    def __init__(self, name, parent, is_dir, text=""):
        self.name = name
        self.parent = parent
        self.is_dir = is_dir
        self.text = text
        self.children = {} if is_dir else None

    def is_within(self, ancestor):
        """True if this node is `ancestor` or lies anywhere below it."""
        node = self
        while node is not None:
            if node is ancestor:
                return True
            node = node.parent
        return False

    def path(self):
        names = []
        node = self
        while node.parent is not None:
            names.append(node.name)
            node = node.parent
        return "/" + "/".join(reversed(names))


class Missing:
    """A final path component that does not exist yet."""

    def __init__(self, parent, name):
        self.parent = parent
        self.name = name


class Vfs:
    def __init__(self):
        self.root = Node("", None, True)
        self.cwd = self.root

    def resolve(self, path):
        """Return an existing Node or a Missing; raise FsError on a failed walk."""
        node = self.root if path.startswith("/") else self.cwd
        components = [c for c in path.split("/") if c]
        for i, comp in enumerate(components):
            if not node.is_dir:
                raise FsError("ERR not a directory")
            if comp == ".":
                continue
            if comp == "..":
                node = node.parent or node
                continue
            child = node.children.get(comp)
            if child is not None:
                node = child
            elif i == len(components) - 1:
                return Missing(node, comp)
            else:
                raise FsError("ERR not found")
        return node

    def existing(self, path):
        target = self.resolve(path)
        if isinstance(target, Missing):
            raise FsError("ERR not found")
        return target

    # Commands. Each takes the argument tokens and returns the response.

    def pwd(self):
        return self.cwd.path()

    def cd(self, path):
        node = self.existing(path)
        if not node.is_dir:
            raise FsError("ERR not a directory")
        self.cwd = node
        return "OK"

    def mkdir(self, path):
        target = self.resolve(path)
        if not isinstance(target, Missing):
            raise FsError("ERR exists")
        target.parent.children[target.name] = Node(target.name, target.parent, True)
        return "OK"

    def write(self, path, text):
        target = self.resolve(path)
        if isinstance(target, Missing):
            target.parent.children[target.name] = Node(target.name, target.parent, False, text)
        elif target.is_dir:
            raise FsError("ERR is a directory")
        else:
            target.text = text
        return "OK"

    def cat(self, path):
        node = self.existing(path)
        if node.is_dir:
            raise FsError("ERR is a directory")
        return node.text

    def ls(self, path=None):
        node = self.cwd if path is None else self.existing(path)
        if not node.is_dir:
            return node.name
        if not node.children:
            return "-"
        return " ".join(
            name + "/" if node.children[name].is_dir else name
            for name in sorted(node.children)
        )

    def rm(self, path):
        node = self.existing(path)
        if self.cwd.is_within(node):
            raise FsError("ERR busy")
        if node.is_dir and node.children:
            raise FsError("ERR not empty")
        del node.parent.children[node.name]
        return "OK"

    def mv(self, src_path, dst_path):
        src = self.existing(src_path)
        if src.parent is None:
            raise FsError("ERR invalid")
        dst = self.resolve(dst_path)
        if isinstance(dst, Missing):
            parent, name = dst.parent, dst.name
        elif dst.is_dir:
            parent, name = dst, src.name
            if name in parent.children:
                raise FsError("ERR exists")
        else:
            raise FsError("ERR exists")
        if src.is_dir and parent.is_within(src):
            raise FsError("ERR invalid")
        del src.parent.children[src.name]
        src.name = name
        src.parent = parent
        parent.children[name] = src
        return "OK"

    def du(self, path=None):
        node = self.cwd if path is None else self.existing(path)
        if not node.is_dir:
            return f"{len(node.text)} 1 0"
        size, files, dirs = du_below(node)
        return f"{size} {files} {dirs}"

    def handle(self, line):
        if line.startswith("WRITE "):
            return self.handle_write(line)
        tokens = line.split(" ")
        command, args = tokens[0], tokens[1:]
        arity = {
            "PWD": (0, self.pwd), "CD": (1, self.cd), "MKDIR": (1, self.mkdir),
            "CAT": (1, self.cat), "RM": (1, self.rm), "MV": (2, self.mv),
        }
        optional = {"LS": self.ls, "DU": self.du}
        if command in arity:
            count, method = arity[command]
            if len(args) != count:
                return BAD
        elif command in optional:
            method = optional[command]
            if len(args) > 1:
                return BAD
        else:
            return BAD
        if not all(PATH_RE.fullmatch(a) for a in args):
            return BAD
        try:
            return method(*args)
        except FsError as e:
            return str(e)

    def handle_write(self, line):
        path, sep, text = line[len("WRITE "):].partition(" ")
        if not sep or not PATH_RE.fullmatch(path) or not TEXT_RE.fullmatch(text):
            return BAD
        try:
            return self.write(path, text)
        except FsError as e:
            return str(e)


def du_below(directory):
    size = files = dirs = 0
    for child in directory.children.values():
        if child.is_dir:
            s, f, d = du_below(child)
            size, files, dirs = size + s, files + f, dirs + d + 1
        else:
            size += len(child.text)
            files += 1
    return size, files, dirs


def main():
    if len(sys.argv) > 1:
        print("usage: vfs (takes no arguments)", file=sys.stderr)
        return 2

    fs = Vfs()
    for raw in sys.stdin.buffer:
        line = raw.decode("ascii", errors="replace")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        sys.stdout.write(fs.handle(line) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
