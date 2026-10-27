"""Set 4 fixtures, independently worked from frozen task specs.

This builder never imports, executes, or reads a reference or submitted program.
Expectations are literal results or closed-form constructions for simple inputs.
Formatting helpers receive already-worked values; none implements a task solver.
"""
from pathlib import Path
import shutil
ROOT = Path(__file__).resolve().parent
TASK = ''

def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value, bytes) else value.encode('utf-8'))

def base(name, setup):
    p = ROOT / TASK / 'cases' / name
    if p.exists(): shutil.rmtree(p)
    p.mkdir(parents=True)
    for filename, value in (setup or {}).items():
        if value is None: (p/'setup'/filename).mkdir(parents=True, exist_ok=True)
        else: put(p/'setup'/filename, value)
    return p

def files(p, args, stdin, out, code):
    put(p/'cmd', ''.join(a+'\n' for a in args))
    if stdin: put(p/'stdin', stdin)
    put(p/'expected_stdout', out)
    if code is not None: put(p/'expected_exit', str(code)+'\n')

def case(name, args=(), stdin='', out='', code=0, setup=None):
    files(base(name,setup),args,stdin,out,code)

def multi(name, steps, setup=None):
    p = base(name,setup)
    manifest = []
    for i, (args, stdin, out, code, *kill) in enumerate(steps,1):
        label = f'step-{i}'
        manifest.append(label+(f' kill-after={kill[0]}' if kill else ''))
        files(p/label,args,stdin,out,None if kill else code)
    put(p/'steps','\n'.join(manifest)+'\n')

def errors(name, variants, code=2, setup=None):
    multi(name, [(a,'','',code) for a in variants], setup)

def lines(items): return ''.join(x+'\n' for x in items)

def hexline(offset, fields, ascii_text, width=16):
    # Merely render explicitly supplied byte fields and ASCII, without reading input.
    return f'{offset:08x}  '+fields.ljust(3*width-1)+f'  |{ascii_text}|\n'

TASK = '01-hexdump'
HELLO = b'Hello, world!\n'
HELLO_SETUP = {'hello.txt': HELLO}
case('example-1',['-w','8','hello.txt'],out=hexline(0,'48 65 6c 6c 6f 2c 20 77','Hello, w',8)+hexline(8,'6f 72 6c 64 21 0a','orld!.',8)+'0000000e\n',setup=HELLO_SETUP)
case('example-2',stdin=b'id\tname\r\n1\tAl\x00\xff\n2\tBo\n',out=hexline(0,'69 64 09 6e 61 6d 65 0d 0a 31 09 41 6c 00 ff 0a','id.name..1.Al...')+hexline(16,'32 09 42 6f 0a','2.Bo.')+'00000015\n')
case('example-3',['-s','4','-n','6','-w','4','hello.txt'],out=hexline(4,'6f 2c 20 77','o, w',4)+hexline(8,'6f 72','or',4)+'0000000a\n',setup=HELLO_SETUP)
multi('example-4',[([], '', '00000000\n',0),(['-s','100','hello.txt'],'','00000064\n',0),(['-n','0','-'],'abc','00000000\n',0)],HELLO_SETUP)
multi('example-5',[(a,'','',2) for a in [['-w','0'],['-w','33'],['-s'],['-n','-1'],['-x'],['a.bin','b.bin']]]+[(['missing.bin'],'','',1)])
case('empty-file',['e'],out='00000000\n',setup={'e':b''})
# Every byte, with closed-form expected columns for the deliberately exhaustive alphabet.
case('all-byte-values',['-w','32'],bytes(range(256)),out=''.join(hexline(i,' '.join(f'{j:02x}' for j in range(i,i+32)),''.join(chr(j) if 32 <= j <= 126 else '.' for j in range(i,i+32)),32) for i in range(0,256,32))+'00000100\n')
case('ascii-boundaries',['-w','6'],b'\x1f !~\x7f\x80',hexline(0,'1f 20 21 7e 7f 80','. !~..',6)+'00000006\n')
case('width-one',['-w','1'],b'A\n\xff',hexline(0,'41','A',1)+hexline(1,'0a','.',1)+hexline(2,'ff','.',1)+'00000003\n')
case('width32-short',['-w','32'],b'abc',hexline(0,'61 62 63','abc',32)+'00000003\n')
case('exact-chunk-no-empty-row',['-w','4'],b'abcdefgh',hexline(0,'61 62 63 64','abcd',4)+hexline(4,'65 66 67 68','efgh',4)+'00000008\n')
case('unaligned-skip',['-s','3','-w','3','-n','5'],b'0123456789',hexline(3,'33 34 35','345',3)+hexline(6,'36 37','67',3)+'00000008\n')
case('skip-exact-eof',['-s','3'],b'abc','00000003\n')
case('length-past-eof',['-n','999999999','-w','4'],b'xy',hexline(0,'78 79','xy',4)+'00000002\n')
case('zero-length-keeps-skip',['-s','12','-n','0'],b'abc','0000000c\n')
case('maximum-skip',['-s','999999999'],b'abc','3b9ac9ff\n')
case('repeated-options-anywhere',['-w','1','f','-s','000000001','-w','04','-n','000000001','-n','000000003','-s','000000002'],out=hexline(2,'63 64 65','cde',4)+'00000005\n',setup={'f':'abcdef'})
case('explicit-stdin',['-','-w','2'],b'\x00\r\n',hexline(0,'00 0d','..',2)+hexline(2,'0a','.',2)+'00000003\n')
case('filename-with-spaces',['a b','-w','2'],b'wrong',hexline(0,'4f 4b','OK',2)+'00000002\n',setup={'a b':'OK'})
case('dash-prefixed-path',['./-x','-w','2'],out=hexline(0,'2d','-',2)+'00000001\n',setup={'-x':'-'})
errors('unreadable-directory-and-empty-path',[['dir'],['']],1,{'dir':None})
errors('usage-value-grammar',[[flag,x] for flag in ['-s','-n'] for x in ['','+1','1.0',' 1','1 ','1234567890']]+[['-w',x] for x in ['','-1','+1','000','100','1.0',' 2']])
errors('usage-missing-unknown-files',[['-n'],['-w'],['--'],['-sn','2'],['-s','-w'],['-','-'],['f','-']])
case('usage-before-read',['missing','-w','x'],b'anything','',2)
case('input-mib-boundary',['-s','1048560'],b'z'*(1024*1024),hexline(1048560,' '.join(['7a']*16),'z'*16)+'00100000\n')

TASK = '02-uniqx'
ABC = 'a\na\nb\na\na\na\nc\n'
multi('example-1',[([],ABC,'a\nb\na\nc\n',0),(['-c'],ABC,'      2 a\n      1 b\n      3 a\n      1 c\n',0)])
multi('example-2',[(['-d'],ABC,'a\na\n',0),(['-u','-c'],ABC,'      1 b\n      1 c\n',0),(['-d','-u'],ABC,'',0)])
case('example-3',['-c','-i','-f','1'],'10:01 Disk full\n10:02 disk FULL\n10:05  Disk full\n10:07 Net down\n10:09 net down\r\n','      2 10:01 Disk full\n      1 10:05  Disk full\n      2 10:07 Net down\n')
multi('example-4',[(['-s','2','-c'],'x-apple\ny-apple\nz-pear\nApear','      2 x-apple\n      1 z-pear\n      1 Apear\n',0),(['-c'],'\n\nx\n\n','      2 \n      1 x\n      1 \n',0),(['-f','3'],'a b\nc d\n','a b\n',0)])
errors('example-5',[['-f'],['-f','x'],['-s','12345'],['-ci'],['input.txt']])
case('empty')
case('single-final-line',stdin='abc',out='abc\n')
case('only-newlines',['-c'],'\n\n\n','      3 \n')
case('adjacency-not-global',['-c'],'x\nx\ny\nx\n','      2 x\n      1 y\n      1 x\n')
case('case-sensitive-default',stdin='A\na\nA\n',out='A\na\nA\n')
case('case-fold-original',['-i','-c'],'AbC\naBc\nABC\n!\n','      3 AbC\n      1 !\n')
case('field-blanks-retained',['-f','1','-c'],'\t aa x\nbb x\ncc\tx\ndd\tx\n','      2 \t aa x\n      2 cc\tx\n')
case('skip-two-fields',['-f','2','-c'],'a b c\nx y c\nz y  c\n','      2 a b c\n      1 z y  c\n')
case('fields-and-chars',['-f','1','-s','2','-c'],'aa xKey\nbb yKey\ncc zElse\n','      2 aa xKey\n      1 cc zElse\n')
case('fields-exhausted',['-f','9999','-c'],'\na\na b\n \n\t','      5 \n')
case('characters-exhausted',['-s','9999','-c'],'first\nsecond\n\n','      3 first\n')
case('crlf-strip-exactly-one',['-c'],b'a\r\na\n\r\n\nq\r\r\nq\r\n',b'      2 a\n      2 \n      1 q\r\n      1 q\n')
case('repeat-options-last-wins',['-f','2','-s','9','-c','-i','-c','-f','0001','-s','0001','-i'],'1 Ab\n2 aB\n3 Ac\n','      2 1 Ab\n      1 3 Ac\n')
case('unique-selection',['-u','-c'],'a\nb\nb\nc\nd\nd\n','      1 a\n      1 c\n')
case('duplicate-selection',['-d','-c'],'a\nb\nb\nc\nd\nd\n','      2 b\n      2 d\n')
case('both-flags-suppress',['-u','-d','-c'],'a\na\nb\n','')
errors('usage-values',[[f,v] for f in ['-f','-s'] for v in ['','-1','+1','1.0',' 1','1 ','00000']]+[['-s'],['-s','-i']])
errors('usage-tokens',[['--'],['-'],[''],['-C'],['-ic'],['-f1'],['-s=2']])
case('zero-skip-keeps-spaces',['-f','0000','-s','0000','-c'],' x \n x \nx\n','      2  x \n      1 x\n')
case('million-byte-count',['-c'],'a\n'*500000,' 500000 a\n')

