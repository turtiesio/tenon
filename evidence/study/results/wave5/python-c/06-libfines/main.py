import re
import sys
from dataclasses import dataclass, field

DAY_RE = re.compile(r"[0-9]{1,6}")
BOOK_ID_RE = re.compile(r"[A-Za-z0-9-]{1,12}")
MEMBER_RE = re.compile(r"[a-z][a-z0-9]{0,11}")


class InputError(Exception):
    pass


@dataclass
class Book:
    title: str
    rate: int
    cap: int


@dataclass
class Member:
    loans: int = 0
    late: int = 0
    fine: int = 0
    details: list = field(default_factory=list)


def records(path):
    """Yield (line number, fields) for every non-ignored line of the file."""
    try:
        with open(path, "rb") as f:
            text = f.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise InputError(f"cannot read {path}: {e}")
    lines = text.split("\n")
    if text.endswith("\n") or not text:
        lines.pop()
    for lineno, line in enumerate(lines, start=1):
        if line.endswith("\r"):
            line = line[:-1]
        if line == "" or line.startswith("#"):
            continue
        yield lineno, line.split("|")


def check(ok, path, lineno, message):
    if not ok:
        raise InputError(f"{path}:{lineno}: {message}")


def load_books(path):
    books = {}
    for lineno, fields in records(path):
        check(len(fields) == 4, path, lineno, "expected 4 fields")
        book_id, title, rate, cap = fields
        check(BOOK_ID_RE.fullmatch(book_id), path, lineno, f"bad book id {book_id!r}")
        check(title != "", path, lineno, "empty title")
        check(DAY_RE.fullmatch(rate), path, lineno, f"bad rate {rate!r}")
        check(DAY_RE.fullmatch(cap), path, lineno, f"bad cap {cap!r}")
        check(book_id not in books, path, lineno, f"duplicate book id {book_id!r}")
        books[book_id] = Book(title, int(rate), int(cap))
    return books


def load_loans(path):
    loans = []
    for lineno, fields in records(path):
        check(len(fields) == 5, path, lineno, "expected 5 fields")
        member, book_id, out, due, returned = fields
        check(MEMBER_RE.fullmatch(member), path, lineno, f"bad member {member!r}")
        check(BOOK_ID_RE.fullmatch(book_id), path, lineno, f"bad book id {book_id!r}")
        check(DAY_RE.fullmatch(out), path, lineno, f"bad out day {out!r}")
        check(DAY_RE.fullmatch(due), path, lineno, f"bad due day {due!r}")
        check(int(due) >= int(out), path, lineno, "due is before out")
        if returned == "-":
            returned_day = None
        else:
            check(DAY_RE.fullmatch(returned), path, lineno, f"bad returned day {returned!r}")
            returned_day = int(returned)
            check(returned_day >= int(out), path, lineno, "returned is before out")
        loans.append((member, book_id, int(due), returned_day))
    return loans


def money(cents):
    return f"{cents // 100}.{cents % 100:02d}"


def main():
    args = sys.argv[1:]
    if len(args) != 3 or not DAY_RE.fullmatch(args[2]):
        print("usage: libfines BOOKS LOANS TODAY", file=sys.stderr)
        sys.exit(2)
    books_path, loans_path, today = args[0], args[1], int(args[2])

    try:
        books = load_books(books_path)
        loans = load_loans(loans_path)
    except InputError as e:
        print(f"libfines: {e}", file=sys.stderr)
        sys.exit(1)

    members = {}
    skipped = 0
    for member_name, book_id, due, returned in loans:
        book = books.get(book_id)
        if book is None:
            skipped += 1
            continue
        end = today if returned is None else returned
        days = max(0, end - due)
        fine = min(days * book.rate, book.cap)
        member = members.setdefault(member_name, Member())
        member.loans += 1
        member.fine += fine
        if days > 0:
            member.late += 1
            member.details.append(f"  {book_id} {book.title} days={days} fine={money(fine)}\n")

    out = []
    for name in sorted(members, key=lambda n: (-members[n].fine, n)):
        m = members[name]
        out.append(f"{name} loans={m.loans} late={m.late} fine={money(m.fine)}\n")
        out.extend(m.details)
    total = sum(m.fine for m in members.values())
    out.append(f"total={money(total)} skipped={skipped}\n")
    sys.stdout.buffer.write("".join(out).encode("utf-8"))


if __name__ == "__main__":
    main()
