"""Private spec-only reference; strict single-physical-line CSV parser."""
import datetime
import re
import sys

def date(s):
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',s): raise ValueError()
    datetime.date(*map(int,s.split('-')))
    return s

def csvline(s):
    result=[]; i=0
    while True:
        field=''
        if i<len(s) and s[i]=='"':
            i+=1
            while True:
                if i>=len(s): raise ValueError()
                if s[i]=='"':
                    i+=1
                    if i<len(s) and s[i]=='"': field+='"'; i+=1
                    else: break
                else: field+=s[i]; i+=1
            if i<len(s) and s[i]!=',': raise ValueError()
        else:
            while i<len(s) and s[i]!=',':
                if s[i]=='"': raise ValueError()
                field+=s[i]; i+=1
        result.append(field)
        if i==len(s): return result
        i+=1

def main(a):
    files=[]; low=high=None; i=0
    while i<len(a):
        x=a[i]
        if x in ('--from','--to') or x.startswith(('--from=','--to=')):
            kind=x.split('=')[0]
            if '=' in x: v=x.split('=',1)[1]
            else:
                i+=1
                if i==len(a): return 2
                v=a[i]
            try: date(v)
            except ValueError: return 2
            if kind=='--from': low=v
            else: high=v
        elif x.startswith('-'): return 2
        else: files.append(x)
        i+=1
    if len(files)!=1: return 2
    try: data=open(files[0],encoding='utf-8',newline='').read()
    except OSError: return 1
    lines=data.split('\n'); lines=[s[:-1] if s.endswith('\r') else s for s in lines]
    if lines[0]!='date,region,product,units,unit_price': return 1
    groups={}; total=[0,0,{}]; skipped=0
    for line in lines[1:]:
        if line=='': continue
        try:
            row=csvline(line)
            if len(row)!=5: raise ValueError()
            d,r,p,u,price=row; date(d)
            if not r or not p or not re.fullmatch('[0-9]+',u) or int(u)>10000: raise ValueError()
            if not re.fullmatch(r'[0-9]+\.[0-9]{2}',price): raise ValueError()
            cents=int(price.replace('.',''))
            if cents>1000000: raise ValueError()
        except ValueError:
            skipped+=1; continue
        if (low and d<low) or (high and d>high): continue
        for g in (groups.setdefault(r,[0,0,{}]),total):
            units=int(u); revenue=units*cents
            g[0]+=units; g[1]+=revenue; g[2][p]=g[2].get(p,0)+revenue
    def quote(s): return '"'+s.replace('"','""')+'"' if ',' in s or '"' in s else s
    def money(n): return '%d.%02d'%(n//100,n%100)
    print('region,units,revenue,avg_price,top_product')
    for r,g in [(r,groups[r]) for r in sorted(groups,key=lambda s:s.encode())]+[('TOTAL',total)]:
        u,c,p=g; top=min(p,key=lambda s:(-p[s],s.encode())) if p else '-'
        print(','.join(map(quote,[r,str(u),money(c),money((2*c+u)//(2*u)) if u else '-',top])))
    print('skipped',skipped)
    return 0
sys.exit(main(sys.argv[1:]))