TASK = '03-icalc'
multi('example-1',[( [x], '', y+'\n',0) for x,y in [('1+2*3','7'),('(1+2)*3','9'),('-7/2','-3'),('-7%3','-1'),('-17 / 5 * 5 + -17 % 5','-17'),(' 0007 ','7')]])
multi('example-2',[(['-D','x=10','-D','y=-4','x*x + y'],'','96\n',0),(['-D','rate=7','-D','rate=3','-D','n_2=-0','(rate - n_2) * -(2 + rate) / 4'],'','-3\n',0)])
multi('example-3',[([x],'','error: '+y+'\n',1) for x,y in [('1/0','division by zero'),('5%0','division by zero'),('999999999999999+1','overflow'),('999999999999999*2/2','overflow'),('z+1','undefined z'),('1/0+z','division by zero'),('z+1/0','undefined z')]])
multi('example-4',[([x],'','error: syntax\n',1) for x in ['1+','1/0+','+1','2x','X','1 2','()','1234567890123456','--','']])
errors('example-5',[[],['1','2'],['-D'],['-D','x=5'],['-D','x','1'],['-D','X=1','1']])
multi('left-associativity',[([x],'',y+'\n',0) for x,y in [('10-4-3','3'),('20/3/2','3'),('17%5*3','6'),('8/3*3','6')]])
multi('signs-and-precedence',[([x],'',y+'\n',0) for x,y in [('2*-3+4','-2'),('1--2','3'),('2---3','-1'),('-(2+3)*-4','20')]])
case('repeated-unary',['-'*200+'3'],out='3\n')
multi('zero-normalization',[([x],'','0\n',0) for x in ['-0','--000','0*-999999999999999','0/-7','0%-7']])
case('definitions-after-expression',['x+y','-D','x=0007','-D','y=-0002','-D','x=9'],out='7\n')
multi('names-boundaries',[(['-D','a123456789012345=7','a123456789012345'],'','7\n',0),(['abcdefghijklmnopq'],'','error: undefined abcdefghijklmnopq\n',1)])
multi('token-boundaries',[([x],'','error: syntax\n',1) for x in ['1a','a b','(1)(2)','1(2)','1\t+2','0.1','1_0','a!']])
multi('syntax-before-evaluation',[([x],'','error: syntax\n',1) for x in ['z + (1','1/0 + 2 3','999999999999999*2 )','z + @','z+1234567890123456','1/0 + +2']])
multi('first-evaluation-error',[([x],'','error: '+reason+'\n',1) for x,reason in [('u*(1/0)','undefined u'),('(1/0)*u','division by zero'),('(999999999999999+1)+u','overflow'),('u+(999999999999999+1)','undefined u'),('1+(v+u)','undefined v')]])
multi('overflow-negative-and-product',[([x],'','error: overflow\n',1) for x in ['-999999999999999-1','999999999999999- -1','999999999999999*-2','-999999999999999+-1']])
multi('intermediate-overflow',[([x],'','error: overflow\n',1) for x in ['(999999999999999+1)-1','0*(999999999999999*2)','999999999999999*2%2']])
multi('number-range-endpoints',[([x],'',y+'\n',0) for x,y in [('999999999999999','999999999999999'),('-999999999999999','-999999999999999'),('999999999999999/-1','-999999999999999'),('999999999999999%2','1'),('000000000000007','7')]])
errors('usage-definition-grammar',[['-D',v,'1'] for v in ['=1','1x=2','_x=1','x=+1','x=','x=1234567890123456','abcdefghijklmnopq=1','x=1=2','x= 1','x=-','x=1 ']])
errors('usage-option-consumption',[['1','-D','-D'],['-D','-1','1'],['1','2/0'],['-D','a=1','1','-D']])
case('expression-1000-bytes',[' '*500+'1'+' '*499],out='1\n')
case('depth-fifty',['('*50+'2+3'+')'*50],out='5\n')
multi('division-sign-matrix',[([x],'',y+'\n',0) for x,y in [('7/3','2'),('-7/3','-2'),('7/-3','-2'),('-7/-3','2'),('-1/2','0')]])
multi('remainder-sign-matrix',[([x],'',y+'\n',0) for x,y in [('7%3','1'),('-7%3','-1'),('7%-3','1'),('-7%-3','-1'),('-6%3','0')]])
multi('unsupported-syntax',[([x],'','error: syntax\n',1) for x in ['2**3','1//2','x=1','0x10','1,2','[1]','1\r','2^3']])
case('maximal-variable-token',['-D','a1_b=42','a1_b+1'],out='43\n')

def tm(m): return f'{m//60}:{m%60:02d}'
def employee(name, days=(), total=0, overtime=0, anomalies=0):
    return ' '.join([name]+[d+'='+tm(m) for d,m in days]+['total='+tm(total),'overtime='+tm(overtime),'anomalies='+str(anomalies)])+'\n'

