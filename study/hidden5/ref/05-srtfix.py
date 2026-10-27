"""Private srtfix reference, implemented from tasks5/05-srtfix.md."""
import re
import sys
from common import fail, match, stdin_lines
if len(sys.argv) != 2 or not match(r'[+-]?[0-9]{1,9}',sys.argv[1]): fail(2)
offset = int(sys.argv[1])
blocks, block = [], []
for line in stdin_lines():
    if match(r'[ \t]*',line):
        if block: blocks.append(block)
        block = []
    else: block.append(line)
if block: blocks.append(block)
timestamp = r'[0-9]{2}:[0-5][0-9]:[0-5][0-9],[0-9]{3}'
def milliseconds(t):
    h,m,s,ms = map(int,re.split('[:,]',t))
    return ((h*60+m)*60+s)*1000+ms
def fmt(t):
    seconds,ms = divmod(t,1000)
    minutes,s = divmod(seconds,60)
    h,m = divmod(minutes,60)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'
cues = []
for b in blocks:
    if len(b) < 3 or not match(r'[0-9]{1,9}',b[0]) or not match(timestamp+' --> '+timestamp,b[1]): fail(1)
    start,end = map(milliseconds,b[1].split(' --> '))
    if end <= start: fail(1)
    start,end = start+offset,end+offset
    if end > 0: cues.append((max(0,start),end,b[2:]))
cues.sort(key=lambda c:c[0])
for i,(start,end,text) in enumerate(cues,1):
    print(f'{i}\n{fmt(start)} --> {fmt(end)}\n'+'\n'.join(text)+'\n')
