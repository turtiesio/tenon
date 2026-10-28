"""Private spec-only reference with canonical append-only WAL."""
import os
from pathlib import Path
import re
import sys
RID=r'[A-Za-z0-9_-]{1,32}'
ACCT=r'[a-z][a-z0-9_]{0,15}'
AMT=r'[1-9][0-9]{0,11}'

def parse(line):
    t=[x for x in line.strip(' ').split(' ') if x]
    if len(t)==3 and re.fullmatch(RID,t[0]) and t[1]=='OPEN' and re.fullmatch(ACCT,t[2]): return t
    if len(t)==4 and re.fullmatch(RID,t[0]) and t[1] in ('DEPOSIT','WITHDRAW') and re.fullmatch(ACCT,t[2]) and re.fullmatch(AMT,t[3]): return t
    if len(t)==5 and re.fullmatch(RID,t[0]) and t[1]=='TRANSFER' and all(re.fullmatch(ACCT,s) for s in t[2:4]) and re.fullmatch(AMT,t[4]): return t
    return None

def main():
    if len(sys.argv)!=2: return 2
    directory=Path(sys.argv[1])
    try:
        if not directory.exists(): directory.mkdir()
        if not directory.is_dir(): return 1
        path=directory/'ledger.log'
        raw=path.read_bytes() if path.exists() else b''
        if raw and not raw.endswith(b'\n'):
            raw=raw[:raw.rfind(b'\n')+1]
            with path.open('r+b') as f: f.truncate(len(raw))
    except OSError: return 1
    balances={}; seen=set()
    def apply(t):
        rid,op,acct=t[:3]
        if op=='OPEN': balances[acct]=0
        elif op=='DEPOSIT': balances[acct]+=int(t[3])
        elif op=='WITHDRAW': balances[acct]-=int(t[3])
        else: balances[acct]-=int(t[4]); balances[t[3]]+=int(t[4])
        seen.add(rid)
    for line in raw.split(b'\n')[:-1]:
        try: t=parse(line.decode('utf-8'))
        except UnicodeDecodeError: t=None
        if t is None: return 3
        apply(t)
    try: log=path.open('ab',buffering=0)
    except OSError: return 1
    with log:
        for rawline in sys.stdin.buffer:
            line=rawline.decode().removesuffix('\n').removesuffix('\r')
            tokens=[x for x in line.strip(' ').split(' ') if x]
            t=parse(line)
            if tokens==['ACCOUNTS']: answer=' '.join('%s=%d'%(a,balances[a]) for a in sorted(balances)) or '-'
            elif len(tokens)==2 and tokens[0]=='BALANCE' and re.fullmatch(ACCT,tokens[1]):
                acct=tokens[1]; answer='%s %d'%(acct,balances[acct]) if acct in balances else 'ERR no such account'
            elif t is None: answer='ERR bad command'
            elif t[0] in seen: answer='DUP '+t[0]
            else:
                rid,op,acct=t[:3]; reason=None
                if op=='OPEN':
                    if acct in balances: reason='exists'
                elif op=='DEPOSIT':
                    if acct not in balances: reason='no such account'
                    elif balances[acct]+int(t[3])>10**15: reason='limit'
                elif op=='WITHDRAW':
                    if acct not in balances: reason='no such account'
                    elif balances[acct]<int(t[3]): reason='insufficient'
                else:
                    other=t[3]; amount=int(t[4])
                    if acct==other: reason='same account'
                    elif acct not in balances or other not in balances: reason='no such account'
                    elif balances[acct]<amount: reason='insufficient'
                    elif balances[other]+amount>10**15: reason='limit'
                if reason: answer='ERR %s %s'%(rid,reason)
                else:
                    os.write(log.fileno(),(' '.join(t)+'\n').encode())
                    apply(t)
                    answer='OK '+rid
                    if op in ('DEPOSIT','WITHDRAW'): answer+=' '+str(balances[acct])
            print(answer,flush=True)
    return 0
sys.exit(main())