TASK = '04-timesheet'
case('example-1',stdin='ann Mon 09:00 IN\nann Mon 17:30 OUT\nbob Mon 08:00 IN\nbob Mon 12:00 OUT\nann Tue 08:15 IN\nbob Mon 13:00 IN\nann Tue 18:00 OUT\nbob Mon 16:45 OUT\n',out='ann Mon=8:30 Tue=9:45 total=18:15 overtime=2:15 anomalies=0\nbob Mon=7:45 total=7:45 overtime=0:00 anomalies=0\nskipped=0\n')
case('example-2',stdin='cy Wed 13:00 OUT\ncy Wed 08:00 IN\ncy Wed 12:00 IN\ncy Thu 09:00 IN\ncy Thu 09:30 OUT\ncy Thu 10:00 OUT\ncy Fri 22:00 IN\n',out='cy Wed=1:00 Thu=0:30 total=1:30 overtime=0:00 anomalies=3\nskipped=0\n')
case('example-3',stdin='dee Sat 10:00 IN\ndee Sat 10:00 OUT\nDee Sat 10:00 IN\ndee sat 10:00 IN\ndee Sat 24:00 OUT\ndee Sat 9:00 IN\n   \ndee  Sun 10:00 IN\r\ndee Sun 10:00 IN\r\ndee Sun 23:59 OUT',out='dee Sun=13:59 total=13:59 overtime=5:59 anomalies=0\nskipped=5\n')
multi('example-4',[([], '', 'skipped=0\n',0),([], 'x\n','skipped=1\n',0)])
case('example-5',['week.txt'],out='',code=2)
case('ignored-space-lines',stdin='\n   \n \r\n\r\n',out='skipped=0\n')
case('chronological-sort',stdin='a Mon 18:00 OUT\na Mon 13:00 IN\na Mon 12:00 OUT\na Mon 08:00 IN\n',out=employee('a',[('Mon',540)],540,60)+'skipped=0\n')
multi('stable-ties',[([], 'a Mon 09:00 IN\na Mon 09:00 OUT\n',employee('a')+'skipped=0\n',0),([], 'a Mon 09:00 OUT\na Mon 09:00 IN\n',employee('a',anomalies=2)+'skipped=0\n',0)])
case('replacement-in',stdin='a Tue 08:00 IN\na Tue 09:00 IN\na Tue 10:00 IN\na Tue 11:15 OUT\n',out=employee('a',[('Tue',75)],75,0,2)+'skipped=0\n')
case('unmatched-outs',stdin='a Fri 00:00 OUT\na Fri 01:00 OUT\na Fri 10:00 IN\na Fri 11:00 OUT\na Fri 12:00 OUT\n',out=employee('a',[('Fri',60)],60,0,3)+'skipped=0\n')
case('no-cross-day-pairing',stdin='a Mon 23:00 IN\na Tue 01:00 OUT\na Sun 23:59 IN\n',out=employee('a',anomalies=3)+'skipped=0\n')
case('daily-sum-before-overtime',stdin='a Mon 00:00 IN\na Mon 05:00 OUT\na Mon 10:00 IN\na Mon 15:00 OUT\na Tue 00:00 IN\na Tue 02:00 OUT\n',out=employee('a',[('Mon',600),('Tue',120)],720,120)+'skipped=0\n')
DAYS = 'Mon Tue Wed Thu Fri Sat Sun'.split()
case('no-weekly-threshold',stdin=''.join(f'a {d} 08:00 IN\na {d} 16:00 OUT\n' for d in DAYS[:6]),out=employee('a',[(d,480) for d in DAYS[:6]],2880)+'skipped=0\n')
case('daily-thresholds',stdin='a Mon 00:00 IN\na Mon 08:00 OUT\na Tue 00:00 IN\na Tue 08:01 OUT\na Wed 00:00 IN\na Wed 07:59 OUT\n',out=employee('a',[('Mon',480),('Tue',481),('Wed',479)],1440,1)+'skipped=0\n')
case('maximum-week-span',stdin=''.join(f'a {d} 00:00 IN\na {d} 23:59 OUT\n' for d in reversed(DAYS)),out=employee('a',[(d,1439) for d in DAYS],10073,6713)+'skipped=0\n')
case('employee-byte-order',stdin='z Sun 00:00 IN\naa Tue 00:00 OUT\na Wed 00:00 OUT\n',out=employee('a',anomalies=1)+employee('aa',anomalies=1)+employee('z',anomalies=1)+'skipped=0\n')
BAD_PUNCHES = ['a  Mon 00:00 IN',' a Mon 00:00 IN','a Mon 00:00 IN ','a\tMon 00:00 IN','A Mon 00:00 IN','a1 Mon 00:00 IN','a mon 00:00 IN','a Mon 24:00 IN','a Mon 23:60 OUT','a Mon 9:00 IN','a Mon 00:0 IN','a Mon 00:00 in','a Mon 00:00 IN extra']
case('strict-skips-do-not-alter-state',stdin='a Mon 00:00 IN\n'+lines(BAD_PUNCHES)+'a Mon 01:00 OUT\n',out=employee('a',[('Mon',60)],60)+'skipped=13\n')
case('tabs-not-ignored',stdin='\t\n \t \n   \n\n',out='skipped=2\n')
case('invalid-lines-create-no-employees',stdin='ghost Mon 99:00 IN\nother Tue 00:00 BAD\n',out='skipped=2\n')
case('one-cr-only',stdin=b'a Mon 00:00 IN\r\na Mon 01:00 OUT\r\r\na Mon 02:00 OUT\r',out=employee('a',[('Mon',120)],120)+'skipped=1\n')
case('final-no-newline',stdin='a Thu 12:34 IN\na Thu 12:35 OUT',out=employee('a',[('Thu',1)],1)+'skipped=0\n')
case('duplicate-punches',stdin='a Mon 00:00 IN\na Mon 00:00 IN\na Mon 00:01 OUT\na Mon 00:01 OUT\n',out=employee('a',[('Mon',1)],1,0,2)+'skipped=0\n')
errors('usage-arguments',[[''],['-x'],['a','b']])
case('name-lengths',stdin='abcdefghijklmnop Mon 00:00 OUT\nabcdefghijklmnopq Mon 00:00 OUT\na Mon 00:00 OUT\n',out=employee('a',anomalies=1)+employee('abcdefghijklmnop',anomalies=1)+'skipped=1\n')
case('hundred-thousand-lines',stdin='a Mon 00:00 IN\na Mon 00:00 OUT\n'*50000,out=employee('a')+'skipped=0\n')

