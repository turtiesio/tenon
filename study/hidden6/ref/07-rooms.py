import re
import sys
from common import fail, emit
if len(sys.argv)!=1: fail(2)
name=r'[a-z0-9]{1,12}'; number=r'[1-9][0-9]{0,2}'; time=r'(?:[01][0-9]:[0-5][0-9]|2[0-3]:[0-5][0-9]|24:00)'; bid=r'B[1-9][0-9]{0,8}'
forms=[r'ROOM ('+name+r') ('+number+r')',r'BOOK ('+name+r') ('+time+r') ('+time+r') ('+name+r')',r'CANCEL ('+bid+r')',r'SCHEDULE ('+name+r')',r'FIND ('+number+r') ([1-9][0-9]{0,3})']
rooms={}; bookings={}; nxt=1
def mins(t): return int(t[:2])*60+int(t[3:])
def clock(n): return f'{n//60:02d}:{n%60:02d}'
def overlap(s,e,b): return s<b[2] and b[1]<e
for raw in sys.stdin.buffer:
    line=raw.decode('ascii').removesuffix('\n').removesuffix('\r')
    m=next((m for p in forms if (m:=re.fullmatch(p,line))),None)
    response='ERR bad command'
    if m:
        a=m.groups(); cmd=line.split(' ')[0]
        if cmd=='ROOM':
            if a[0] in rooms: response='ERR room exists'
            else: rooms[a[0]]=int(a[1]); response='OK'
        elif cmd=='BOOK':
            r,s,e,who=a; s,e=mins(s),mins(e)
            if s>=e: response='ERR bad time'
            elif r not in rooms: response='ERR no such room'
            else:
                hits=sorted((b[1],i) for i,b in bookings.items() if b[0]==r and overlap(s,e,b))
                if hits: response='ERR conflict B'+str(hits[0][1])
                else: bookings[nxt]=(r,s,e,who); response='OK B'+str(nxt); nxt+=1
        elif cmd=='CANCEL':
            i=int(a[0][1:])
            if i in bookings: del bookings[i]; response='OK'
            else: response='ERR no such booking'
        elif cmd=='SCHEDULE':
            if a[0] not in rooms: response='ERR no such room'
            else:
                bs=sorted((b[1],i,b) for i,b in bookings.items() if b[0]==a[0])
                response=', '.join(f'B{i} {clock(b[1])}-{clock(b[2])} {b[3]}' for _,i,b in bs) or '(empty)'
        else:
            people,duration=map(int,a); choices=[]
            for r,cap in rooms.items():
                if cap<people: continue
                start=480
                for b in sorted((b for b in bookings.values() if b[0]==r),key=lambda b:b[1]):
                    if b[2]<=start: continue
                    if start+duration<=b[1]: break
                    start=b[2]
                if start+duration<=1080: choices.append((start,cap,r))
            if choices:
                s,_,r=min(choices); response=f'{r} {clock(s)} {clock(s+duration)}'
            else: response='NONE'
    emit(response+'\n')
