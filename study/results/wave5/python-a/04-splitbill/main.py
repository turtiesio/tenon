import re
import sys

NAME_RE = re.compile(r"[a-z][a-z0-9_]{0,15}")
AMOUNT_RE = re.compile(r"([0-9]{1,7})\.([0-9]{2})")
TOKEN_RE = re.compile(r"[^ \t]+")


class InvalidInput(Exception):
    pass


def parse_name(token):
    if not NAME_RE.fullmatch(token):
        raise InvalidInput("bad name: " + token)
    return token


def parse_amount(token):
    m = AMOUNT_RE.fullmatch(token)
    if not m:
        raise InvalidInput("bad amount: " + token)
    cents = int(m.group(1)) * 100 + int(m.group(2))
    if cents == 0:
        raise InvalidInput("zero amount")
    return cents


def parse_line(tokens):
    """Return ('expense', payer, cents, participants) or ('transfer', src, dst, cents)."""
    kind = tokens[0]
    if kind == "expense":
        if len(tokens) < 4:
            raise InvalidInput("expense needs at least 4 tokens")
        payer = parse_name(tokens[1])
        cents = parse_amount(tokens[2])
        participants = [parse_name(t) for t in tokens[3:]]
        if len(set(participants)) != len(participants):
            raise InvalidInput("participant listed twice")
        return ("expense", payer, cents, participants)
    if kind == "transfer":
        if len(tokens) != 4:
            raise InvalidInput("transfer needs exactly 4 tokens")
        src = parse_name(tokens[1])
        dst = parse_name(tokens[2])
        cents = parse_amount(tokens[3])
        if src == dst:
            raise InvalidInput("transfer to self")
        return ("transfer", src, dst, cents)
    raise InvalidInput("unknown record: " + kind)


def money(cents):
    return "%d.%02d" % divmod(cents, 100)


def signed(cents):
    if cents > 0:
        return "+" + money(cents)
    if cents < 0:
        return "-" + money(-cents)
    return money(0)


def apply_record(balances, record):
    if record[0] == "expense":
        _, payer, cents, participants = record
        q, r = divmod(cents, len(participants))
        balances[payer] = balances.get(payer, 0) + cents
        for i, p in enumerate(participants):
            balances[p] = balances.get(p, 0) - (q + 1 if i < r else q)
    else:
        _, src, dst, cents = record
        balances[src] = balances.get(src, 0) + cents
        balances[dst] = balances.get(dst, 0) - cents


def settle(balances):
    work = dict(balances)
    payments = []
    while work:
        debtor = min(work, key=lambda n: (work[n], n))
        if work[debtor] >= 0:
            break
        creditor = min(work, key=lambda n: (-work[n], n))
        x = min(-work[debtor], work[creditor])
        payments.append((debtor, creditor, x))
        work[debtor] += x
        work[creditor] -= x
    return payments


def main():
    if len(sys.argv) > 1:
        print("splitbill: takes no arguments", file=sys.stderr)
        return 2

    text = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()

    balances = {}
    try:
        for line in lines:
            if line.endswith("\r"):
                line = line[:-1]
            tokens = TOKEN_RE.findall(line)
            if not tokens or tokens[0].startswith("#"):
                continue
            apply_record(balances, parse_line(tokens))
    except InvalidInput as e:
        print("splitbill: " + str(e), file=sys.stderr)
        return 1

    out = [name + " " + signed(balances[name]) for name in sorted(balances)]
    out.append("--")
    for debtor, creditor, x in settle(balances):
        out.append("%s pays %s %s" % (debtor, creditor, money(x)))
    sys.stdout.write("\n".join(out) + "\n")
    return 0


sys.exit(main())
