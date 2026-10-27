import os
import re
import sys

NAME_RE = re.compile(r"[a-z0-9]{1,12}")


class Poll:
    def __init__(self, options):
        self.options = options
        self.votes = {}  # voter -> option
        self.closed = False

    def result(self, name):
        counts = {o: 0 for o in self.options}
        for option in self.votes.values():
            counts[option] += 1
        parts = ["%s %s" % (name, "closed" if self.closed else "open")]
        parts.extend("%s=%d" % (o, counts[o]) for o in self.options)
        return " ".join(parts)


class Service:
    def __init__(self):
        self.polls = {}

    def execute(self, line):
        """Apply a command. Returns (response, changed)."""
        tokens = line.split(" ")
        cmd, args = tokens[0], tokens[1:]
        if not all(NAME_RE.fullmatch(a) for a in args):
            return "ERR bad command", False
        if cmd == "CREATE":
            if not 3 <= len(args) <= 10 or len(set(args[1:])) != len(args) - 1:
                return "ERR bad command", False
            return self.create(args[0], args[1:])
        if cmd == "VOTE" and len(args) == 3:
            return self.vote(*args)
        if cmd == "CLOSE" and len(args) == 1:
            return self.close(args[0])
        if cmd == "RESULT" and len(args) == 1:
            return self.result(args[0])
        return "ERR bad command", False

    def create(self, name, options):
        if name in self.polls:
            return "ERR poll exists", False
        self.polls[name] = Poll(options)
        return "OK", True

    def open_poll(self, name):
        """Return (poll, error) for a poll that must exist and be open."""
        poll = self.polls.get(name)
        if poll is None:
            return None, "ERR no such poll"
        if poll.closed:
            return None, "ERR poll closed"
        return poll, None

    def vote(self, name, voter, option):
        poll, error = self.open_poll(name)
        if error:
            return error, False
        if option not in poll.options:
            return "ERR no such option", False
        previous = poll.votes.get(voter)
        if previous == option:
            return "UNCHANGED", False
        poll.votes[voter] = option
        return ("VOTED" if previous is None else "CHANGED"), True

    def close(self, name):
        poll, error = self.open_poll(name)
        if error:
            return error, False
        poll.closed = True
        return "OK", True

    def result(self, name):
        poll = self.polls.get(name)
        if poll is None:
            return "ERR no such poll", False
        return poll.result(name), False


class Journal:
    def __init__(self, path):
        self.path = path
        self.fd = None

    def load(self, service):
        """Replay the journal into service. Returns the length of the valid prefix, or raises ValueError."""
        try:
            with open(self.path, "rb") as f:
                data = f.read()
        except FileNotFoundError:
            return None
        end = data.rfind(b"\n") + 1
        try:
            text = data[:end].decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("journal is not valid UTF-8")
        if text:
            for number, line in enumerate(text[:-1].split("\n"), 1):
                response, changed = service.execute(line)
                if not changed:
                    raise ValueError("journal line %d is not valid: %r" % (number, line))
        return end if end != len(data) else None

    def truncate(self, length):
        with open(self.path, "r+b") as f:
            f.truncate(length)

    def append(self, line):
        if self.fd is None:
            self.fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        data = (line + "\n").encode("utf-8")
        while data:
            written = os.write(self.fd, data)
            data = data[written:]


def prepare_directory(path):
    if not os.path.exists(path):
        os.mkdir(path)
    if not os.path.isdir(path):
        raise OSError("not a directory: " + path)


def main():
    if len(sys.argv) != 2:
        print("usage: polls DIR", file=sys.stderr)
        return 2
    directory = sys.argv[1]
    try:
        prepare_directory(directory)
    except OSError as e:
        print("polls: %s" % e, file=sys.stderr)
        return 1

    service = Service()
    journal = Journal(os.path.join(directory, "polls.log"))
    try:
        torn_at = journal.load(service)
        if torn_at is not None:
            journal.truncate(torn_at)
    except (ValueError, OSError) as e:
        print("polls: %s" % e, file=sys.stderr)
        return 1

    for raw in sys.stdin.buffer:
        line = raw.decode("utf-8", errors="replace")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        response, changed = service.execute(line)
        if changed:
            journal.append(line)
        sys.stdout.write(response + "\n")
        sys.stdout.flush()
    return 0


sys.exit(main())
