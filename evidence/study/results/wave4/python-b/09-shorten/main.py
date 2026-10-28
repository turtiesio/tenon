import os
from pathlib import Path
import re
import sys

URL = r'[!-~]{1,200}'
CODE = r'[0-9a-z]{1,8}'
RECORD = re.compile(rf'([1-9][0-9]{{0,8}}) (?:P ({URL})|([HD]) ({CODE}))\n')


def base36(number):
    digits = '0123456789abcdefghijklmnopqrstuvwxyz'
    result = ''
    while number:
        number, digit = divmod(number, 36)
        result = digits[digit] + result
    return result or '0'


class Shortener:
    def __init__(self, journal):
        self.journal = journal
        self.links = {}
        self.next_id = 1
        self.records = 0
        valid_end = 0
        journal.seek(0)
        for raw in journal:
            try:
                line = raw.decode('ascii')
            except UnicodeDecodeError:
                break
            match = RECORD.fullmatch(line)
            if match is None or int(match[1]) != self.records + 1:
                break
            _, url, kind, code = match.groups()
            if kind and code not in self.links:
                break
            self.apply('P' if url is not None else kind, url if url is not None else code)
            self.records += 1
            valid_end += len(raw)
        journal.seek(valid_end)
        journal.truncate()
        journal.flush()

    def apply(self, kind, value):
        if kind == 'P':
            self.links[base36(self.next_id)] = [value, 0]
            self.next_id += 1
        elif kind == 'H':
            self.links[value][1] += 1
        else:
            del self.links[value]

    def change(self, kind, value):
        record = f'{self.records + 1} {kind} {value}\n'.encode('ascii')
        self.journal.write(record)
        self.journal.flush()
        self.apply(kind, value)
        self.records += 1

    def command(self, line):
        if line == 'INFO':
            return f'links={len(self.links)} next={base36(self.next_id)} records={self.records}'
        match = re.fullmatch(rf'PUT ({URL})', line)
        if match:
            code = base36(self.next_id)
            self.change('P', match[1])
            return 'CODE ' + code
        match = re.fullmatch(rf'(GET|HITS|DEL) ({CODE})', line)
        if match is None:
            return 'ERR bad command'
        kind, code = match.groups()
        if code not in self.links:
            return 'ERR not found'
        if kind == 'HITS':
            return f'HITS {self.links[code][1]}'
        if kind == 'GET':
            url = self.links[code][0]
            self.change('H', code)
            return 'URL ' + url
        self.change('D', code)
        return 'OK'


def main():
    if len(sys.argv) != 2:
        print('Expected a directory', file=sys.stderr)
        return 2
    directory = Path(sys.argv[1])
    try:
        if not directory.exists():
            directory.mkdir()
        if not directory.is_dir():
            raise OSError('Not a directory')
        journal = open(directory / 'journal', 'a+b')
        service = Shortener(journal)
    except OSError as error:
        print(error, file=sys.stderr)
        return 1
    try:
        with journal:
            for raw in sys.stdin.buffer:
                line = raw.decode('utf-8', errors='replace').removesuffix('\n').removesuffix('\r')
                print(service.command(line), flush=True)
    except OSError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
