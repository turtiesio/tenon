import os
import re
import sys
from dataclasses import dataclass, field

NAME_RE = re.compile(r"[a-z0-9]{1,12}")
JOURNAL = "polls.log"


@dataclass
class Poll:
    options: list
    closed: bool = False
    votes: dict = field(default_factory=dict)  # voter -> option


def parse(line):
    """Return the tokens of a well-formed command, or None."""
    tokens = line.split(" ")
    if not all(NAME_RE.fullmatch(t) for t in tokens[1:]):
        return None
    command, args = tokens[0], tokens[1:]
    if command == "CREATE":
        options = args[1:]
        if 2 <= len(options) <= 9 and len(set(options)) == len(options):
            return tokens
    elif command == "VOTE" and len(args) == 3:
        return tokens
    elif command in ("CLOSE", "RESULT") and len(args) == 1:
        return tokens
    return None


class Polls:
    def __init__(self):
        self.polls = {}

    def execute(self, line):
        """Run one command line. Return (response, changes_state)."""
        tokens = parse(line)
        if tokens is None:
            return "ERR bad command", False
        command, name, args = tokens[0], tokens[1], tokens[2:]
        poll = self.polls.get(name)

        if command == "CREATE":
            if poll is not None:
                return "ERR poll exists", False
            return "OK", True
        if poll is None:
            return "ERR no such poll", False
        if command == "RESULT":
            state = "closed" if poll.closed else "open"
            counts = {option: 0 for option in poll.options}
            for option in poll.votes.values():
                counts[option] += 1
            return " ".join([name, state] + [f"{o}={n}" for o, n in counts.items()]), False
        if poll.closed:
            return "ERR poll closed", False
        if command == "CLOSE":
            return "OK", True
        voter, option = args
        if option not in poll.options:
            return "ERR no such option", False
        previous = poll.votes.get(voter)
        if previous == option:
            return "UNCHANGED", False
        return ("VOTED" if previous is None else "CHANGED"), True

    def apply(self, line):
        """Apply a command already known (via execute) to change the state."""
        tokens = line.split(" ")
        command, name = tokens[0], tokens[1]
        if command == "CREATE":
            self.polls[name] = Poll(tokens[2:])
        elif command == "CLOSE":
            self.polls[name].closed = True
        else:
            voter, option = tokens[2:]
            self.polls[name].votes[voter] = option


class JournalError(Exception):
    pass


def load_journal(path, state):
    """Replay the journal into state; return the length of its valid prefix."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return None
    except OSError as e:
        raise JournalError(f"cannot read {path}: {e}")
    complete = data[: data.rfind(b"\n") + 1]
    try:
        text = complete.decode("utf-8")
    except UnicodeDecodeError:
        raise JournalError(f"{path} is not valid UTF-8")
    for lineno, line in enumerate(text.split("\n")[:-1], start=1):
        response, changes = state.execute(line)
        if not changes:
            raise JournalError(f"{path}:{lineno}: invalid record ({response})")
        state.apply(line)
    return len(complete) if len(complete) != len(data) else None


def open_data_dir(path):
    try:
        os.mkdir(path)
    except FileExistsError:
        if not os.path.isdir(path):
            raise OSError(f"{path} exists but is not a directory")


def main():
    if len(sys.argv) != 2:
        print("usage: polls DIR", file=sys.stderr)
        sys.exit(2)
    data_dir = sys.argv[1]
    journal_path = os.path.join(data_dir, JOURNAL)

    state = Polls()
    try:
        open_data_dir(data_dir)
        torn_at = load_journal(journal_path, state)
        if torn_at is not None:
            os.truncate(journal_path, torn_at)
        journal = open(journal_path, "ab", buffering=0)
    except (OSError, JournalError) as e:
        print(f"polls: {e}", file=sys.stderr)
        sys.exit(1)

    with journal:
        for raw in sys.stdin.buffer:
            line = raw.decode("utf-8", errors="replace")
            if line.endswith("\n"):
                line = line[:-1]
            if line.endswith("\r"):
                line = line[:-1]
            response, changes = state.execute(line)
            if changes:
                journal.write((line + "\n").encode("utf-8"))
                state.apply(line)
            sys.stdout.write(response + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
