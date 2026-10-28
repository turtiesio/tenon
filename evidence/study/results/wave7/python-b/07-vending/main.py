import re
import sys

DENOMINATIONS = (5, 10, 20, 50, 100, 200)


def coin_list(coins):
    return ' '.join(f'{coin}x{coins[coin]}' for coin in reversed(DENOMINATIONS) if coins[coin]) or '-'


class Machine:
    def __init__(self):
        self.tubes = dict.fromkeys(DENOMINATIONS, 0)
        self.escrow = dict.fromkeys(DENOMINATIONS, 0)
        self.slots = {}

    def credit(self):
        return sum(coin*count for coin, count in self.escrow.items())

    def command(self, line):
        match = re.fullmatch(r'LOAD ([A-F][1-9]) ([a-z]{1,12}) ([1-9][0-9]{0,3}) (0|[1-9][0-9]?)', line)
        if match:
            slot, name, price, count = match.groups()
            if int(price) % 5:
                return 'ERR bad command'
            self.slots[slot] = [name, int(price), int(count)]
            return 'OK'
        match = re.fullmatch(r'FILL (5|10|20|50|100|200) ([1-9][0-9]{0,2})', line)
        if match:
            coin, count = map(int, match.groups())
            self.tubes[coin] += count
            return 'OK'
        match = re.fullmatch(r'INSERT ([1-9][0-9]{0,5})', line)
        if match:
            coin = int(match[1])
            if coin not in self.escrow:
                return f'REJECT {coin}'
            self.escrow[coin] += 1
            return f'CREDIT {self.credit()}'
        if line == 'COINS':
            return ' '.join(f'{coin}x{self.tubes[coin]}' for coin in DENOMINATIONS)
        if line == 'REFUND':
            response = f'REFUND {self.credit()} {coin_list(self.escrow)}'
            self.escrow = dict.fromkeys(DENOMINATIONS, 0)
            return response
        match = re.fullmatch(r'(STOCK|SELECT) ([A-F][1-9])', line)
        if not match:
            return 'ERR bad command'
        action, slot = match.groups()
        if slot not in self.slots:
            return 'ERR no such slot'
        name, price, count = self.slots[slot]
        if action == 'STOCK':
            return f'{slot} {name} {price} {count}'
        if count == 0:
            return 'ERR sold out'
        credit = self.credit()
        if credit < price:
            return f'ERR need {price-credit}'
        available = {coin: self.tubes[coin] + self.escrow[coin] for coin in DENOMINATIONS}
        owed = credit-price
        change = dict.fromkeys(DENOMINATIONS, 0)
        for coin in reversed(DENOMINATIONS):
            change[coin] = min(available[coin], owed // coin)
            owed -= coin*change[coin]
        if owed:
            return 'ERR no change'
        self.tubes = {coin: available[coin]-change[coin] for coin in DENOMINATIONS}
        self.escrow = dict.fromkeys(DENOMINATIONS, 0)
        self.slots[slot][2] -= 1
        return f'VEND {name} {credit-price} {coin_list(change)}'


def main():
    if len(sys.argv) != 1:
        print('no arguments allowed', file=sys.stderr)
        return 2
    machine = Machine()
    for line in sys.stdin.buffer:
        line = line.removesuffix(b'\n').removesuffix(b'\r').decode('ascii')
        print(machine.command(line), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
