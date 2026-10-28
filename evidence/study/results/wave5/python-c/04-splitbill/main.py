import re
import sys

NAME_RE = re.compile(r"[a-z][a-z0-9_]{0,15}")
AMOUNT_RE = re.compile(r"[0-9]{1,7}\.[0-9]{2}")
TOKEN_RE = re.compile(r"[^ \t]+")


class InputError(Exception):
    pass


def read_lines():
    text = sys.stdin.buffer.read().decode("utf-8")
    if not text:
        return []
    lines = text.split("\n")
    if text.endswith("\n"):
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def parse_name(token):
    if not NAME_RE.fullmatch(token):
        raise InputError(f"malformed name: {token!r}")
    return token


def parse_amount(token):
    if not AMOUNT_RE.fullmatch(token):
        raise InputError(f"malformed amount: {token!r}")
    whole, cents = token.split(".")
    amount = int(whole) * 100 + int(cents)
    if amount == 0:
        raise InputError("amount must not be zero")
    return amount


def apply_record(tokens, balances):
    kind = tokens[0]
    if kind == "expense":
        if len(tokens) < 4:
            raise InputError("expense needs a payer, an amount and participants")
        payer = parse_name(tokens[1])
        amount = parse_amount(tokens[2])
        participants = [parse_name(t) for t in tokens[3:]]
        if len(set(participants)) != len(participants):
            raise InputError("participant listed twice")
        q, r = divmod(amount, len(participants))
        balances[payer] = balances.get(payer, 0) + amount
        for i, person in enumerate(participants):
            share = q + 1 if i < r else q
            balances[person] = balances.get(person, 0) - share
    elif kind == "transfer":
        if len(tokens) != 4:
            raise InputError("transfer needs exactly: from to amount")
        giver = parse_name(tokens[1])
        receiver = parse_name(tokens[2])
        amount = parse_amount(tokens[3])
        if giver == receiver:
            raise InputError("transfer to oneself")
        balances[giver] = balances.get(giver, 0) + amount
        balances[receiver] = balances.get(receiver, 0) - amount
    else:
        raise InputError(f"unknown record type: {kind!r}")


def settle(balances):
    remaining = dict(balances)
    payments = []
    while True:
        debtor = min(remaining, key=lambda n: (remaining[n], n), default=None)
        if debtor is None or remaining[debtor] >= 0:
            return payments
        creditor = min(remaining, key=lambda n: (-remaining[n], n))
        x = min(-remaining[debtor], remaining[creditor])
        payments.append((debtor, creditor, x))
        remaining[debtor] += x
        remaining[creditor] -= x


def money(cents):
    return f"{cents // 100}.{cents % 100:02d}"


def signed_money(cents):
    if cents > 0:
        return "+" + money(cents)
    if cents < 0:
        return "-" + money(-cents)
    return money(0)


def main():
    if len(sys.argv) > 1:
        print("usage: splitbill  (reads records from stdin)", file=sys.stderr)
        sys.exit(2)

    balances = {}
    for lineno, line in enumerate(read_lines(), start=1):
        tokens = TOKEN_RE.findall(line)
        if not tokens or tokens[0].startswith("#"):
            continue
        try:
            apply_record(tokens, balances)
        except InputError as e:
            print(f"splitbill: line {lineno}: {e}", file=sys.stderr)
            sys.exit(1)

    out = [f"{name} {signed_money(balances[name])}\n" for name in sorted(balances)]
    out.append("--\n")
    out += [f"{d} pays {c} {money(x)}\n" for d, c, x in settle(balances)]
    sys.stdout.write("".join(out))


if __name__ == "__main__":
    main()