TASK = '05-runoff'
case('example-1',stdin='candidates: Alice Bob Carol\nAlice>Bob\nAlice\nAlice>Carol\nBob>Alice\nBob\nCarol>Bob\nCarol>Bob\n',out='ballots=7 invalid=0\nround 1: Alice=3 Bob=2 Carol=2 exhausted=0\neliminated: Carol\nround 2: Alice=3 Bob=4 exhausted=0\nwinner: Bob\n')
case('example-2',stdin='# club vote\ncandidates: Ana Ben Cho Dov\nAna>Ben\nBen>Ana\nCho\nDov>Cho\n\nAna>Zed\nBen>Ben\nAna>>Ben\nana\nCho>Ana\r\nBen>Cho>Dov\n',out='ballots=6 invalid=4\nround 1: Ana=1 Ben=2 Cho=2 Dov=1 exhausted=0\neliminated: Dov\nround 2: Ana=1 Ben=2 Cho=3 exhausted=0\neliminated: Ana\nround 3: Ben=3 Cho=3 exhausted=0\neliminated: Cho\nround 4: Ben=3 exhausted=3\nwinner: Ben\n')
case('example-3',stdin='candidates: X Y\nX\nY\n',out='ballots=2 invalid=0\nround 1: X=1 Y=1 exhausted=0\neliminated: Y\nround 2: X=1 exhausted=1\nwinner: X\n')
case('example-4',stdin='candidates: P Q R\n',out='ballots=0 invalid=0\nround 1: P=0 Q=0 R=0 exhausted=0\neliminated: R\nround 2: P=0 Q=0 exhausted=0\neliminated: Q\nround 3: P=0 exhausted=0\nwinner: P\n')
multi('example-5',[([],s,'',1) for s in ['candidates:\nA\n','A>B\n','candidates: A B A\n','candidates:  A B\n','']]+[(['ballots.txt'],'','',2)])
case('ignored-only-input',stdin='\n   \n# header missing\r\n',code=1)
case('one-candidate-no-ballots',stdin='candidates: Solo\n',out='ballots=0 invalid=0\nround 1: Solo=0 exhausted=0\nwinner: Solo\n')
case('one-candidate-mixed-ballots',stdin='candidates: Solo\nSolo\nSolo>Solo\nsolo\n#x\n \nSolo\n',out='ballots=2 invalid=2\nround 1: Solo=2 exhausted=0\nwinner: Solo\n')
case('immediate-majority',stdin='candidates: A B C\nA\nA>C\nB>A\n',out='ballots=3 invalid=0\nround 1: A=2 B=1 C=0 exhausted=0\nwinner: A\n')
case('half-is-not-majority',stdin='candidates: A B C\nA\nA\nB>C\nC>B\n',out='ballots=4 invalid=0\nround 1: A=2 B=1 C=1 exhausted=0\neliminated: C\nround 2: A=2 B=2 exhausted=0\neliminated: B\nround 3: A=2 exhausted=2\nwinner: A\n')
case('listing-order-not-name-order',stdin='candidates: Z A M\nZ\nA\nM\n',out='ballots=3 invalid=0\nround 1: Z=1 A=1 M=1 exhausted=0\neliminated: M\nround 2: Z=1 A=1 exhausted=1\neliminated: A\nround 3: Z=1 exhausted=2\nwinner: Z\n')
case('zero-votes-eliminated-singly',stdin='candidates: A B C D\nA\nB\n',out='ballots=2 invalid=0\nround 1: A=1 B=1 C=0 D=0 exhausted=0\neliminated: D\nround 2: A=1 B=1 C=0 exhausted=0\neliminated: C\nround 3: A=1 B=1 exhausted=0\neliminated: B\nround 4: A=1 exhausted=1\nwinner: A\n')
case('exhaustion-majority-denominator',stdin='candidates: A B C D\nA\nA\nA\nB\nB\nC\nD\n',out='ballots=7 invalid=0\nround 1: A=3 B=2 C=1 D=1 exhausted=0\neliminated: D\nround 2: A=3 B=2 C=1 exhausted=1\neliminated: C\nround 3: A=3 B=2 exhausted=2\nwinner: A\n')
BAD_BALLOTS = ['A>A','A>>B','A>','>A','a','A B',' A','A ','B\t','Z','A>B>A','candidates: A B']
case('strict-ballot-grammar',stdin='candidates: A B\n'+lines(BAD_BALLOTS)+'A\n',out='ballots=1 invalid=12\nround 1: A=1 B=0 exhausted=0\nwinner: A\n')
case('case-distinct-candidates',stdin='candidates: a A\na>A\nA>a\n',out='ballots=2 invalid=0\nround 1: a=1 A=1 exhausted=0\neliminated: A\nround 2: a=2 exhausted=0\nwinner: a\n')
NAMES20 = [f'C{i}' for i in range(20)]
case('twenty-candidates-zero-ballots',stdin='candidates: '+' '.join(NAMES20)+'\n',out='ballots=0 invalid=0\n'+''.join(f'round {21-n}: '+' '.join(x+'=0' for x in NAMES20[:n])+' exhausted=0\n'+('eliminated: '+NAMES20[n-1]+'\n' if n > 1 else 'winner: C0\n') for n in range(20,0,-1)))
case('twenty-character-name',stdin='candidates: Abcdefghijklmnopqrs9\nAbcdefghijklmnopqrs9\n',out='ballots=1 invalid=0\nround 1: Abcdefghijklmnopqrs9=1 exhausted=0\nwinner: Abcdefghijklmnopqrs9\n')
multi('invalid-header-names',[([],f'candidates: {name}\n','',1) for name in ['1A','_A','A-B','ABCDEFGHIJKLMNOPQRSTU','A.B']]+[([], 'candidates: '+' '.join(f'A{i}' for i in range(21))+'\n','',1)])
multi('invalid-header-whitespace',[([],s,'',1) for s in [' candidates: A\n','candidates:A\n','candidates: A \n','candidates: A\tB\n','Candidates: A\n','candidates: A\r\r\n']])
case('comments-only-at-column-zero',stdin='#x\n \n\ncandidates: A\n# ignore\n # invalid ballot\n\t\nA\n',out='ballots=1 invalid=2\nround 1: A=1 exhausted=0\nwinner: A\n')
case('second-header-is-invalid-ballot',stdin='candidates: A B\ncandidates: B A\nA\n',out='ballots=1 invalid=1\nround 1: A=1 B=0 exhausted=0\nwinner: A\n')
case('hundred-thousand-ballots',stdin='candidates: A B\n'+'A>B\n'*100000,out='ballots=100000 invalid=0\nround 1: A=100000 B=0 exhausted=0\nwinner: A\n')
case('crlf-final-ballot',stdin='candidates: A B\r\nA\r\nB>A',out='ballots=2 invalid=0\nround 1: A=1 B=1 exhausted=0\neliminated: B\nround 2: A=2 exhausted=0\nwinner: A\n')
case('valid-name-punctuation',stdin='candidates: A_0 b99\nA_0\nb99>A_0\n',out='ballots=2 invalid=0\nround 1: A_0=1 b99=1 exhausted=0\neliminated: b99\nround 2: A_0=2 exhausted=0\nwinner: A_0\n')
errors('usage-arguments',[[''],['-x'],['a','b']])

TASK = '06-mdtoc'
MD1 = '# Project Tenon\n\nIntro text.\n\n## Getting Started\n### Install\n### First steps\n## FAQ\n'
MO1 = '- [Project Tenon](#project-tenon)\n  - [Getting Started](#getting-started)\n    - [Install](#install)\n    - [First steps](#first-steps)\n  - [FAQ](#faq)\n'
MD2 = '## Usage\n```\n# not a heading\n## also not\n```\n## Usage\n#Hashtag\n#### Notes & Tips!\n##  Spaced   out  \n## Usage-1\n## Usage\n## ???\n####### Seven\n'
MO2 = '- [Usage](#usage)\n- [Usage](#usage-1)\n    - [Notes & Tips!](#notes--tips)\n- [Spaced   out](#spaced---out)\n- [Usage-1](#usage-1-1)\n- [Usage](#usage-2)\n- [???](#section)\n'
case('example-1',stdin=MD1,out=MO1)
case('example-2',stdin=MD2,out=MO2)
multi('example-3',[(['-l','2'],MD2,MO2.replace('    - [Notes & Tips!](#notes--tips)\n',''),0),(['-l','1'],'# A\n## A\n# A\n','- [A](#a)\n- [A](#a-2)\n',0),([], '### Deep\n#### Deeper\n','- [Deep](#deep)\n  - [Deeper](#deeper)\n',0)])
multi('example-4',[([], 'text\n#\n# \n','',0),([], '## A\n```\n# B\n','- [A](#a)\n',0)])
errors('example-5',[['-l','7'],['-l'],['-l','0'],['README.md']])
case('empty')
case('ordinary-text',stdin='no headings\nplain\n\n')
case('levels-one-through-six',stdin=''.join('#'*i+f' L{i}\n' for i in range(1,7)),out=''.join(' '*(2*(i-1))+f'- [L{i}](#l{i})\n' for i in range(1,7)))
case('minimum-appears-later',stdin='#### High\n## Low\n### Middle\n',out='    - [High](#high)\n- [Low](#low)\n  - [Middle](#middle)\n')
case('suffix-reservations',stdin='# A-1\n# A\n# A\n# A-2\n# A\n',out='- [A-1](#a-1)\n- [A](#a)\n- [A](#a-2)\n- [A-2](#a-2-1)\n- [A](#a-3)\n')
case('hidden-headings-reserve-slugs',['-l','2'],'###### A\n### A\n## A\n# A-3\n## A\n','  - [A](#a-2)\n- [A-3](#a-3)\n  - [A](#a-4)\n')
case('fallback-and-collisions',stdin='# !!!\n## ???\n# section\n# Section-1\n',out='- [!!!](#section)\n  - [???](#section-1)\n- [section](#section-2)\n- [Section-1](#section-1-1)\n')
case('spaces-trimmed-not-merged',stdin='##    A  B   \n## A B\n',out='- [A  B](#a--b)\n- [A B](#a-b)\n')
case('inline-text-kept',stdin='# [Link](dest) *Bold* `code` A_B 99!\n',out='- [[Link](dest) *Bold* `code` A_B 99!](#linkdest-bold-code-a_b-99)\n')
case('unclosed-fence',stdin='# Before\n```python\n# Hidden\n## Hidden too',out='- [Before](#before)\n')
case('fence-prefix-arbitrary-suffix',stdin='````lang\n# Hidden\n```closing anything\n# Seen\n',out='- [Seen](#seen)\n')
case('fence-heading-does-not-reserve',stdin='```\n# A\n```\n# A\n# A\n',out='- [A](#a)\n- [A](#a-1)\n')
case('heading-start-grammar',stdin='#No\n # No\n####### No\n## \n#\n##\tNo\n# Yes\n',out='- [Yes](#yes)\n')
case('crlf-final-heading',stdin='## A\r\n### B\r',out='- [A](#a)\n  - [B](#b)\n')
case('numbered-base-collisions',stdin='# X\n# X\n# X-1\n# X-1\n# X\n',out='- [X](#x)\n- [X](#x-1)\n- [X-1](#x-1-1)\n- [X-1](#x-1-2)\n- [X](#x-2)\n')
case('explicit-level-six',['-l','6'],'###### Last\n# First\n','          - [Last](#last)\n- [First](#first)\n')
case('all-headings-filtered',['-l','1'],'## A\n###### B\n')
errors('usage-level-grammar',[['-l',x] for x in ['','01','+1','-1','1 ',' 1','10','x']])
errors('usage-shape',[['-l1'],['-L','2'],['-l','2','-l','3'],['--'],[''],['-l','2','file']])
case('million-byte-document',stdin='x'*999996+'\n# A',out='- [A](#a)\n')

