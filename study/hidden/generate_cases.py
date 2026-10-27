"""Rebuild explicit, spec-derived fixtures. Never imports or runs references."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data,str) else data)

def C(task,name,args=(),stdin='',stdout='',exit=0,setup=None,base=None):
    p=(ROOT/task/'cases'/name) if base is None else base/name
    write(p/'cmd',''.join(x+'\n' for x in args))
    if stdin: write(p/'stdin',stdin)
    write(p/'expected_stdout',stdout)
    if exit is not None: write(p/'expected_exit',str(exit)+'\n')
    for f,data in (setup or {}).items(): write(p/'setup'/f,data)
    return p

def M(task,name,steps,setup=None):
    p=ROOT/task/'cases'/name
    order=[]
    for i,step in enumerate(steps,1):
        args,stdin,stdout,*rest=step
        kill=rest[0] if rest else None
        stepname='run-'+str(i)
        C(task,stepname,args,stdin,stdout,None if kill else 0,base=p)
        order.append(stepname+(' kill-after='+str(kill) if kill else ''))
    write(p/'steps','\n'.join(order)+'\n')
    for f,data in (setup or {}).items(): write(p/'setup'/f,data)

def lines(*s): return '\n'.join(s)+'\n'

t='01-wordfreq'
s='the cat and the hat\nThe end\n'
C(t,'example-1',stdin=s,stdout='2 the\n1 The\n1 and\n1 cat\n1 end\n1 hat\n')
C(t,'example-2',['-i','-n','2'],s,'3 the\n1 and\n')
C(t,'example-3',['--min-length=4','notes.txt','missing.txt'],stdout='1 TOWELS\n1 panic\n1 towels\n',exit=1,setup={'notes.txt':"Don't panic: 42 towels, 42 TOWELS.\n"})
C(t,'example-4',['-n','0'],'a1 b2 a1\n','2 a1\n1 b2\n')
C(t,'example-5',['-n','abc'],exit=2)
C(t,'empty')
C(t,'separators',['--ignore-case'],"Don't_éx-y🙂Z 007 007\n",'2 007\n1 don\n1 t\n1 x\n1 y\n1 z\n')
C(t,'ascii-ties',stdin='z a Z A 9 0 a9 A9\n',stdout='1 0\n1 9\n1 A\n1 A9\n1 Z\n1 a\n1 a9\n1 z\n')
C(t,'default-ten',stdin='l k j i h g f e d c b a\n',stdout=''.join('1 '+x+'\n' for x in 'abcdefghij'))
C(t,'last-options',['--top=1','-n','0002','-m','4','--min-length','02','--ignore-case'],'A aa BB BB cc\n','2 bb\n1 aa\n')
C(t,'file-stdin-repeat',['one','-','one','--top','1000000000'], 's a\n','3 a\n2 z\n1 s\n',setup={'one':'a z\n'})
C(t,'end-options',['--','-i','--top=1'],stdout='2 Case\n1 case\n',setup={'-i':'Case\n','--top=1':'Case case\n'})
C(t,'missing-between',['a','missing','b'],stdout='2 x\n1 y\n',exit=1,setup={'a':'x\n','b':'x y\n'})
C(t,'all-missing',['missing'],exit=1)
C(t,'length-boundary',['-m','1000'],'a'*999+' '+'b'*1000+'\n','1 '+'b'*1000+'\n')
C(t,'missing-value',['--top'],stdin='should not print\n',exit=2)
C(t,'negative-value',['-n','-1'],exit=2)
C(t,'top-too-large',['--top=1000000001'],exit=2)
C(t,'min-zero',['--min-length=0'],exit=2)
C(t,'min-too-large',['-m','1001'],exit=2)
C(t,'empty-top',['--top='],exit=2)
C(t,'combined-short',['-in'],exit=2)
C(t,'flag-value',['--ignore-case=x'],exit=2)
C(t,'usage-after-file',['valid','-i=x'],exit=2,setup={'valid':'already read\n'})
C(t,'signed-number',['-n','+2'],exit=2)

t='02-semsort'
s=lines('1.0.0','1.0.0-alpha','1.0.0-alpha.1','1.0.0-beta.11','1.0.0-beta.2','1.0.0-rc.1','0.9.12','1.0.0-alpha.beta','1.0.0-beta')
C(t,'example-1',stdin=s,stdout=lines('0.9.12','1.0.0-alpha','1.0.0-alpha.1','1.0.0-alpha.beta','1.0.0-beta','1.0.0-beta.2','1.0.0-beta.11','1.0.0-rc.1','1.0.0'))
C(t,'example-2',['-r','-u'],lines('2.0.0+build.1','1.10.0','1.2.0','2.0.0+build.2','1.2.0'),lines('2.0.0+build.1','1.10.0','1.2.0'))
C(t,'example-3',stdin=lines('1.2.3','01.2.3','1.2','v1.0.0','','1.0.0-rc.01','1.0.0-rc.1+001'),stdout=lines('1.0.0-rc.1+001','1.2.3'),exit=1)
C(t,'example-4',['--no-pre','versions.txt'],stdout=lines('0.1.0+meta','1.0.0'),setup={'versions.txt':lines('1.0.0-rc.1','  1.0.0','0.1.0+meta')})
C(t,'example-5',['a.txt','b.txt'],exit=2)
C(t,'example-5-option',['--sort'],exit=2)
C(t,'example-5-missing',['nope.txt'],exit=1)
C(t,'empty')
C(t,'trim-crlf-final',stdin=' \t\r\n\t1.0.0+X \t\r\n 0.0.0\t',stdout=lines('0.0.0','1.0.0+X'))
C(t,'stable-build',stdin=lines('1.0.0+z','1.0.0+a','1.0.0','1.0.0+z'),stdout=lines('1.0.0+z','1.0.0+a','1.0.0','1.0.0+z'))
C(t,'reverse-equals',['-r'],lines('1.0.0+a','0.0.0','1.0.0+b'),lines('1.0.0+b','1.0.0+a','0.0.0'))
C(t,'unique-first',['-u'],lines('1.0.0-rc+z','1.0.0-rc+a','1.0.0+z','1.0.0+a'),lines('1.0.0-rc+z','1.0.0+z'))
C(t,'filter-unique-reverse',['--no-pre','-u','-r'],lines('2.0.0-a','1.0.0+x','0.0.0','1.0.0+y','junk'),lines('1.0.0+x','0.0.0'),1)
C(t,'pre-identifier-types',stdin=lines('1.0.0-a','1.0.0-10','1.0.0-2','1.0.0-Z','1.0.0--','1.0.0-2.a','1.0.0-2.0'),stdout=lines('1.0.0-2','1.0.0-2.0','1.0.0-2.a','1.0.0-10','1.0.0--','1.0.0-Z','1.0.0-a'))
C(t,'numeric-cores',stdin=lines('10.0.0','2.0.0','1.10.0','1.2.10','1.2.2'),stdout=lines('1.2.2','1.2.10','1.10.0','2.0.0','10.0.0'))
C(t,'max-numbers',stdin=lines('999999999.999999999.999999999-999999999+0000000000','0.0.0-0'),stdout=lines('0.0.0-0','999999999.999999999.999999999-999999999+0000000000'))
C(t,'invalid-core-numbers',stdin=lines('1000000000.0.0','1.00.0','-1.0.0','1.0.00','1.0.0.0','1.0.0'),stdout='1.0.0\n',exit=1)
C(t,'invalid-pre-numbers',stdin=lines('1.0.0-01','1.0.0-rc.1000000000','1.0.0-00a'),stdout='1.0.0-00a\n',exit=1)
C(t,'empty-identifiers',stdin=lines('1.0.0-','1.0.0+','1.0.0-a..b','1.0.0+a..b','1.0.0-.a','1.0.0+a.'),exit=1)
C(t,'invalid-characters',stdin=lines('v1.0.0','1.0.0_a','1.0.0+é','1.0.0-a b','1.0.0+a+b'),exit=1)
C(t,'build-alphabet',stdin=lines('1.0.0+000.Z-a.---','1.0.0-000a+0'),stdout=lines('1.0.0-000a+0','1.0.0+000.Z-a.---'))
C(t,'repeat-options-after-file',['v','-r','-r','-u','-u','--no-pre','--no-pre'],stdout='1.0.0\n',setup={'v':lines('1.0.0','1.0.0+x','1.0.0-a')})
C(t,'dash-is-option',['-'],exit=2)
C(t,'filter-all',['--no-pre'],'1.0.0-a\n')
C(t,'all-invalid',stdin=lines('no','1','1.0'),exit=1)

t='03-fcut'
C(t,'example-1',['-f','3,1','-d',','],'a,b,c\nd,e\nnodelim\n','c,a\nd\nnodelim\n')
C(t,'example-2',['-f2-','-s'],'x\ty\tz\nplain\n\n','y\tz\n')
C(t,'example-3',['-f','-2,2','-d',':','--output-delimiter= | '],'root:x:0:0\n','root | x | x\n')
C(t,'example-4',['-f1','-d',',','a.csv','nope.csv'],stdout='1\n',exit=1,setup={'a.csv':'1,2\n'})
C(t,'example-5',['-f','0'],exit=2)
C(t,'example-5-missing-fields',['-d',',','a.csv'],exit=2)
C(t,'example-5-descending',['-f','3-1'],exit=2)
C(t,'example-5-delimiter',['-f','1','-d','ab'],exit=2)
C(t,'empty',['-f1'])
C(t,'empty-fields-repeat',['-f4,2,1,3,4','-d,'],'a,,b,\n',',,a,b,\n')
C(t,'missing-all',['-f1000000','-d,'],'a,b\nplain\n\n','\nplain\n\n')
C(t,'range-order',['-f3-,1-2,2,9-10','-d:','--output-delimiter=/'],'a:b:c:d\n','c/d/a/b/b\n')
C(t,'cr-is-data',['-f2,1','-d,'],'a,b\r\n,\r\nlast,no-newline','b\r,a\n\r,\nno-newline,last\n')
C(t,'skip-only',['-f1','--only-delimited','-d,'],'\nplain\n,\nx,y\n','\nx\n')
C(t,'empty-output-delimiter',['-f2,1','-d,','--output-delimiter='],'a,b\n','ba\n')
C(t,'last-options',['-f1','-d,','-f2','-d:','--output-delimiter=xxx','--output-delimiter= '],'a:b:c\n','b\n')
C(t,'files-stdin-repeat',['a','-f1','-','a','-d,'],'s,t\n','x\ns\nx\n',setup={'a':'x,y\n'})
C(t,'end-options',['-f1','-d,','--','-s'],stdout='x\nplain\n',setup={'-s':'x,y\nplain\n'})
C(t,'leading-zero-range',['-f0001-0002,0002-','-d,'],'a,b,c\n','a,b,b,c\n')
C(t,'empty-list',['-f',''],exit=2)
C(t,'empty-element',['-f1,,2'],exit=2)
C(t,'lone-range',['-f','-'],exit=2)
C(t,'range-too-large',['-f1-1000001'],exit=2)
C(t,'empty-delimiter',['-f1','-d',''],exit=2)
C(t,'output-missing-equals',['-f1','--output-delimiter'],exit=2)
