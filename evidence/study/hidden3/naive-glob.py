"""Deliberately exponential * / literal control for the glob stress case only."""
import sys
pattern=sys.argv[-1]

def match(p,i,s,j):
    if i==len(p): return j==len(s)
    if p[i]=='*':
        return any(match(p,i+1,s,k) for k in range(j,len(s)+1))
    return j<len(s) and p[i]==s[j] and match(p,i+1,s,j+1)

count=0
for line in sys.stdin:
    if match(pattern,0,line.removesuffix('\n'),0): count+=1
print(count)
sys.exit(0 if count else 1)