TASK = '07-parking'
case('example-1',['2'],'IN AB12 0\nIN CD34 5\nIN EF56 10\nOUT AB12 20\nIN EF56 20\nWHERE EF56\nSTATUS\nOUT CD34 70\nSTATUS\n','OK 1\nOK 2\nFULL\nFEE 2.50\nOK 1\nSPOT 1\nfree=0 parked=2 revenue=2.50\nFEE 5.00\nfree=1 parked=1 revenue=7.50\n')
case('example-2',['1'],'IN A 100\nIN B 90\nOUT A 115\nIN B 115\nOUT B 1556\nOUT B 1600\nIN A 0100\nOUT A 1640\nSTATUS\n','OK 1\nERR bad time\nFEE 0.00\nOK 1\nFEE 22.50\nERR not parked\nERR bad time\nERR not parked\nfree=1 parked=0 revenue=22.50\n')
case('example-3',['5'],'IN Z 0\nIN Y 0\nOUT Z 600\nIN Z 600\nOUT Y 1440\nOUT Z 3540\nSTATUS\n','OK 1\nOK 2\nFEE 20.00\nOK 1\nFEE 20.00\nFEE 42.50\nfree=5 parked=0 revenue=82.50\n')
case('example-4',['3'],'in A 1\nIN a 1\nIN A  1\nIN ABCDEFGHI 1\nIN A 12345678\nIN A\nWHERE\nSTATUS \n\nIN A 1\nIN A 2\nWHERE B\nOUT B 3\n','ERR bad command\n'*9+'OK 1\nERR already parked\nERR not parked\nERR not parked\n')
errors('example-5',[[],['0'],['1001'],['x'],['5','6']])
case('empty',['1'])
FEES = [(0,'0.00'),(1,'0.00'),(14,'0.00'),(15,'0.00'),(16,'2.50'),(59,'2.50'),(60,'2.50'),(61,'5.00'),(119,'5.00'),(120,'5.00'),(121,'7.50'),(419,'17.50'),(420,'17.50'),(421,'20.00'),(480,'20.00'),(481,'20.00'),(600,'20.00'),(1439,'20.00'),(1440,'20.00'),(1441,'22.50'),(1455,'22.50'),(1500,'22.50'),(1501,'25.00'),(2880,'40.00'),(2940,'42.50')]
multi('fee-boundaries',[(['1'],f'IN A 0\nOUT A {duration}\nSTATUS\n',f'OK 1\nFEE {fee}\nfree=1 parked=0 revenue={fee}\n',0) for duration,fee in FEES])
case('lowest-of-multiple-holes',['4'],'IN A 0\nIN B 0\nIN C 0\nIN D 0\nOUT C 0\nOUT A 0\nIN E 0\nIN F 0\nWHERE B\nWHERE D\nWHERE E\nWHERE F\n','OK 1\nOK 2\nOK 3\nOK 4\nFEE 0.00\nFEE 0.00\nOK 1\nOK 3\nSPOT 2\nSPOT 4\nSPOT 1\nSPOT 3\n')
case('duplicate-before-full',['1'],'IN A 0\nIN A 0\nIN B 0\nSTATUS\n','OK 1\nERR already parked\nFULL\nfree=0 parked=1 revenue=0.00\n')
case('duplicate-advances-clock',['1'],'IN A 0\nIN A 100\nOUT A 99\nOUT A 100\n','OK 1\nERR already parked\nERR bad time\nFEE 5.00\n')
case('full-advances-clock',['1'],'IN A 0\nIN B 100\nOUT A 99\nOUT A 100\n','OK 1\nFULL\nERR bad time\nFEE 5.00\n')
case('missing-out-advances-clock',['1'],'OUT X 100\nIN A 99\nIN A 100\n','ERR not parked\nERR bad time\nOK 1\n')
case('bad-time-precedes-plate-check',['1'],'IN A 10\nIN A 9\nOUT X 9\nWHERE A\nOUT A 10\n','OK 1\nERR bad time\nERR bad time\nSPOT 1\nFEE 0.00\n')
case('malformed-command-does-not-advance',['1'],'IN a 100\nIN A  100\nOUT A 12345678\nIN A 0\nOUT A 16\n','ERR bad command\n'*3+'OK 1\nFEE 2.50\n')
case('invalid-plate-preserves-state',['1'],'IN A 0\nOUT a 100\nOUT ABCDEFGHI 100\nWHERE A\nOUT A 15\n','OK 1\nERR bad command\nERR bad command\nSPOT 1\nFEE 0.00\n')
case('reenter-is-new-stay',['1'],'IN A 0\nOUT A 60\nIN A 60\nOUT A 75\nIN A 75\nOUT A 136\nSTATUS\n','OK 1\nFEE 2.50\nOK 1\nFEE 0.00\nOK 1\nFEE 5.00\nfree=1 parked=0 revenue=7.50\n')
case('leading-zero-equal-times',['0002'],'IN 00000000 0000000\nIN Z9 0000000\nOUT 00000000 0000000\nWHERE Z9\nSTATUS\n','OK 1\nOK 2\nFEE 0.00\nSPOT 2\nfree=1 parked=1 revenue=0.00\n')
case('queries-do-not-change-clock',['1'],'IN A 50\nWHERE A\nWHERE B\nSTATUS\nOUT A 50\n','OK 1\nSPOT 1\nERR not parked\nfree=0 parked=1 revenue=0.00\nFEE 0.00\n')
case('maximum-time-and-large-fee',['1'],'IN A 0\nOUT A 9999999\nSTATUS\nIN A 9999999\nOUT A 9999999\n','OK 1\nFEE 138900.00\nfree=1 parked=0 revenue=138900.00\nOK 1\nFEE 0.00\n')
case('thousand-spots',['1000'],''.join(f'IN A{i} 0\n' for i in range(1000))+'IN FULL 0\nOUT A0 0\nIN NEW 0\nWHERE A999\nSTATUS\n', ''.join(f'OK {i}\n' for i in range(1,1001))+'FULL\nFEE 0.00\nOK 1\nSPOT 1000\nfree=0 parked=1000 revenue=0.00\n')
case('crlf-final-line',['1'],b'IN A 0\r\n\r\nWHERE A\r\nOUT A 16\r', 'OK 1\nERR bad command\nSPOT 1\nFEE 2.50\n')
PARK_BAD = [' STATUS','STATUS  ','STATUS extra','WHERE A X','WHERE  A','WHERE A ','OUT A -1','OUT A +1','OUT A 1.0','IN A 1 ','IN A\t1','IN A 00000000','IN A_B 1','OUT A','FOO','']
case('strict-command-grammar',['1'],lines(PARK_BAD)+'STATUS\n','ERR bad command\n'*len(PARK_BAD)+'free=1 parked=0 revenue=0.00\n')
errors('usage-capacity-grammar',[[x] for x in ['','-1','+1','00001','1.0',' 1','1 ','10000','--']])
multi('lockstep-flush',[(['1'],'IN A 0\nSTATUS\nOUT A 1\n','OK 1\nfree=0 parked=1 revenue=0.00\n',None,2),(['1'],'STATUS\n','free=1 parked=0 revenue=0.00\n',0)])
case('hundred-thousand-commands',['1'],'STATUS\n'*100000,'free=1 parked=0 revenue=0.00\n'*100000)

