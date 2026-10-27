import re
import sys

TODAY_RE = re.compile(r"[0-9]{1,6}")
BOOK_ID_RE = re.compile(r"[A-Za-z0-9-]{1,12}")
NUMBER_RE = re.compile(r"[0-9]{1,6}")
MEMBER_RE = re.compile(r"[a-z][a-z0-9]{0,11}")


class InvalidFile(Exception):
    pass


def read_records(path, nfields):
    """Return the list of field lists of a data file; raise on read or format errors."""
    try:
        with open(path, "rb") as f:
            text = f.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise InvalidFile("cannot read %s: %s" % (path, e))
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    records = []
    for number, line in enumerate(lines, 1):
        if line.endswith("\r"):
            line = line[:-1]
        if not line or line.startswith("#"):
            continue
        fields = line.split("|")
        if len(fields) != nfields:
            raise InvalidFile("%s:%d: expected %d fields" % (path, number, nfields))
        records.append((number, fields))
    return records


def require(pattern, value, path, number, what):
    if not pattern.fullmatch(value):
        raise InvalidFile("%s:%d: bad %s: %r" % (path, number, what, value))


def load_books(path):
    books = {}
    for number, (book_id, title, rate, cap) in read_records(path, 4):
        require(BOOK_ID_RE, book_id, path, number, "book id")
        if not title:
            raise InvalidFile("%s:%d: empty title" % (path, number))
        require(NUMBER_RE, rate, path, number, "rate")
        require(NUMBER_RE, cap, path, number, "cap")
        if book_id in books:
            raise InvalidFile("%s:%d: duplicate book id %s" % (path, number, book_id))
        books[book_id] = (title, int(rate), int(cap))
    return books


def load_loans(path):
    loans = []
    for number, (member, book_id, out, due, returned) in read_records(path, 5):
        require(MEMBER_RE, member, path, number, "member")
        require(BOOK_ID_RE, book_id, path, number, "book id")
        require(NUMBER_RE, out, path, number, "out day")
        require(NUMBER_RE, due, path, number, "due day")
        out, due = int(out), int(due)
        if due < out:
            raise InvalidFile("%s:%d: due before out" % (path, number))
        if returned == "-":
            ret = None
        else:
            require(NUMBER_RE, returned, path, number, "returned day")
            ret = int(returned)
            if ret < out:
                raise InvalidFile("%s:%d: returned before out" % (path, number))
        loans.append((member, book_id, due, ret))
    return loans


def money(cents):
    return "%d.%02d" % divmod(cents, 100)


def main():
    args = sys.argv[1:]
    if len(args) != 3 or not TODAY_RE.fullmatch(args[2]):
        print("usage: libfines BOOKS LOANS TODAY", file=sys.stderr)
        return 2
    today = int(args[2])

    try:
        books = load_books(args[0])
        loans = load_loans(args[1])
    except InvalidFile as e:
        print("libfines: " + str(e), file=sys.stderr)
        return 1

    skipped = 0
    # member -> [loan count, late count, fine total, late details]
    members = {}
    for member, book_id, due, returned in loans:
        book = books.get(book_id)
        if book is None:
            skipped += 1
            continue
        title, rate, cap = book
        end = today if returned is None else returned
        days = max(0, end - due)
        fine = min(days * rate, cap)
        entry = members.setdefault(member, [0, 0, 0, []])
        entry[0] += 1
        entry[2] += fine
        if days > 0:
            entry[1] += 1
            entry[3].append("  %s %s days=%d fine=%s" % (book_id, title, days, money(fine)))

    out = []
    for member in sorted(members, key=lambda m: (-members[m][2], m)):
        count, late, fine, details = members[member]
        out.append("%s loans=%d late=%d fine=%s" % (member, count, late, money(fine)))
        out.extend(details)
    total = sum(entry[2] for entry in members.values())
    out.append("total=%s skipped=%d" % (money(total), skipped))
    sys.stdout.write("\n".join(out) + "\n")
    return 0


sys.exit(main())
