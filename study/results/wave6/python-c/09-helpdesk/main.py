"""helpdesk: persistent support tickets backed by an append-only journal."""
import os
import re
import sys
from dataclasses import dataclass

NAME = re.compile(r"[a-z0-9]{1,12}")
TICKET = re.compile(r"T([1-9][0-9]{0,8})")
TITLE = re.compile(r"[\x21-\x7e](?:[\x20-\x7e]{0,58}[\x21-\x7e])?")
JOURNAL = "tickets.log"


class CommandError(Exception):
    pass


BAD = CommandError("bad command")


@dataclass
class Ticket:
    number: int
    customer: str
    title: str
    agent: str | None = None
    closed: bool = False


def check(pattern: re.Pattern, token: str) -> re.Match:
    m = pattern.fullmatch(token)
    if not m:
        raise BAD
    return m


class Desk:
    def __init__(self) -> None:
        self.tickets: dict[int, Ticket] = {}

    @property
    def next_number(self) -> int:
        return len(self.tickets) + 1

    def ticket(self, token: str) -> Ticket:
        number = int(check(TICKET, token)[1])
        if number not in self.tickets:
            raise CommandError("no such ticket")
        return self.tickets[number]

    def execute(self, line: str) -> tuple[str, str | None]:
        """Run one command; return (response, journal record or None).

        The state is only changed when a record is returned; the caller must
        persist the record before answering.
        """
        command, _, rest = line.partition(" ")
        if command == "OPEN":
            customer, sep, title = rest.partition(" ")
            check(NAME, customer)
            if not sep:
                raise BAD
            check(TITLE, title)
            number = self.next_number
            self.tickets[number] = Ticket(number, customer, title)
            return f"T{number}", f"OPEN T{number} {customer} {title}"

        args = rest.split(" ") if rest else []
        if command == "ASSIGN" and len(args) == 2:
            check(TICKET, args[0])
            check(NAME, args[1])
            ticket = self.ticket(args[0])
            if ticket.closed:
                raise CommandError("closed")
            if ticket.agent == args[1]:
                return "UNCHANGED", None
            ticket.agent = args[1]
            return "OK", line
        if command == "CLOSE" and len(args) == 1:
            ticket = self.ticket(args[0])
            if ticket.closed:
                raise CommandError("closed")
            ticket.closed = True
            return "OK", line
        if command == "REOPEN" and len(args) == 1:
            ticket = self.ticket(args[0])
            if not ticket.closed:
                raise CommandError("not closed")
            ticket.closed = False
            return "OK", line
        if command == "SHOW" and len(args) == 1:
            t = self.ticket(args[0])
            state = "closed" if t.closed else "open"
            return f"T{t.number} {state} {t.customer} {t.agent or '-'} {t.title}", None
        if command == "QUEUE" and len(args) == 1:
            agent = None if args[0] == "-" else check(NAME, args[0])[0]
            queue = [f"T{t.number}" for t in self.tickets.values()
                     if not t.closed and t.agent == agent]
            return " ".join(queue) or "-", None
        raise BAD

    def replay(self, record: str) -> None:
        """Apply one journal record; raise ValueError if it is not valid."""
        if record.startswith("OPEN "):
            parts = record.split(" ", 2)
            if len(parts) != 3 or parts[1] != f"T{self.next_number}":
                raise ValueError(f"bad OPEN record: {record!r}")
            command = f"OPEN {parts[2]}"
        elif record.split(" ")[0] in ("ASSIGN", "CLOSE", "REOPEN"):
            command = record
        else:
            raise ValueError(f"not a record: {record!r}")
        try:
            response, written = self.execute(command)
        except CommandError as e:
            raise ValueError(f"record {record!r} fails: {e}")
        if written != record:
            raise ValueError(f"record {record!r} is not a change")


def load(path: str, desk: Desk) -> None:
    """Replay the journal into desk, truncating a torn final record."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return
    complete_end = data.rfind(b"\n") + 1
    try:
        text = data[:complete_end].decode("ascii")
    except UnicodeDecodeError:
        raise ValueError("journal is not ASCII")
    for record in text.split("\n")[:-1]:
        desk.replay(record)
    if complete_end != len(data):
        os.truncate(path, complete_end)


def prepare_dir(path: str) -> None:
    if not os.path.exists(path):
        os.mkdir(path)
    elif not os.path.isdir(path):
        raise OSError(f"{path} is not a directory")


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: helpdesk DIR", file=sys.stderr)
        return 2
    directory = argv[0]
    journal_path = os.path.join(directory, JOURNAL)
    desk = Desk()
    try:
        prepare_dir(directory)
        load(journal_path, desk)
    except (OSError, ValueError) as e:
        print(f"helpdesk: {e}", file=sys.stderr)
        return 1

    journal = None  # opened when the first record is written
    try:
        for raw in sys.stdin.buffer:
            line = raw.decode("ascii", errors="replace")
            if line.endswith("\n"):
                line = line[:-1]
            if line.endswith("\r"):
                line = line[:-1]
            try:
                response, record = desk.execute(line)
            except CommandError as e:
                response, record = f"ERR {e}", None
            if record is not None:
                if journal is None:
                    journal = open(journal_path, "ab")
                journal.write(record.encode("ascii") + b"\n")
                journal.flush()
            sys.stdout.write(response + "\n")
            sys.stdout.flush()
    finally:
        if journal is not None:
            journal.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