TASK = '08-pubsub'
case('example-1',stdin='SUB ann news.sport\nSUB bob news.*\nSUB cy news.#\nPUB news.sport Goal!\nPUB news.weather Rain\nPUB news Extra\nPUB news.sport.uk Win\nPUB other Hi\nPOLL ann 10\nPOLL bob 1\nPOLL bob 5\nPOLL cy 10\nPOLL cy 10\n',out='OK\nOK\nOK\nDELIVERED 3\nDELIVERED 2\nDELIVERED 1\nDELIVERED 1\nDELIVERED 0\nMSGS 1 news.sport=Goal!\nMSGS 1 news.sport=Goal!\nMSGS 1 news.weather=Rain\nMSGS 3 news.weather=Rain news=Extra news.sport.uk=Win\nMSGS 0\n')
case('example-2',stdin='SUB dee a.#\nSUB dee a.b\nSUB dee a.#\nPUB a.b m1\nPUB a.c m2\nPUB a m3\nPUB a.b.c m4\nSTATS dee\nPOLL dee 2\nSTATS dee\nUNSUB dee a.#\nUNSUB dee a.#\nPUB a.c m5\nPUB a.b m6\nSTATS dee\nPOLL dee 9\nSTATS zed\nPOLL zed 1\n',out='OK\nOK\nERR already subscribed\nDELIVERED 1\nDELIVERED 1\nDELIVERED 1\nDELIVERED 1\nsubs=2 queued=3 dropped=1\nMSGS 2 a.c=m2 a=m3\nsubs=2 queued=1 dropped=1\nOK\nERR not subscribed\nDELIVERED 0\nDELIVERED 1\nsubs=1 queued=2 dropped=1\nMSGS 2 a.b.c=m4 a.b=m6\nsubs=0 queued=0 dropped=0\nMSGS 0\n')
case('example-3',stdin='SUB Ann x\nSUB ann x.#.y\nSUB ann #\nSUB ann *.#\nPUB a.* m\nPUB a hello world\nPUB a.b.c.d.e.f.g.h.i m\nPOLL ann 0\nPOLL ann 1000\nsub ann x\nSTATS\n\nPUB a\nPUB q x,y\nSUB ann a..b\n',out='ERR bad command\nERR bad command\nOK\nOK\n'+'ERR bad command\n'*11)
case('example-4',['3'],code=2)
case('empty')
case('hash-includes-single-topic',stdin='SUB a #\nPUB x 1\nPUB x.y 2\nPOLL a 999\n',out='OK\nDELIVERED 1\nDELIVERED 1\nMSGS 2 x=1 x.y=2\n')
case('star-exactly-one-segment',stdin='SUB a x.*\nPUB x one\nPUB x.y two\nPUB x.y.z three\nPOLL a 9\n',out='OK\nDELIVERED 0\nDELIVERED 1\nDELIVERED 0\nMSGS 1 x.y=two\n')
case('star-hash-minimum-depth',stdin='SUB a *.#\nSUB b x.*.#\nPUB x a\nPUB x.y b\nPUB x.y.z c\nPOLL a 9\nPOLL b 9\n',out='OK\nOK\nDELIVERED 1\nDELIVERED 2\nDELIVERED 2\nMSGS 3 x=a x.y=b x.y.z=c\nMSGS 2 x.y=b x.y.z=c\n')
TOP8 = '.'.join(['a'*16]*8)
PAT8 = '.'.join(['*']*7+['#'])
case('eight-maximal-segments',stdin=f'SUB abcdefghijklmnop {PAT8}\nPUB {TOP8} {"Z"*32}\nPOLL abcdefghijklmnop 999\n',out=f'OK\nDELIVERED 1\nMSGS 1 {TOP8}={"Z"*32}\n')
case('literal-hash-zero-suffix',stdin='SUB a a.b.#\nPUB a x\nPUB a.b y\nPUB a.b.c z\nPUB a.c w\nPOLL a 9\n',out='OK\nDELIVERED 0\nDELIVERED 1\nDELIVERED 1\nDELIVERED 0\nMSGS 2 a.b=y a.b.c=z\n')
case('overlap-delivers-once',stdin='SUB a #\nSUB a a.#\nSUB a a.*\nSUB a a.b\nPUB a.b x\nSTATS a\nPOLL a 9\n',out='OK\n'*4+'DELIVERED 1\nsubs=4 queued=1 dropped=0\nMSGS 1 a.b=x\n')
case('drop-oldest-and-poll-order',stdin='SUB a x\n'+''.join(f'PUB x m{i}\n' for i in range(1,7))+'STATS a\nPOLL a 1\nPOLL a 1\nPOLL a 1\nPOLL a 1\nSTATS a\n',out='OK\n'+'DELIVERED 1\n'*6+'subs=1 queued=3 dropped=3\nMSGS 1 x=m4\nMSGS 1 x=m5\nMSGS 1 x=m6\nMSGS 0\nsubs=1 queued=0 dropped=3\n')
case('unsub-retains-queue-and-drops',stdin='SUB a x\n'+'PUB x y\n'*4+'UNSUB a x\nPUB x z\nSTATS a\nPOLL a 9\nSTATS a\n',out='OK\n'+'DELIVERED 1\n'*4+'OK\nDELIVERED 0\nsubs=0 queued=3 dropped=1\nMSGS 3 x=y x=y x=y\nsubs=0 queued=0 dropped=1\n')
case('unsub-compares-exact-pattern',stdin='SUB a a.#\nUNSUB a a.*\nSUB a a.#\nSTATS a\n',out='OK\nERR not subscribed\nERR already subscribed\nsubs=1 queued=0 dropped=0\n')
case('resubscribe-without-retention',stdin='PUB a old\nSUB c a\nPOLL c 1\nUNSUB c a\nPUB a missed\nSUB c a\nPUB a new\nPOLL c 2\n',out='DELIVERED 0\nOK\nMSGS 0\nOK\nDELIVERED 0\nOK\nDELIVERED 1\nMSGS 1 a=new\n')
case('implicit-clients',stdin='POLL zero 1\nUNSUB zero #\nSTATS zero\nSTATS other\n',out='MSGS 0\nERR not subscribed\nsubs=0 queued=0 dropped=0\nsubs=0 queued=0 dropped=0\n')
BAD_CLIENTS = ['A','1a','a_b','a'*17,'-a']
case('client-grammar',stdin=lines([f'SUB {c} x' for c in BAD_CLIENTS])+ 'SUB a0 x\nSTATS a0\n',out='ERR bad command\n'*5+'OK\nsubs=1 queued=0 dropped=0\n')
BAD_TOPICS = ['A','a..b','.a','a.','a_b','a-b','a'*17,'.'.join(['a']*9),'a.#','*']
case('topic-and-pattern-grammar',stdin=lines([f'PUB {t} x' for t in BAD_TOPICS]+['SUB a a.#.b','SUB a a..b','SUB a a*','SUB a ##','SUB a '+'.'.join(['*']*9)])+'STATS a\n',out='ERR bad command\n'*15+'subs=0 queued=0 dropped=0\n')
case('text-alphabet-and-length',stdin='SUB a q\nPUB q A0_.!?-\nPUB q '+ 'x'*32+'\n'+lines(['PUB q '+ 'x'*33,'PUB q a,b','PUB q a=b','PUB q a/b','PUB q a b','PUB q '])+'POLL a 3\n',out='OK\nDELIVERED 1\nDELIVERED 1\n'+'ERR bad command\n'*6+'MSGS 2 q=A0_.!?- q='+'x'*32+'\n')
case('poll-max-grammar',stdin=lines(['POLL a '+x for x in ['0','00','01','0001','1000','+1','-1','1.0']])+ 'POLL a 999\n',out='ERR bad command\n'*8+'MSGS 0\n')
BROKER_BAD = ['',' SUB a x','SUB  a x','SUB a x ','SUB a','UNSUB a','PUB x','POLL a','STATS','STATS a b','STATS a ','stats a','SUB a\tx']
case('strict-command-syntax',stdin=lines(BROKER_BAD)+'STATS a\n',out='ERR bad command\n'*len(BROKER_BAD)+'subs=0 queued=0 dropped=0\n')
case('crlf-and-final-command',stdin='SUB a x\r\nPUB x y\r\nPOLL a 1\r',out='OK\nDELIVERED 1\nMSGS 1 x=y\n')
case('thousand-clients',stdin=''.join(f'SUB a{i} #\n' for i in range(1000))+'PUB a x\nSTATS a999\nPOLL a0 1\n',out='OK\n'*1000+'DELIVERED 1000\nsubs=1 queued=1 dropped=0\nMSGS 1 a=x\n')
case('hundred-thousand-commands',stdin='SUB a x\n'+'PUB x y\n'*99997+'STATS a\nPOLL a 999\n',out='OK\n'+'DELIVERED 1\n'*99997+'subs=1 queued=3 dropped=99994\nMSGS 3 x=y x=y x=y\n')
multi('lockstep-flush-and-reset',[([], 'SUB a x\nPUB x y\nPOLL a 1\n','OK\nDELIVERED 1\n',None,2),([], 'STATS a\nPOLL a 1\n','subs=0 queued=0 dropped=0\nMSGS 0\n',0)])

def code36(n):
    # Numeric formatting only, for explicit id boundary fixtures.
    alphabet = '0123456789abcdefghijklmnopqrstuvwxyz'
    result = ''
    while n:
        n, digit = divmod(n,36)
        result = alphabet[digit]+result
    return result or '0'

