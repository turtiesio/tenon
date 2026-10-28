import re
import sys


class FsError(Exception):
    pass


class Node:
    def __init__(self, name='', parent=None, text=None):
        self.name = name
        self.parent = parent
        self.text = text
        self.children = {} if text is None else None

    @property
    def is_dir(self):
        return self.children is not None


def valid_path(path):
    if not 1 <= len(path) <= 200:
        return False
    if path == '/':
        return True
    return all(re.fullmatch(r'[A-Za-z0-9._-]{1,32}', part) for part in path.removeprefix('/').split('/'))


def ancestor(parent, node):
    while node is not None:
        if node is parent:
            return True
        node = node.parent
    return False


class FileSystem:
    def __init__(self):
        self.root = Node()
        self.cwd = self.root

    def resolve(self, path):
        node = self.root if path.startswith('/') else self.cwd
        if path == '/':
            return node, None, None
        parts = path.removeprefix('/').split('/')
        for index, part in enumerate(parts):
            if not node.is_dir:
                raise FsError('not a directory')
            if part == '.':
                continue
            if part == '..':
                node = node.parent or node
            elif part in node.children:
                node = node.children[part]
            elif index == len(parts)-1:
                return None, node, part
            else:
                raise FsError('not found')
        return node, node.parent, node.name

    def command(self, line):
        if line.startswith('WRITE '):
            parts = line.split(' ', 2)
            if len(parts) != 3 or not valid_path(parts[1]) or not re.fullmatch(r'[\x20-\x7e]{1,100}', parts[2]):
                raise FsError('bad command')
            action, path, text = parts
            node, parent, name = self.resolve(path)
            if node is not None:
                if node.is_dir:
                    raise FsError('is a directory')
                node.text = text
            else:
                parent.children[name] = Node(name, parent, text)
            return 'OK'
        parts = line.split(' ')
        action, paths = parts[0], parts[1:]
        counts = {'PWD': (0,), 'CD': (1,), 'MKDIR': (1,), 'CAT': (1,), 'LS': (0, 1), 'RM': (1,), 'MV': (2,), 'DU': (0, 1)}
        if action not in counts or len(paths) not in counts[action] or not all(valid_path(path) for path in paths):
            raise FsError('bad command')
        if action == 'PWD':
            names = []
            node = self.cwd
            while node.parent is not None:
                names.append(node.name)
                node = node.parent
            return '/' + '/'.join(reversed(names))
        node, parent, name = self.resolve(paths[0]) if paths else (self.cwd, self.cwd.parent, self.cwd.name)
        if action == 'MKDIR':
            if node is not None:
                raise FsError('exists')
            parent.children[name] = Node(name, parent)
            return 'OK'
        if node is None:
            raise FsError('not found')
        if action == 'CD':
            if not node.is_dir:
                raise FsError('not a directory')
            self.cwd = node
            return 'OK'
        if action == 'CAT':
            if node.is_dir:
                raise FsError('is a directory')
            return node.text
        if action == 'LS':
            if not node.is_dir:
                return node.name
            return ' '.join(child.name + ('/' if child.is_dir else '') for _, child in sorted(node.children.items())) or '-'
        if action == 'RM':
            if ancestor(node, self.cwd):
                raise FsError('busy')
            if node.is_dir and node.children:
                raise FsError('not empty')
            del parent.children[name]
            return 'OK'
        if action == 'MV':
            if node is self.root:
                raise FsError('invalid')
            destination, target_parent, target_name = self.resolve(paths[1])
            if destination is not None:
                if not destination.is_dir or node.name in destination.children:
                    raise FsError('exists')
                target_parent, target_name = destination, node.name
            if node.is_dir and ancestor(node, target_parent):
                raise FsError('invalid')
            del node.parent.children[node.name]
            node.parent, node.name = target_parent, target_name
            target_parent.children[target_name] = node
            return 'OK'
        if action == 'DU':
            size, files, dirs = 0, 0, 0
            stack = [node]
            while stack:
                current = stack.pop()
                if current.is_dir:
                    dirs += 1
                    stack.extend(current.children.values())
                else:
                    files += 1
                    size += len(current.text)
            return f'{size} {files} {dirs-int(node.is_dir)}'


def main():
    if len(sys.argv) != 1:
        print('no arguments allowed', file=sys.stderr)
        return 2
    fs = FileSystem()
    for line in sys.stdin.buffer:
        line = line.removesuffix(b'\n').removesuffix(b'\r').decode('ascii')
        try:
            response = fs.command(line)
        except FsError as exc:
            response = f'ERR {exc}'
        print(response, flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
