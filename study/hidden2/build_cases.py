"""Reproducible spec-derived fixtures; expected bytes never come from references."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent
TASK = ''

def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value,bytes) else value.encode('utf-8'))

def files(base, setup):
    for key,value in (setup or {}).items():
        put(base/'setup'/key,value)

def case(name, args=(), stdin='', out='', code=0, setup=None):
    base = ROOT/TASK/'cases'/name
    put(base/'cmd', ''.join(a+'\n' for a in args))
    if stdin:
        put(base/'stdin',stdin)
    put(base/'expected_stdout',out); put(base/'expected_exit',str(code)+'\n')
    files(base,setup)

def multi(name, steps, setup=None):
    base = ROOT/TASK/'cases'/name
    files(base,setup)
    manifest = []
    for i,step in enumerate(steps,1):
        args,stdin,out,code,*kill = step
        s = 'step-'+str(i); directory = base/s
        put(directory/'cmd',''.join(a+'\n' for a in args))
        if stdin:
            put(directory/'stdin',stdin)
        put(directory/'expected_stdout',out)
        if kill:
            manifest.append(s+' kill-after='+str(kill[0]))
        else:
            manifest.append(s); put(directory/'expected_exit',str(code)+'\n')
    put(base/'steps','\n'.join(manifest)+'\n')

def usage(name, variants, code=2, setup=None):
    multi(name,[(a,'','',code) for a in variants],setup)

TASK='01-cfgcheck'
S='# service settings\nserver.port   int     required 1..65535\nserver.host   string  required maxlen=10\nserver.debug  bool    optional\nlog.level     enum    required debug,info,warn\n'
GOOD='[server]\nport = 8080\nhost = localhost\ndebug = true\n\n[log]\nlevel = info\n'
BAD='; broken\n[server]\nport = 70000\nhost = a-very-long-hostname\ndebug = yes\nport = 1\ntimeout = 5\n[log]\ngarbage line\n'
case('example-1',['schema.txt','config.ini'],out='OK\n',setup={'schema.txt':S,'config.ini':GOOD})
case('example-2',['schema.txt','config.ini'],out='3: server.port: out of range 1..65535\n4: server.host: longer than 10\n5: server.debug: not a boolean\n6: duplicate key server.port\n9: syntax error\nmissing: log.level\nerrors: 6\n',code=1,setup={'schema.txt':S,'config.ini':BAD})
case('example-3',['schema.txt','--strict','config.ini'],out='1: key outside section\n3: log.level: not one of debug,info,warn\n4: unknown key log.color\nerrors: 3\n',code=1,setup={'schema.txt':S,'config.ini':'level = info\n[log]\nlevel = verbose\ncolor = on\n[server]\nport=443\nhost=\n'})
case('example-4',['-q','schema.txt','config.ini'],code=1,setup={'schema.txt':S,'config.ini':BAD})
multi('example-5',[(['bad.txt','config.ini'],'','',3),(['schema.txt'],'','',2),(['-x','schema.txt','config.ini'],'','',2),(['schema.txt','nope.ini'],'','',2)],{'bad.txt':'a.b float required\n','schema.txt':S})
def cfg(name,s,c,out='OK\n',code=0,args=None):
    case(name,args or ['s','c'],out=out,code=code,setup={'s':s,'c':c})
cfg('empty-files','','')
cfg('required-order','z.x int required\na.z string required\na.y bool optional\n','','missing: z.x\nmissing: a.z\nerrors: 2\n',1)
cfg('crlf-tabs-final-line',' \t# c\r\n s.x\tint\trequired\t-00..0005\r\ns.y string required maxlen=0002','\t[s]\t\r\n x = -0\r\n y=ab')
cfg('section-accumulation','a.x int required\na.y bool required\n','[a]\nx=2\n[b]\nz=unused\n[a]\ny=false\n')
cfg('first-equals-no-inline-comments','a.x string required\na.y enum required #,;\n','[a]\nx=hello=world#;\ny=#\n')
cfg('unknown-duplicate-nonstrict','','[x]\na=1\na=2\n','3: duplicate key x.a\nerrors: 1\n',1)
cfg('strict-unknown-section','','[other]\nk=1\nk=2\n','2: unknown key other.k\n3: duplicate key other.k\nerrors: 2\n',1,['s','--strict','c','--strict'])
cfg('syntax-precedence','a.x int required\n','bad\n[INVALID]\nInvalid=1\nx=1\n[a]\nx=no\nx=2\n','1: syntax error\n2: syntax error\n3: syntax error\n4: key outside section\n6: a.x: not an integer\n7: duplicate key a.x\nerrors: 6\n',1)
cfg('integer-lexical-boundaries','a.w int required\na.x int required\na.y int required\na.z int required\n','[a]\nw=-999999999999999999\nx=999999999999999999\ny=+1\nz=1000000000000000000\n','4: a.y: not an integer\n5: a.z: not an integer\nerrors: 2\n',1)
cfg('range-inclusive-spelling','a.a int required -002..0003\na.b int required -002..0003\na.c int required -002..0003\n','[a]\na=-2\nb=0003\nc=-3\n','4: a.c: out of range -002..0003\nerrors: 1\n',1)
cfg('string-length-empty-and-enum','a.a string required maxlen=0\na.b string required maxlen=0001\na.c enum required one,Two,one\na.d bool required\n','[a]\na=\nb=xy\nc=two\nd=True\n','3: a.b: longer than 0001\n4: a.c: not one of one,Two,one\n5: a.d: not a boolean\nerrors: 3\n',1)
cfg('quiet-valid-repeat',S,GOOD,out='',args=['-q','s','-q','c'])
invalids=['a.b int required 4..2','a.b int required +1..2','a.b int required 0..1000000000000000000','a.b string optional maxlen=10000000','a.b string required maxlen=-1','a.b bool optional yes','a.b enum required','a.b enum required a,,b','a.b enum required ,a','a.b enum required a,','a.b int sometimes','A.b int optional','a.b.c int optional','a.b int optional extra extra','a.b int','a.b int optional\na.b string required','; not a comment']
multi('invalid-schema-grammar',[(['s'+str(i),'missing'],'','',3) for i in range(len(invalids))],{'s'+str(i):s+'\n' for i,s in enumerate(invalids)})
usage('usage-count-and-options',[[],['s','c','x'],['--','s','c'],['-q'],['-x','s']],setup={'s':''})
usage('read-failure-precedence',[['missing','missing2'],['s','missing']],setup={'s':''})
cfg('comments-and-repeated-cr','a.x string optional\n',' #hi\n\t;bye\n \t\n[a]\nx=value\r\r\n')
cfg('outside-key-not-seen','a.x int required\n','x=5\n[a]\n','1: key outside section\nmissing: a.x\nerrors: 2\n',1)
cfg('invalid-header-keeps-section','a.x int required\na.y int required\n','[a]\nx=1\n[bad name]\ny=2\n','3: syntax error\nerrors: 1\n',1)
cfg('maximum-line-string','a.x string required maxlen=998\n','[a]\nx='+('a'*998)+'\n')
cfg('paths-with-spaces','','',args=['s','c'])

TASK='02-ldiff'
def diff(name,a,b,out='',code=1,flags=()):
    case(name,[*flags,'a','b'],out=out,code=code,setup={'a':a,'b':b})
diff('example-1','apple\nbanana\ncherry\ndate\n','apple\nblueberry\ncherry\ndate\nelder\n','  apple\n- banana\n+ blueberry\n  cherry\n  date\n+ elder\n')
diff('example-2','Hello\nWorld\n','hello\nworld\n!\n','+1 -0 =2\n',flags=['-i','-s'])
multi('example-3',[(['-b','-q','p','q'],'','',0),(['-s','p','q'],'','+1 -1 =1\n',1)],{'p':'a  \nb\n','q':'a\nb'})
diff('example-4','','x\n','+ x\n')
usage('example-5',[['a'],['-q','-s','a','b'],['-u','a','b'],['a','missing.txt']],setup={'a':'a\n','b':'b\n'})
diff('empty-both','','',code=0)
diff('empty-summary','','','+0 -0 =0\n',0,['-s'])
diff('deletions-only','a\n\nb','','- a\n- \n- b\n')
diff('insert-empty-lines','','\n\n','+ \n+ \n')
diff('final-newline-equivalent','same\n','same','  same\n',0)
diff('tie-delete-before-insert','a\nb\n','b\na\n','- a\n  b\n+ a\n')
diff('repeated-lines','x\nx\ny\n','x\ny\nx\n','  x\n- x\n  y\n+ x\n')
diff('ascii-original-preserved','AbC\t \n','abc\n','  AbC\t \n',0,['-i','-b'])
diff('non-ascii-case-sensitive','Ä\nÉ\n','ä\nÉ\n','- Ä\n+ ä\n  É\n',1,['-i'])
diff('carriage-return-is-data','a\r\n','a\n','- a\r\n+ a\n',1,['-b'])
diff('leading-space-not-ignored',' a\n','a\n','-  a\n+ a\n',1,['-b'])
diff('trailing-only-removal','\t \na\t\t \n','\na\n','  \t \n  a\t\t \n',0,['-b'])
diff('quiet-different','a','b',code=1,flags=['-q'])
diff('quiet-equal','a','a',code=0,flags=['-q','-q'])
case('options-anywhere-repeated',['a','-i','-b','b','-s','-i'],out='+0 -0 =1\n',setup={'a':'X \n','b':'x\n'})
usage('usage-empty-extra-emptyarg',[[],['a','b','c'],['','a']],setup={'a':'','b':'','c':''})
usage('missing-first',[['missing','b']],setup={'b':''})
diff('unicode-byte-output','한글\n🙂\n','한글\n界\n','  한글\n- 🙂\n+ 界\n')
diff('line-byte-boundary','x'*1000+'\n','x'*1000,'  '+'x'*1000+'\n',0)
diff('lcs-line-count-boundary','a\n'*2000,'a\n'*1999,'+0 -1 =1999\n',1,['-s'])