TASK = '09-shorten'
case('example-1',['data'],'PUT https://example.com/a\nPUT http://x.org/?q=1&r=2\nGET 1\nGET 1\nGET 2\nHITS 1\nHITS 3\nDEL 2\nGET 2\nDEL 2\nPUT https://example.com/a\nINFO\n','CODE 1\nCODE 2\nURL https://example.com/a\nURL https://example.com/a\nURL http://x.org/?q=1&r=2\nHITS 2\nERR not found\nOK\nERR not found\nERR not found\nCODE 3\nlinks=2 next=4 records=7\n')
multi('example-2',[(['d'],'PUT u1\nPUT u2\nGET 2\nDEL 1\n','CODE 1\nCODE 2\nURL u2\n',None,3),(['d'],'INFO\nHITS 2\nGET 1\nPUT u4\n','links=2 next=3 records=3\nHITS 1\nURL u1\nCODE 3\n',0)])
multi('example-3',[(['d'],'INFO\nHITS 1\nGET 2\nINFO\n','links=2 next=3 records=4\nHITS 2\nURL b.com\nlinks=2 next=3 records=5\n',0),(['d'],'INFO\nGET 2\n','links=2 next=3 records=5\nURL b.com\n',0)],{'d/journal':'1 P a.com\n2 H 1\n3 P b.com\n4 H 1\n5 D 2'})
multi('example-4',[(['gap'],'INFO\nPUT c.com\n','links=1 next=2 records=2\nCODE 2\n',0),(['inconsistent'],'INFO\nGET 1\nGET 2\n','links=0 next=2 records=2\nERR not found\nERR not found\n',0)],{'gap/journal':'1 P a.com\n2 H 1\n4 P b.com\n5 H 1\n','inconsistent/journal':'1 P a.com\n2 D 1\n3 H 1\n4 P b.com\n'})
multi('example-5', [([], '', '',2),(['a','b'],'','',2),(['f'],'','',1),(['e'],'PUT\nPUT a b\nput x\nGET A1\nGET 123456789\n\nINFO \nGET 0\n','ERR bad command\n'*7+'ERR not found\n',0)],{'f':'regular file'})
case('empty-run',['d'])
multi('duplicates-deletes-and-normal-restart',[(['d'],'PUT same\nPUT same\nDEL 1\nPUT same\nGET 2\nINFO\n','CODE 1\nCODE 2\nOK\nCODE 3\nURL same\nlinks=2 next=4 records=5\n',0),(['d'],'INFO\nGET 1\nHITS 2\nHITS 3\nDEL 2\nDEL 3\nPUT same\nINFO\n','links=2 next=4 records=5\nERR not found\nHITS 1\nHITS 0\nOK\nOK\nCODE 4\nlinks=1 next=5 records=8\n',0)])
multi('base36-boundaries',[(['d'],'INFO\nGET 9\nGET a\nGET z\nGET 10\nGET zz\nPUT new\nINFO\n','links=1295 next=100 records=1295\nURL u\nURL u\nURL u\nURL u\nURL u\nCODE 100\nlinks=1296 next=101 records=1301\n',0),(['d'],'HITS zz\nHITS 100\nINFO\n','HITS 1\nHITS 0\nlinks=1296 next=101 records=1301\n',0)],{'d/journal':''.join(f'{i} P u\n' for i in range(1,1296))})
case('code-grammar-and-canonical-code',['d'],'PUT u\n'+lines([f'{op} {c}' for op in ['GET','HITS','DEL'] for c in ['0','01','00000001','zzzzzzzz']])+lines(['GET A','GET 123456789','GET a_','HITS -1'])+'INFO\n','CODE 1\n'+'ERR not found\n'*12+'ERR bad command\n'*4+'links=1 next=2 records=1\n')
URL200 = ''.join(chr(i) for i in range(33,127))*2+'!'*12
case('url-alphabet-and-length',['d'],b'PUT !\nPUT '+URL200.encode()+b'\nPUT '+b'x'*201+b'\nPUT a b\nPUT a\tb\nPUT \x7f\nGET 1\nGET 2\nINFO\n','CODE 1\nCODE 2\n'+'ERR bad command\n'*4+'URL !\nURL '+URL200+'\nlinks=2 next=3 records=4\n')
SHORT_BAD = ['',' INFO','INFO ','INFO x','put u','PUT','PUT  u','PUT u ','GET','GET  1','DEL 1 x','HITS 1 ','GET\t1','UNKNOWN']
case('strict-command-syntax',['d'],lines(SHORT_BAD)+'INFO\n','ERR bad command\n'*len(SHORT_BAD)+'links=0 next=1 records=0\n')
multi('directory-paths-and-crlf',[(['parent/child'],'PUT u\r\nGET 1\r\nHITS 1\r','CODE 1\nURL u\nHITS 1\n',0),(['a b'],'INFO\n','links=0 next=1 records=0\n',0),(['-'],'PUT dash\n','CODE 1\n',0),(['parent/child'],'INFO\n','links=1 next=2 records=2\n',0)],{'parent':None})
errors('unusable-directories',[['missing/child'],['file/child'],['file']],1,{'file':'x'})
multi('kill-after-put',[(['d'],'PUT one\nPUT unsent\n','CODE 1\n',None,1),(['d'],'INFO\nHITS 1\nGET 2\nPUT next\n','links=1 next=2 records=1\nHITS 0\nERR not found\nCODE 2\n',0)])
multi('kill-after-hit',[(['d'],'PUT one\nGET 1\nGET 1\nDEL 1\n','CODE 1\nURL one\nURL one\n',None,3),(['d'],'INFO\nHITS 1\nGET 1\nHITS 1\n','links=1 next=2 records=3\nHITS 2\nURL one\nHITS 3\n',0)])
multi('kill-after-delete',[(['d'],'PUT a\nPUT b\nDEL 1\nPUT unsent\n','CODE 1\nCODE 2\nOK\n',None,3),(['d'],'INFO\nGET 1\nHITS 2\nPUT c\n','links=1 next=3 records=3\nERR not found\nHITS 0\nCODE 3\n',0)])
multi('kill-after-reads-and-errors',[(['d'],'INFO\nHITS 1\nGET 2\nDEL 2\nBAD\nPUT unsent\n','links=1 next=2 records=2\nHITS 1\nERR not found\nERR not found\nERR bad command\n',None,5),(['d'],'INFO\nHITS 1\nPUT b\n','links=1 next=2 records=2\nHITS 1\nCODE 2\n',0)],{'d/journal':'1 P a\n2 H 1\n'})
multi('successive-kill-restarts',[(['d'],'PUT a\nGET 1\nDEL 1\n','CODE 1\nURL a\n',None,2),(['d'],'INFO\nDEL 1\nPUT b\nGET 2\n','links=1 next=2 records=2\nOK\nCODE 2\n',None,3),(['d'],'INFO\nGET 1\nHITS 2\nGET 2\nINFO\n','links=1 next=3 records=4\nERR not found\nHITS 0\nURL b\nlinks=1 next=3 records=5\n',0)])
multi('torn-first-record',[(['d'],'INFO\nPUT real\n','links=0 next=1 records=0\nCODE 1\n',0),(['d'],'INFO\nGET 1\n','links=1 next=2 records=1\nURL real\n',0)],{'d/journal':'1 P phantom'})
BAD_SEQS = ['1 P bad\n','3 P bad\n','0 P bad\n','02 P bad\n','+2 P bad\n','1000000000 P bad\n','2.0 P bad\n']
SEQ_SETUP = {f'd{i}/journal':'1 P good\n'+bad+'3 P ignored\n' for i,bad in enumerate(BAD_SEQS)}
multi('sequence-numbers-stop-prefix',[step for i in range(len(BAD_SEQS)) for step in [([f'd{i}'],'INFO\nPUT new\nINFO\n','links=1 next=2 records=1\nCODE 2\nlinks=2 next=3 records=2\n',0),([f'd{i}'],'INFO\nGET 2\nGET 3\n','links=2 next=3 records=2\nURL new\nERR not found\n',0)]],SEQ_SETUP)
INCONSISTENT = [('1 P a\n2 H 2\n3 P ignored\n','links=1 next=2 records=1\nHITS 0\n'),('1 P a\n2 D 2\n3 P ignored\n','links=1 next=2 records=1\nHITS 0\n'),('1 P a\n2 D 1\n3 D 1\n4 P ignored\n','links=0 next=2 records=2\nERR not found\n'),('1 P a\n2 D 1\n3 H 1\n4 P ignored\n','links=0 next=2 records=2\nERR not found\n'),('1 P a\n2 H 01\n3 P ignored\n','links=1 next=2 records=1\nHITS 0\n')]
multi('inconsistent-records', [([f'd{i}'],'INFO\nHITS 1\n',out,0) for i,(_,out) in enumerate(INCONSISTENT)],{f'd{i}/journal':data for i,(data,_) in enumerate(INCONSISTENT)})
BAD_RECORDS = ['\n','2 X a\n','2  H 1\n','2 H 1 \n','2 H A\n','2 P \n','2 P a b\n','2 P '+ 'x'*201+'\n','2 P a\r\n','2 P a\t\n','2 H 123456789\n','2 P a\x00b\n',' 2 H 1\n']
multi('malformed-records-stop-prefix',[step for i in range(len(BAD_RECORDS)) for step in [([f'd{i}'],'INFO\nPUT b\n','links=1 next=2 records=1\nCODE 2\n',0),([f'd{i}'],'INFO\nGET 2\n','links=2 next=3 records=2\nURL b\n',0)]],{f'd{i}/journal':'1 P a\n'+bad+'3 P ignored\n' for i,bad in enumerate(BAD_RECORDS)})
multi('invalid-tail-replaced-before-killed-append',[(['d'],'INFO\nGET 1\nPUT unsent\n','links=1 next=2 records=1\nURL a\n',None,2),(['d'],'INFO\nHITS 1\nGET 2\nPUT b\n','links=1 next=2 records=2\nHITS 1\nERR not found\nCODE 2\n',0),(['d'],'INFO\nGET 2\n','links=2 next=3 records=3\nURL b\n',0)],{'d/journal':'1 P a\n9 P invalid\n3 P ignored\n'})
multi('hundred-thousand-records',[(['d'],'INFO\nHITS 1\n','links=1 next=2 records=100000\nHITS 99999\n',0),(['d'],'HITS 1\nINFO\n','HITS 99999\nlinks=1 next=2 records=100000\n',0)],{'d/journal':'1 P a\n'+''.join(f'{i} H 1\n' for i in range(2,100001))})
multi('ten-thousand-commands',[(['d'],'PUT a\n'+'GET 1\n'*9998+'INFO\n','CODE 1\n'+'URL a\n'*9998+'links=1 next=2 records=9999\n',0),(['d'],'HITS 1\nINFO\n','HITS 9998\nlinks=1 next=2 records=9999\n',0)])

