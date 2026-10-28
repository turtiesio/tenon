import os
import re
import sys

NAME_RE = re.compile(r"[a-z0-9]{1,12}")
TICKET_RE = re.compile(r"T([1-9][0-9]{0,8})")
TITLE_RE = re.compile(r"[ -~]{1,60}")


class JournalError(Exception):
    pass


class Ticket:
    def __init__(self, customer, title):
        self.customer = customer
        self.title = title
        self.agent = None
        self.open = True


class Tickets:
    """The ticket state. handle() applies one command line and returns
    (response, record); record is the journal line to write, or None."""

    def __init__(self):
        self.tickets = {}
        self.next_number = 1
        # agent (None for unassigned) -> numbers of open tickets
        self.open_by_agent = {}

    def _index(self, number, ticket):
        self.open_by_agent.setdefault(ticket.agent, set()).add(number)

    def _unindex(self, number, ticket):
        self.open_by_agent[ticket.agent].discard(number)

    def handle(self, line):
        tokens = line.split(" ")
        cmd, args = tokens[0], tokens[1:]
        if cmd == "OPEN":
            return self.open_ticket(line)
        if cmd in ("ASSIGN", "CLOSE", "REOPEN", "SHOW") and args:
            m = TICKET_RE.fullmatch(args[0])
            if m:
                number = int(m.group(1))
                if cmd == "ASSIGN" and len(args) == 2 and NAME_RE.fullmatch(args[1]):
                    return self.assign(number, args[1], line)
                if cmd in ("CLOSE", "REOPEN", "SHOW") and len(args) == 1:
                    return getattr(self, cmd.lower())(number, line)
        elif cmd == "QUEUE" and len(args) == 1:
            if args[0] == "-":
                return self.queue(None)
            if NAME_RE.fullmatch(args[0]):
                return self.queue(args[0])
        return "ERR bad command", None

    def open_ticket(self, line):
        _, _, rest = line.partition(" ")
        customer, sep, title = rest.partition(" ")
        if (not sep or not NAME_RE.fullmatch(customer) or not TITLE_RE.fullmatch(title)
                or title.startswith(" ") or title.endswith(" ")):
            return "ERR bad command", None
        number = self.next_number
        self.next_number += 1
        ticket = Ticket(customer, title)
        self.tickets[number] = ticket
        self._index(number, ticket)
        return f"T{number}", f"OPEN T{number} {customer} {title}"

    def assign(self, number, agent, line):
        ticket = self.tickets.get(number)
        if ticket is None:
            return "ERR no such ticket", None
        if not ticket.open:
            return "ERR closed", None
        if ticket.agent == agent:
            return "UNCHANGED", None
        self._unindex(number, ticket)
        ticket.agent = agent
        self._index(number, ticket)
        return "OK", line

    def close(self, number, line):
        ticket = self.tickets.get(number)
        if ticket is None:
            return "ERR no such ticket", None
        if not ticket.open:
            return "ERR closed", None
        self._unindex(number, ticket)
        ticket.open = False
        return "OK", line

    def reopen(self, number, line):
        ticket = self.tickets.get(number)
        if ticket is None:
            return "ERR no such ticket", None
        if ticket.open:
            return "ERR not closed", None
        ticket.open = True
        self._index(number, ticket)
        return "OK", line

    def show(self, number, line):
        ticket = self.tickets.get(number)
        if ticket is None:
            return "ERR no such ticket", None
        state = "open" if ticket.open else "closed"
        agent = ticket.agent or "-"
        return f"T{number} {state} {ticket.customer} {agent} {ticket.title}", None

    def queue(self, agent):
        numbers = sorted(self.open_by_agent.get(agent, ()))
        return (" ".join(f"T{n}" for n in numbers) or "-"), None

    def replay(self, record):
        """Apply a journal record; raise JournalError unless it is valid here."""
        if record.startswith("OPEN "):
            parts = record.split(" ", 3)
            m = TICKET_RE.fullmatch(parts[1]) if len(parts) == 4 else None
            if not m:
                raise JournalError(f"bad record: {record!r}")
            response, _ = self.open_ticket(f"OPEN {parts[2]} {parts[3]}")
            if response != f"T{m.group(1)}":
                raise JournalError(f"bad record: {record!r}")
        else:
            if record.split(" ", 1)[0] not in ("ASSIGN", "CLOSE", "REOPEN"):
                raise JournalError(f"bad record: {record!r}")
            response, _ = self.handle(record)
            if response != "OK":
                raise JournalError(f"bad record: {record!r}")


def load_journal(path, state):
    """Replay the journal into state; return the length of the valid prefix
    of the file if a torn record must be cut off, else None."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return None
    except OSError as e:
        raise JournalError(f"{path}: {e}")
    end = data.rfind(b"\n") + 1
    for raw in data[:end].split(b"\n")[:-1]:
        state.replay(raw.decode("latin-1"))
    return end if end < len(data) else None


def main(argv):
    if len(argv) != 1:
        print("usage: helpdesk DIR", file=sys.stderr)
        return 2
    directory = argv[0]
    try:
        os.mkdir(directory)
    except FileExistsError:
        if not os.path.isdir(directory):
            print(f"helpdesk: {directory}: not a directory", file=sys.stderr)
            return 1
    except OSError as e:
        print(f"helpdesk: {directory}: {e.strerror}", file=sys.stderr)
        return 1

    path = os.path.join(directory, "tickets.log")
    state = Tickets()
    try:
        cut = load_journal(path, state)
        if cut is not None:
            os.truncate(path, cut)
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    except (JournalError, OSError) as e:
        print(f"helpdesk: journal unusable: {e}", file=sys.stderr)
        return 1

    for raw in sys.stdin.buffer:
        line = raw.decode("latin-1")
        if line.endswith("\n"):
            line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
        response, record = state.handle(line)
        if record is not None:
            os.write(fd, (record + "\n").encode("ascii"))
        sys.stdout.write(response + "\n")
        sys.stdout.flush()
    os.close(fd)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