TASK = '10-elevator'
case('example-1',['5'],'0 0 3\n','1 board=0 arrive=4\nmoves=3 stops=2 finish=4 total_wait=0\n')
case('example-2',['5'],'0 2 0\n1 1 4\n','1 board=3 arrive=11\n2 board=1 arrive=6\nmoves=8 stops=4 finish=11 total_wait=3\n')
case('example-3',['6'],'0 3 1\n0 1 3\n2 0 4\n5 4 0\n','1 board=4 arrive=10\n2 board=1 arrive=4\n3 board=12 arrive=17\n4 board=6 arrive=12\nmoves=12 stops=6 finish=17 total_wait=16\n')
multi('example-4',[(['5'],'0 4 0\n0 2 0\n','1 board=5 arrive=10\n2 board=2 arrive=10\nmoves=8 stops=3 finish=10 total_wait=7\n',0),(['5'],'0 0 2\n\n10 1 0\r\n10 3 4','1 board=0 arrive=3\n2 board=17 arrive=19\n3 board=11 arrive=13\nmoves=8 stops=6 finish=19 total_wait=8\n',0),(['2'],'','moves=0 stops=0 finish=0 total_wait=0\n',0)])
multi('example-5',[(['2'],s,'',1) for s in ['0 0 0\n','0 0 2\n','5 0 1\n4 1 0\n','0 0  1\n']]+[([s],'','',2) for s in ['1','101']]+[([], '', '',2)])
case('only-ignored-lines',['2'],'\n  \n\r\n   \r','moves=0 stops=0 finish=0 total_wait=0\n')
case('simultaneous-same-destination',['3'],'0 0 2\n'*3,lines([f'{i} board=0 arrive=3' for i in range(1,4)])+'moves=2 stops=2 finish=3 total_wait=0\n')
case('several-destinations',['4'],'0 0 1\n0 0 2\n0 0 3\n','1 board=0 arrive=2\n2 board=0 arrive=4\n3 board=0 arrive=6\nmoves=3 stops=4 finish=6 total_wait=0\n')
case('board-opposite-direction',['5'],'0 0 4\n0 2 0\n','1 board=0 arrive=6\n2 board=3 arrive=11\nmoves=8 stops=4 finish=11 total_wait=3\n')
case('new-appearance-causes-consecutive-stop',['3'],'0 0 2\n1 0 1\n','1 board=0 arrive=5\n2 board=1 arrive=3\nmoves=2 stops=4 finish=5 total_wait=0\n')
case('arrival-and-boarding-share-stop',['3'],'0 0 2\n3 2 0\n','1 board=0 arrive=3\n2 board=3 arrive=6\nmoves=4 stops=3 finish=6 total_wait=0\n')
case('direction-survives-stop',['5'],'0 2 0\n0 4 3\n','1 board=2 arrive=11\n2 board=5 arrive=7\nmoves=8 stops=4 finish=11 total_wait=7\n')
case('turn-after-farthest-target',['5'],'0 0 4\n2 1 0\n','1 board=0 arrive=6\n2 board=2 arrive=11\nmoves=8 stops=4 finish=11 total_wait=0\n')
case('idle-chooses-nearest-below',['5'],'0 0 2\n10 1 0\n10 4 3\n','1 board=0 arrive=3\n2 board=11 arrive=13\n3 board=18 arrive=20\nmoves=9 stops=6 finish=20 total_wait=9\n')
case('future-requests-not-targets',['5'],'0 0 2\n100 4 0\n','1 board=0 arrive=3\n2 board=102 arrive=107\nmoves=8 stops=4 finish=107 total_wait=2\n')
case('maximum-time-and-floors',['100'],'999999 99 0\n','1 board=1000098 arrive=1000198\nmoves=198 stops=2 finish=1000198 total_wait=99\n')
case('leading-zero-values',['002'],'000000 000 001\r','1 board=0 arrive=2\nmoves=1 stops=2 finish=2 total_wait=0\n')
case('top-floor-direct',['100'],'0 0 99\n','1 board=0 arrive=100\nmoves=99 stops=2 finish=100 total_wait=0\n')
BAD_REQUESTS = [' 1 0 1','1 0 1 ','1  0 1','1\t0 1','1 0','1 0 1 0','-1 0 1','+1 0 1','1000000 0 1','1 0000 1','1 0 0001','1.0 0 1','\t','1 0 1\r\r']
multi('invalid-format-atomicity',[(['2'],'0 0 1\n'+s+'\n','',1) for s in BAD_REQUESTS])
multi('invalid-floors',[(['5'],s,'',1) for s in ['0 5 0\n','0 0 5\n','0 1 1\n','0 001 1\n','0 999 0\n','0 0 1\n1 4 4\n']])
multi('time-order-with-ignored-lines',[(['2'],'10 0 1\n\n \n9 1 0\n','',1),(['2'],'000010 0 1\n000009 1 0\n','',1)])
errors('usage-floor-grammar',[[v] for v in ['','0','001','+2','-2','0002','2.0',' 2','2 ','1000','--']])
errors('usage-argument-count',[[],['2','3'],['2','-x']])
case('ten-thousand-passengers',['2'],'0 0 1\n'*10000,''.join(f'{i} board=0 arrive=2\n' for i in range(1,10001))+'moves=1 stops=2 finish=2 total_wait=0\n')
case('wait-summed-per-passenger',['2'],'0 1 0\n'*3,''.join(f'{i} board=1 arrive=3\n' for i in range(1,4))+'moves=2 stops=2 finish=3 total_wait=3\n')

if __name__ == '__main__':
    for task in sorted(ROOT.glob('[0-9][0-9]-*')):
        count = len(list((task/'cases').iterdir()))
        assert count == 25, (task.name, count)
        print(f'{task.name}: {count} cases')
