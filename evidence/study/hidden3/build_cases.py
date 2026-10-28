"""Spec-derived acceptance fixtures. Never import, execute, or query references.

Expected bytes are literal worked results or arithmetic/combinatorial constructions
with deliberately simple closed-form answers, not a duplicate general solver.
"""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parent
TASK=''

def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(value if isinstance(value,bytes) else value.encode('utf-8'))

def base_for(name,setup):
    base=ROOT/TASK/'cases'/name
    if base.exists(): shutil.rmtree(base)
    base.mkdir(parents=True)
    for path,value in (setup or {}).items(): put(base/'setup'/path,value)
    return base

def run_files(base,args,stdin,out,code):
    put(base/'cmd',''.join(x+'\n' for x in args))
    if stdin: put(base/'stdin',stdin)
    put(base/'expected_stdout',out)
    if code is not None: put(base/'expected_exit',str(code)+'\n')

def case(name,args=(),stdin='',out='',code=0,setup=None):
    run_files(base_for(name,setup),args,stdin,out,code)

def multi(name,steps,setup=None):
    base=base_for(name,setup); manifest=[]
    for i,step in enumerate(steps,1):
        args,stdin,out,code,*kill=step
        label='step-'+str(i)
        manifest.append(label+(' kill-after='+str(kill[0]) if kill else ''))
        run_files(base/label,args,stdin,out,None if kill else code)
    put(base/'steps','\n'.join(manifest)+'\n')

def errors(name,variants,code=2,setup=None):
    multi(name,[(a,'','',code) for a in variants],setup)

def protocol(name,stdin,out,args=(),setup=None):
    case(name,args,stdin,out,setup=setup)

TASK='01-wrap'
FOX='The quick brown fox jumps over the lazy dog.\n'
multi('example-1',[(['-w','16'],FOX,'The quick brown\nfox jumps over\nthe lazy dog.\n',0),(['-w','16','-j'],FOX,'The  quick brown\nfox  jumps  over\nthe lazy dog.\n',0)])
case('example-2',['-w','10','-i','2'],'  Hello   world, this is\nwrap.\n\n   \nSupercalifragilistic is long\n','  Hello\nworld,\nthis is\nwrap.\n\n  Supercalifragilistic\nis long\n')
case('example-3',['-j','-w','12'],'a bb ccc dddd eeeee ffffff ggggggggggggg hi\n','a   bb   ccc\ndddd   eeeee\nffffff\nggggggggggggg\nhi\n')
multi('example-4',[([], '\n   \n\n','',0),([], 'one\ntwo  three','one two three\n',0)])
multi('example-5',[(a,'','',2) for a in [['-w','0'],['-w','10','-i','10'],['-w','10','-w','12'],['-x'],['notes.txt'],['-w']]]+[([], 'ok line\nhas\ta tab\n','',1)])
case('empty')
case('blank-crlf',stdin=' \r\n\r\n   \r')
case('crlf-final-line',stdin='one\r\ntwo   three\r',out='one two three\n')
case('width-one',['-w','1'],'a bb c\n','a\nbb\nc\n')
case('indent-width-minus-one',['-i','0004','-w','0005'],'a b c d ef\n','    a\nb c d\nef\n')
case('indent-every-paragraph',['-w','8','-i','2'],'\n a b c d e\n\n\n f g h i\n\n','  a b c\nd e\n\n  f g h\ni\n')
case('justify-left-remainder',['-w','10','-j'],'aa b c d eeee f\n','aa  b  c d\neeee f\n')
case('justify-indented',['-i','3','-j','-w','12'],'a b c d e f g h i\n','   a b c d e\nf g h i\n')
case('last-line-unpadded',['-w','10','-j','-i','2'],'a bb\n','  a bb\n')
case('exact-width',['-w','5'],'aa bb c\n','aa bb\nc\n')
case('overlong-first-and-middle',['-w','4','-i','1','-j'],'abcdef x abcde z\n',' abcdef\nx\nabcde\nz\n')
case('punctuation-is-word',stdin='!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~\n',out='!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~\n')
multi('invalid-byte-atomicity',[([],b'good\n\n' + bad + b'\n','',1) for bad in [b'a\tb',b'\x00',b'\x1f',b'\x7f',b'\x80',b'a\rb',b'a\r\r']])
errors('usage-option-spellings',[['-w20'],['--width','20'],['-ij'],['--'],[''],['-W','2']])
errors('usage-duplicates',[['-j','-j'],['-i','0','-i','1'],['-w','1','-w','1']])
errors('usage-width-grammar',[['-w',s] for s in ['','-1','+1','1001','00001','1.0',' 2','2 ']])
errors('usage-indent-grammar',[['-i',s] for s in ['','-1','+1','10000','1.0','72']]+[['-i'],['-w','-j']])
case('usage-before-invalid-input',['-x'],b'\x00\t\xff','',2)
case('maximum-width',['-w','1000','-i','999'],'x y\n',' '*999+'x\ny\n')
# Exactly one million bytes, under either decimal or binary reading of 1 MB.
case('input-size-boundary',['-w','1000'],'a '*499999+'a\n',(' '.join(['a']*500)+'\n')*1000)

TASK='02-radix'
case('example-1',['-t','16','255','-10','0'],out='ff\n-a\n0\n')
multi('example-2',[(['-f','2','-g','3','1111101000'],'','1_000\n',0),(['-f','36','-t','16','-u','zz'],'','50F\n',0),(['-t','2','-w','8','-g','4','5','-3'],'','0000_0101\n-0000_0011\n',0)])
case('example-3',['1000000','-g','3','-t','8','-t','10','9223372036854775807'],out='1_000_000\n9_223_372_036_854_775_807\n')
case('example-4',['-t','16','12','1x','-0','9223372036854775807','9223372036854775808','-','+5'],out='c\n0\n7fffffffffffffff\n',code=1)
errors('example-5',[[],['-t','37','5'],['-t','1','5'],['-g','0','5'],['5','-f'],['-u'],['12','-t','x']])
case('zero-normalization',['-t','36','0','-0','000','-000'],out='0\n'*4)
case('mixed-case-base36',['-f','36','-t','10','Z','z','aB','-Ab'],out='35\n35\n371\n-371\n')
DIGITS='0123456789abcdefghijklmnopqrstuvwxyz'
multi('all-base-boundaries', [step for b in range(2,37) for step in [(['-f',str(b),DIGITS[b-1].upper(),'10'],'',str(b-1)+'\n'+str(b)+'\n',0), (['-t',str(b),str(b),str(b-1)],'','10\n'+DIGITS[b-1]+'\n',0)]])
case('digit-boundary',['-f','2','0','1','10','2','102','01'],out='0\n1\n2\n1\n',code=1)
case('range-endpoints',['9223372036854775807','-9223372036854775807','-9223372036854775808','9223372036854775808'],out='9223372036854775807\n-9223372036854775807\n',code=1)
case('binary-63-bit',['-f','2','-t','16','1'*63,'1'+'0'*63],out='7fffffffffffffff\n',code=1)
case('hex-range',['-f','16','7FFFFFFFFFFFFFFF','-7fffffffffffffff','8000000000000000','-ff','--','-5'],out='9223372036854775807\n-9223372036854775807\n-255\n-5\n',code=1)
case('invalid-value-lexemes',['','--','-','+0','0x10','1_0','1.0',' 1','1 ','--1','-ff','5'],out='5\n',code=1)
case('options-after-values',['15','-t','16','16','-u','-w','4','-g','2'],out='00_0F\n00_10\n')
case('repeat-all-options',['-f','2','-t','2','-w','2','-g','1','-u','10','-f','10','-t','16','-w','3','-g','2','-u'],out='0_0A\n')
case('padding-sign-grouping',['-w','5','-g','2','12','-12','0'],out='0_00_12\n-0_00_12\n0_00_00\n')
case('group-one',['-t','16','-g','1','4095'],out='f_f_f\n')
case('group-no-split',['-g','3','12','123','1234'],out='12\n123\n1_234\n')
case('maximum-padding',['-w','64','-g','64','0','-1'],out='0'*64+'\n-'+'0'*63+'1\n')
case('padding-never-truncates',['-w','1','-g','2','12345'],out='1_23_45\n')
case('leading-zero-options',['-f','02','-t','36','-w','01','-g','02','111111'],out='1r\n')
errors('usage-base-grammar',[['1','-f',x] for x in ['00','01','37','100','+2','-2','','2.0',' 2']])
errors('usage-width-group-grammar',[['1',flag,x] for flag in ['-w','-g'] for x in ['0','65','001','+1','-1','','x']])
errors('usage-missing-values',[[flag] for flag in ['-f','-t','-w','-g']]+[['-u','-u'],['-t','16']])
errors('usage-option-tokens-consumed',[['5','-t','-u'],['5','-w','-g'],['5','-f','-u'],['5','-g','-t'],['5','-t','16','-g']])

TASK='03-globgrep'
case('example-1',['b*.txt'],'a.txt\nb.txt\nbb.txt\nb.txt.bak\nB.TXT\n','b.txt\nbb.txt\n')
case('example-2',['-i','[a-c]?.TXT'],'a1.txt\nB2.TXT\nd3.txt\nc.txt\ncc.txt\n','a1.txt\nB2.TXT\ncc.txt\n')
STAR='*note\n*1st\nnote*\n**\n*\n'
multi('example-3',[([r'\*[!0-9]*'],STAR,'*note\n**\n',0),(['-v','-c',r'\*[!0-9]*'],STAR,'3\n',0)])
multi('example-4',[(['x*'],'abc\n','',1),(['-c','x*'],'abc\n','0\n',1),(['x[]-]'],'x]\nx-\nxa\n','x]\nx-\n',0),(['--','-v'],'-v\nv\n','-v\n',0),([''],'a\n\nb\n','\n',0)])
errors('example-5',[[],['[abc'],['a\\'],['[z-a]'],['-x','a'],['-iv','a'],['a','b']])
case('empty-input',['*'],code=1)
case('empty-input-count-invert',['-v','-c','*'],out='0\n',code=1)
case('empty-lines-crlf-final',['?'],'\r\na\r\nb\ncc\nc','a\nb\nc\n')
case('whole-line-literals',['abc'],'xabc\nabcx\nabc\nAbc\n','abc\n')
case('wildcards-empty-sequence',['a*b?c'],'abc\nabxc\naZZbxc\naZZbc\n','abxc\naZZbxc\n')
case('escaped-metacharacters',[r'\*\?\[\]\\'],'*?[]\\\nanything\n','*?[]\\\n')
case('escape-ordinary',[r'\a\b'],'ab\n\\a\\b\n','ab\n')
case('slash-dot-no-special-treatment',['*'],'/.hidden\na/b\n\n','/.hidden\na/b\n\n')
multi('literal-dash-classes',[([p],'-\na\nz\nb\n',o,0) for p,o in [(r'[a\-z]','-\na\nz\n'),('[-a]','-\na\n'),('[a-]','-\na\n')]])
case('negated-right-bracket',['[!]]'],']\na\n-\n\n','a\n-\n')
case('class-special-characters',['[*?[!]'],'*\n?\n[\n!\n]\n','*\n?\n[\n!\n')
case('escaped-close-and-range',[r'[\]-a]'],']\n^\n_\n`\na\nb\n',']\n^\n_\n`\na\n')
case('case-insensitive-range-original-bytes',['-i','[A-C][!x-z]'],'aQ\nBq\ncX\nCy\nDZ\n','aQ\nBq\n')
case('case-insensitive-punctuation-range',['-i','[A-z]'],'@\n[\n_\n`\na\nZ\n{\n','[\n_\n`\na\nZ\n')
case('repeated-flags-count',['-i','-i','-v','-v','-c','-c','a'],'a\nA\nb\n\n','2\n')
case('separated-stars-question',['a*?*b'],'ab\naxb\naxxb\na\n','axb\naxxb\n')
errors('usage-after-pattern-and-end-options',[['a','-i'],['--'],['--','--','x'],['-'],['-c'],['a','--']])
errors('invalid-class-boundaries',[['[]'],['[!]'],['[a'],['[a\\'],['[z-\\a]'],['[!z-a]']])
# 39-byte pattern, 19 stars; a failing suffix forces exponential naive search.
# Any recursive matcher enumerating allocations has C(2000,19) dead paths.
case('pathological-backtracking',['-c','*a'*19+'b'],'a'*2000+'\n'+'a'*2000+'b\n','1\n')
case('pattern-and-input-limits',['?'*40],('x'*40+'\n')*2439+'x',('x'*40+'\n')*2439)

TASK='04-csvjoin'
PEOPLE='id,name,city\n1,Ann,Oslo\n2,Bob,"Rome, IT"\n3,Cy,Paris\n'
ORDERS='order,id,item\no1,2,pen\no2,1,"ink ""blue"""\no3,2,pad\no4,9,cup\n'
case('example-1',['people.csv','orders.csv'],out='id,name,city,order,item\n1,Ann,Oslo,o2,"ink ""blue"""\n2,Bob,"Rome, IT",o1,pen\n2,Bob,"Rome, IT",o3,pad\n',setup={'people.csv':PEOPLE,'orders.csv':ORDERS})
case('example-2',['-l','-k','sku','a.csv','b.csv'],out='sku,name,r.name,qty\nA1,Widget,Widget Co,5\nB2,"Gadget\nXL",,\nC3,Gizmo,Gizmo Inc,\n',setup={'a.csv':'sku,name\nA1,Widget\nB2,"Gadget\nXL"\nC3,Gizmo\n','b.csv':'name,sku,qty\r\nWidget Co,A1,5\r\nGizmo Inc,C3,\r\n'})
multi('example-3',[(['l.csv','r.csv'],'','id,v,w\n',0),(['r.csv','l.csv','-l'],'','id,w,v\n8,y,\n',0)],{'l.csv':'id,v\n\n7,x\n','r.csv':'id,w\n8,y'})
errors('example-4',[['-k','name','people.csv','orders.csv'],['people.csv','missing.csv'],['people.csv','bad.csv'],['people.csv','short.csv'],['people.csv','mid.csv']],1,{'people.csv':PEOPLE,'orders.csv':ORDERS,'bad.csv':'id,x\n1,"open\n','short.csv':'id,x\n1\n','mid.csv':'id,x\n1,a"b\n'})
errors('example-5',[['people.csv'],['a.csv','b.csv','c.csv'],['-x','people.csv','orders.csv'],['people.csv','orders.csv','-k']])
def join(name,left,right,out='',code=0,flags=()):
    case(name,[*flags,'l','r'],out=out,code=code,setup={'l':left,'r':right})
join('headers-only','id,x\n','id,y\n','id,x,y\n')
join('duplicate-keys-cross-product','id,v\na,L1\na,L2\n','id,v\na,R2\nb,Rx\na,R1\n','id,v,r.v\na,L1,R2\na,L1,R1\na,L2,R2\na,L2,R1\n')
join('empty-keys-exact-spaces','id,v\n,x\n ,space\nA,upper\na,lower\n','id,w\na,l\n,e\n ,s\n','id,v,w\n,x,e\n ,space,s\na,lower,l\n')
join('key-column-middle','x,key,y\nl,K,r\n','z,key,w\na,K,b\n','x,key,y,z,w\nl,K,r,a,b\n',flags=['-k','key'])
join('right-key-only-left','id,x\n1,a\n2,b\n','id\n1\n1\n','id,x\n1,a\n1,a\n2,b\n',flags=['-l'])
join('blank-record-skip','\n\r\nid,x\n\r\n1,y\n\n','\r\nid,w\n\n1,z\n\n','id,x,w\n1,y,z\n')
join('quoted-empty-record','id\n""\n','id,v\n"",ok\n','id,v\n,ok\n')
join('quoted-cr-lf-preserved','id,v\r\n1,"a\r\nb\rc\nd"\r\n','id,w\n1,"x,y"','id,v,w\n1,"a\r\nb\rc\nd","x,y"\n')
join('quotes-only-where-needed','"id","v"\n"1","plain"\n"2"," "\n3,"a""b"\n','id,w\n1,""\n2,x\n3,z\n','id,v,w\n1,plain,\n2, ,x\n3,"a""b",z\n')
join('header-quoting-clashes','id,"a,b","q""x"\n1,v,w\n','"q""x",id,"a,b"\nz,1,t\n','id,"a,b","q""x","r.q""x","r.a,b"\n1,v,w,z,t\n')
join('header-empty-name','id,\n1,x\n','id,\n1,y\n','id,,r.\n1,x,y\n')
multi('invalid-csv-atomicity',[(['l','r'+str(i)],'','',1) for i in range(5)],{'l':'id,x\n1,L\n',**{'r'+str(i):s for i,s in enumerate(['id,y\n1,ok\n2,"x"tail\n','id,y\n1,ok\n2,ab"c\n','id,y\n1,ok\n2,"open','id,y\n1,ok\n2,"a" \n','id,y\n1,ok\n2,x,extra\n'])}})
multi('invalid-headers',[(['l'+str(i),'r'],'','',1) for i in range(5)],{'r':'id\n',**{'l'+str(i):s for i,s in enumerate(['','\n\r\n','id,id\n','ID,x\n',' \n'])}})
join('short-left-late','id,v\n1,x\n2\n','id,w\n1,y\n',code=1)
errors('read-errors',[['missing','r'],['r','missing'],['','r']],1,{'r':'id\n'})
errors('usage-empty-key-options',[['-k','','l','r'],['l','r','-z'],[],['-k'],['--','l','r'],['-l']])
multi('options-anywhere-last-key',[(['-k','unused','left file','-l','right file','-k','key','-l'],'','key,v,w\n1,a,\n',0),(['-k','-l','dash-left','dash-right'],'','-l,v,w\n1,a,b\n',0)],{'left file':'key,v\n1,a\n','right file':'key,w\n','dash-left':'-l,v\n1,a\n','dash-right':'-l,w\n1,b\n'})
join('record-count-limit','id,x\n'+''.join(f'{i},v\n' for i in range(9999)),'id,w\n','id,x,w\n'+''.join(f'{i},v,\n' for i in range(9999)),flags=['-l'])
# Large single field checks the file byte boundary without a Cartesian explosion.
join('file-size-boundary','id,x\n1,'+'z'*999992+'\n','id\n1\n','id,x\n1,'+'z'*999992+'\n')

join('empty-left-data','id,v\n','id,w\n1,x\n','id,v,w\n',flags=['-l'])

TASK='05-standings'
def table(rows):
    # Only a renderer: all ranks, statistics and form supplied independently.
    width=max((len(r[1]) for r in rows),default=0)
    return ''.join(f'{pos:2}. {name:<{width}}{p:3}{w:3}{d:3}{l:3}{str(gf)+":"+str(ga):>7}{("+" if gf>ga else "")+str(gf-ga):>4}{pts:4} {form}\n' for pos,name,p,w,d,l,gf,ga,pts,form in rows)
case('example-1',stdin='# Matchday 1\nLions 2-1 Tigers\nBears 0-0 Wolves\nOld Boys 3-3 Lions\n\nTigers 1-0 Bears\nWolves 2-0 Old Boys\n',out=' 1. Wolves    2  1  1  0    2:0  +2   4 DW\n 2. Lions     2  1  1  0    5:4  +1   4 WD\n 3. Tigers    2  1  0  1    2:2   0   3 LW\n 4. Bears     2  0  1  1    0:1  -1   1 DL\n 5. Old Boys  2  0  1  1    3:5  -2   1 DL\n')
case('example-2',['-p','2,1,0'],'A 1-1 B\nC 0-0 D\nE 2-0 F\n',' 1. E  1  1  0  0    2:0  +2   2 W\n 2. A  1  0  1  0    1:1   0   1 D\n 2. B  1  0  1  0    1:1   0   1 D\n 4. C  1  0  1  0    0:0   0   1 D\n 4. D  1  0  1  0    0:0   0   1 D\n 6. F  1  0  0  1    0:2  -2   0 L\n')
case('example-3',stdin='X 1-0 Y\nY 2-2 X\nX 0-1 Y\nY 0-3 X\nX 4-4 Y\nX 1-0 Y\n',out=' 1. X  6  3  2  1   11:7  +4  11 DLWDW\n 2. Y  6  1  2  3   7:11  -4   5 DWLDL\n')
multi('example-4',[([],s,'',1) for s in ['Lions 2:1 Tigers\n','Lions 2-1 Tigers\nLions 1-1 Lions\n','Lions  2-1 Tigers\n','2-1 Tigers\n','Lions 2-1 1-0 Tigers\n','Lions 100-1 Tigers\n']])
multi('example-5',[(a,'','',2) for a in [['-p','3,1'],['-p'],['-x']]]+[([], '# nothing yet\n\n','',0)])
case('empty')
case('ignored-lines',stdin='\n   \r\n#anything\n#\n\r\n')
case('crlf-final-leading-zeros',stdin='A 09-00 B\r\nB 01-01 A',out=table([(1,'A',2,1,1,0,10,1,4,'WD'),(2,'B',2,0,1,1,1,10,1,'LD')]))
case('case-sensitive-names',stdin='a 0-0 A\n',out=table([(1,'A',1,0,1,0,0,0,1,'D'),(1,'a',1,0,1,0,0,0,1,'D')]))
case('allowed-name-tokens',stdin="St. John's & 9 2-1 FC 2\n",out=table([(1,"St. John's & 9",1,1,0,0,2,1,3,'W'),(2,'FC 2',1,0,0,1,1,2,0,'L')]))
case('goals-for-tiebreak',stdin='A 0-0 B\nC 1-1 D\n',out=table([(1,'C',1,0,1,0,1,1,1,'D'),(1,'D',1,0,1,0,1,1,1,'D'),(3,'A',1,0,1,0,0,0,1,'D'),(3,'B',1,0,1,0,0,0,1,'D')]))
case('wins-final-tiebreak',['-p','0,0,0'],'A 1-0 X\nA 0-1 X\nB 1-1 Y\n',table([(1,'A',2,1,0,1,1,1,0,'WL'),(1,'X',2,1,0,1,1,1,0,'LW'),(3,'B',1,0,1,0,1,1,0,'D'),(3,'Y',1,0,1,0,1,1,0,'D')]))
case('custom-loss-points',['-p','00,01,99'],'A 2-0 B\nC 0-0 D\n',table([(1,'B',1,0,0,1,0,2,99,'L'),(2,'C',1,0,1,0,0,0,1,'D'),(2,'D',1,0,1,0,0,0,1,'D'),(4,'A',1,1,0,0,2,0,0,'W')]))
case('form-five-exact',stdin='A 1-0 B\nB 1-0 A\nA 0-0 B\nA 0-0 B\nB 0-1 A\n',out=table([(1,'A',5,2,2,1,2,1,8,'WLDDW'),(2,'B',5,1,2,2,1,2,5,'LWDDL')]))
multi('malformed-spacing',[([],s,'',1) for s in [' A 1-0 B\n','A 1-0 B \n','A\t1-0 B\n','A 1-0  B\n','A 1-0\n','A 1-0 B\r\r\n']])
multi('malformed-score-and-names',[([],s,'',1) for s in ['A -1-0 B\n','A 1-000 B\n','A 1.0-0 B\n','A-B 1-0 C\n','A_1 1-0 B\n','A 1-0 B!\n']])
case('indented-comment-is-invalid',stdin='  # comment\n',code=1)
case('late-input-error-no-partial-output',stdin='#1\nA 2-1 B\n\nA 0-0 A\n',code=1)
errors('usage-point-grammar',[['-p',s] for s in ['3,1,0,0','3,,0','-1,1,0','100,1,0','+3,1,0','3, 1,0','3,1,0 ','']])
errors('usage-extra-args',[['-p','3,1,0','-p','3,1,0'],['-p3,1,0'],['file'],['--'],['']])
case('usage-before-input',['-x'],'A 2-1 B\ninvalid\n','',2)
case('maximum-score',stdin='A 99-00 B\n',out=table([(1,'A',1,1,0,0,99,0,3,'W'),(2,'B',1,0,0,1,0,99,0,'L')]))
case('wide-statistics-line-limit',['-p','99,99,99'],'A 99-0 B\n'*10000,table([(1,'A',10000,10000,0,0,990000,0,990000,'WWWWW'),(2,'B',10000,0,0,10000,0,990000,990000,'LLLLL')]))
case('team-count-limit',stdin=''.join(f'T00 0-0 T{i:02}\n' for i in range(1,99)),out=table([(1 if i==0 else 2,f'T{i:02}',98 if i==0 else 1,0,98 if i==0 else 1,0,0,0,98 if i==0 else 1,'DDDDD' if i==0 else 'D') for i in range(99)]))
case('byte-name-order',stdin='z 0-0 Z\nA 0-0 a\n',out=table([(1,n,1,0,1,0,0,0,1,'D') for n in ['A','Z','a','z']]))

TASK='06-buildorder'
RULES='# build rules\napp: lib util\nlib: core\nutil: core\ntest: app\n'
multi('example-1',[([],RULES,'core\nlib\nutil\napp\ntest\n',0),(['-l'],RULES,'0: core\n1: lib util\n2: app\n3: test\n',0)])
case('example-2',stdin='b: a\n  b :   c   a\nc:\nZ: b\n',out='a\nc\nb\nZ\n')
CYCLE=RULES+'x: y\ny: x\nz: x\n'
multi('example-3',[([],CYCLE,'CYCLE x y z\n',1),(['-t','app'],CYCLE,'core\nlib\nutil\napp\n',0),(['-l','-t','z','-t','lib'],CYCLE,'CYCLE x y z\n',1)])
multi('example-4',[([],s,'',3) for s in ['lib core\n','a b: c\n','a: b:c\n']]+[(['-t','nope'],'a: b\n','',3)])
multi('example-5',[(a,'','',2) for a in [['-x'],['-t'],['rules.txt']]]+[(['-l'],'# empty\n','',0)])
case('comments-spaces-crlf',stdin='   # comment\r\n  \n a : b   \r\nb:  \r',out='b\na\n')
case('dynamic-smallest-ready',stdin='A: b\nb:\nz:\n',out='b\nA\nz\n')
case('union-deduplication',stdin='a: c c\na: b\na:\nb: c\n',out='c\nb\na\n')
case('plain-dependency-selection',['-t','x'],'a: x y\n','x\n')
case('multi-target-closure',['-t','b','-t','c','-t','b'],'a: b\nb: d\nc: d e\nz: a\n','d\nb\ne\nc\n')
case('levels-longest-path',['-l'],'a: b d\nb: c\nc: d\nx:\n','0: d x\n1: c\n2: b\n3: a\n')
case('level-selection',['-l','-l','-t','b'],'a: b c\nb: d\nc: x\n','0: d\n1: b\n')
case('self-cycle',stdin='a: a\nb:\nc: a\n',out='CYCLE a c\n',code=1)
case('cycle-downstream-not-upstream',['-l'],'a: b root\nb: a\nconsumer: a\nroot:\nfree: root\n','CYCLE a b consumer\n',1)
case('multiple-disjoint-cycles',stdin='Z: Z\nx: y\ny: x\na: x Z\nq:\n',out='CYCLE Z a x y\n',code=1)
case('select-excludes-cycle',['-t','q'],'a: a\nb: a\nq:\n','q\n')
case('malformed-unselected-still-error',['-t','a'],'a:\nx: bad:name\n','',3)
multi('input-name-grammar',[([],s,'',3) for s in [': a\n','a\tb: c\n','a: b\tc\n','a: #inline\n','a!: b\n','a: b c:\n']])
case('name-punctuation-byte-order',stdin='target: ./x /x -x _x X x\n',out='-x\n./x\n/x\nX\n_x\nx\ntarget\n')
multi('unknown-target-and-empty-name',[(['-t',n],'a: b\n','',3) for n in ['','A','nope','a b','-l']])
errors('usage-arguments',[[''],['--'],['-lt'],['a'],['-t','a','-x'],['-l','-t']])
case('usage-before-input',['-x'],'bad\n','',2)
case('maximum-name',stdin='x'*64+':\n',out='x'*64+'\n')
case('deep-chain-item-line-limit',stdin=''.join(f'n{i:04}: n{i+1:04}\n' for i in range(9999))+'n9999:\n',out=''.join(f'n{i:04}\n' for i in range(9999,-1,-1)))
case('wide-level-item-limit',['-l'],''.join(f'n{i:04}:\n' for i in range(10000)),'0: '+' '.join(f'n{i:04}' for i in range(10000))+'\n')

TASK='07-linebuf'
protocol('example-1','APPEND hello world\nAPPEND second\nINSERT 1 first line\nPRINT 1\nPRINT 3\nCOUNT\nFIND o\nREPLACE 2 HELLO\nFIND o\nFIND xyz\n','OK 1\nOK 2\nOK 3\n1|first line\n3|second\n3\n2 3\nOK 3\n3\nNONE\n')
protocol('example-2','APPEND a\nAPPEND b\nAPPEND c\nAPPEND d\nDELETE 2 3\nPRINT 2\nUNDO\nPRINT 3\nUNDO\nREDO\nAPPEND e\nREDO\nUNDO\nCOUNT\n','OK 1\nOK 2\nOK 3\nOK 4\nOK 2\n2|d\nOK 4\n3|c\nOK 3\nOK 4\nOK 5\nERR nothing to redo\nOK 4\n4\n')
protocol('example-3','DELETE 1\nAPPEND \nPRINT 1\nPRINT 2\nINSERT 3 x\nINSERT 2 x\ndelete 1\nREPLACE 1\nDELETE 2 1\nUNDO\nPRINT 02\nFIND \nUNDO\nUNDO\n','ERR bad line\nOK 1\n1|\nERR bad line\nERR bad line\nOK 2\nERR bad command\nERR bad command\nERR bad line\nOK 1\nERR bad line\nERR bad command\nOK 0\nERR nothing to undo\n')
case('example-4',['extra'],code=2)
case('empty')
protocol('empty-state-queries','COUNT\nUNDO\nREDO\nFIND a\nPRINT 0\nPRINT 1\n','0\nERR nothing to undo\nERR nothing to redo\nNONE\nERR bad line\nERR bad line\n')
protocol('text-spaces-empty-and-pipe','APPEND  x  \nAPPEND \nINSERT 2 |\nREPLACE 3  \nPRINT 1\nPRINT 2\nPRINT 3\nFIND  \n','OK 1\nOK 2\nOK 3\nOK 3\n1| x  \n2||\n3| \n1 3\n')
protocol('number-leading-zeros','INSERT 000000001 a\nINSERT 02 b\nPRINT 000000002\nREPLACE 01 c\nDELETE 000000001 02\nCOUNT\nUNDO\nPRINT 01\n','OK 1\nOK 2\n2|b\nOK 2\nOK 0\n0\nOK 2\n1|c\n')
protocol('insertion-boundaries','INSERT 0 x\nINSERT 2 x\nINSERT 1 a\nINSERT 1 b\nINSERT 3 c\nPRINT 1\nPRINT 2\nPRINT 3\n','ERR bad line\nERR bad line\nOK 1\nOK 2\nOK 3\n1|b\n2|a\n3|c\n')
protocol('delete-full-range-undo-redo','APPEND a\nAPPEND b\nAPPEND c\nDELETE 1 3\nCOUNT\nUNDO\nPRINT 2\nREDO\nCOUNT\n','OK 1\nOK 2\nOK 3\nOK 0\n0\nOK 3\n2|b\nOK 0\n0\n')
protocol('replace-undo-redo','APPEND old\nREPLACE 1 new\nUNDO\nPRINT 1\nREDO\nPRINT 1\nUNDO\nUNDO\nREDO\nPRINT 1\nREDO\nPRINT 1\n','OK 1\nOK 1\nOK 1\n1|old\nOK 1\n1|new\nOK 1\nOK 0\nOK 1\n1|old\nOK 1\n1|new\n')
protocol('same-text-replace-is-change','APPEND a\nREPLACE 1 a\nUNDO\nCOUNT\nUNDO\nCOUNT\nREDO\nREDO\nUNDO\nPRINT 1\n','OK 1\nOK 1\nOK 1\n1\nOK 0\n0\nOK 1\nOK 1\nOK 1\n1|a\n')
protocol('failed-commands-preserve-redo','APPEND a\nAPPEND b\nUNDO\nPRINT 1\nFIND a\nCOUNT\nDELETE 9\nREPLACE 0 x\nbad\nREDO\nPRINT 2\n','OK 1\nOK 2\nOK 1\n1|a\n1\n1\nERR bad line\nERR bad line\nERR bad command\nOK 2\n2|b\n')
protocol('new-change-clears-redo','APPEND a\nAPPEND b\nUNDO\nINSERT 1 z\nREDO\nUNDO\nPRINT 1\nREDO\nPRINT 1\n','OK 1\nOK 2\nOK 1\nOK 2\nERR nothing to redo\nOK 1\n1|a\nOK 2\n1|z\n')
protocol('replace-same-clears-redo','APPEND a\nAPPEND b\nUNDO\nREPLACE 1 a\nREDO\nUNDO\nCOUNT\n','OK 1\nOK 2\nOK 1\nOK 1\nERR nothing to redo\nOK 1\n1\n')
protocol('search-substring-case-sensitive','APPEND banana\nAPPEND BANANA\nAPPEND ana ana\nFIND ana\nFIND BAN\nFIND a a\nFIND .\n','OK 1\nOK 2\nOK 3\n1 3\n2\n3\nNONE\n')
bad=['','append x','APPEND','INSERT 1','REPLACE 1','FIND','FIND ','COUNT ','UNDO x','REDO ','DELETE 1 2 3','PRINT 1 x',' INSERT 1 x','DELETE  1','PRINT\t1']
protocol('malformed-command-forms','\n'.join(bad)+'\n','ERR bad command\n'*len(bad))
bad=['PRINT -1','PRINT +1','PRINT 0000000001','INSERT 1.0 x','DELETE x','DELETE 1 0000000000','REPLACE  x']
protocol('malformed-number-grammar','\n'.join(bad)+'\n','ERR bad command\n'*len(bad))
protocol('bad-number-boundaries','APPEND x\nDELETE 0\nDELETE 2\nDELETE 1 0\nDELETE 2 1\nREPLACE 999999999 x\nPRINT 999999999\nINSERT 999999999 x\nCOUNT\n','OK 1\n'+'ERR bad line\n'*7+'1\n')
protocol('crlf-final-no-newline','APPEND x\r\nPRINT 1\r\nCOUNT','OK 1\n1|x\n1\n')
protocol('maximum-text','APPEND '+'x'*1000+'\nPRINT 1\nFIND '+'x'*1000+'\n','OK 1\n1|'+'x'*1000+'\n1\n')
protocol('history-and-buffer-limit','APPEND x\n'*10000+'UNDO\n'*10000+'REDO\n'*10000+'COUNT\n', ''.join(f'OK {i}\n' for i in range(1,10001))+''.join(f'OK {i}\n' for i in range(9999,-1,-1))+''.join(f'OK {i}\n' for i in range(1,10001))+'10000\n')
protocol('command-count-limit','COUNT\n'*100000,'0\n'*100000)
multi('lockstep-response-flushing', [([], 'APPEND x\nPRINT 1\nUNDO\nCOUNT\n','OK 1\n1|x\nOK 0\n0\n',None,4)])
errors('usage-empty-and-options',[[''],['-x'],['a','b']])

TASK='08-sheet'
protocol('example-1','SET A1 10\nSET A2 32\nSET A3 =A1+A2\nGET A3\nSET A1 -5\nGET A3\nSHOW A3\nGET B7\nSHOW B7\n','OK\nOK\nOK\n42\nOK\n27\n=A1+A2\n0\nEMPTY\n')
protocol('example-2','SET B1 1\nSET B2 2\nSET B3 3\nSET C1 =SUM(B3:B1)-1\nGET C1\nSET B2 =C1\nGET B2\nSET D1 =D1+1\nSET D1 =-C1+100\nGET D1\nCLEAR B3\nGET C1\nGET D1\nSHOW B3\n','OK\nOK\nOK\nOK\n5\nERR cycle\n2\nERR cycle\nOK\n95\nOK\n2\n98\nEMPTY\n')
TEN=lambda c: '='+'+'.join([c]*10)
protocol('example-3','SET A1 999999999\n'+''.join(f'SET A{i} {TEN("A"+str(i-1))}\n' for i in range(2,5))+'GET A4\nSET A5 =A4+A4\nGET A5\nSET A6 =A5-A5\nGET A6\nSET A5 0\nGET A6\nSHOW A5\n','OK\n'*4+'999999999000\nOK\nERR overflow\nOK\nERR overflow\nOK\n0\n0\n')
protocol('example-4','SET a1 5\nSET A100 1\nSET A1 =A1+\nSET A1 1+2\nSET A1 = A2\nGET\nget A1\nSET A1 =SUM(A1)\nSHOW A1\n','ERR bad command\n'*8+'EMPTY\n')
case('example-5',['extra'],code=2)
case('empty')
protocol('empty-cells-clear','GET A1\nSHOW Z99\nCLEAR A1\nCLEAR A1\nGET A1\n','0\nEMPTY\nOK\nOK\n0\n')
protocol('literal-spelling-preserved','SET A1 000000007\nGET A1\nSHOW A1\nSET A1 -000\nGET A1\nSHOW A1\nSET A1 -999999999\nGET A1\n','OK\n7\n000000007\nOK\n0\n-000\nOK\n-999999999\n')
protocol('formula-signs-left-to-right','SET A1 =10-3-2+1\nGET A1\nSET A2 =-A1+0009-1\nGET A2\nSET A3 =-5\nGET A3\nSHOW A3\n','OK\n6\nOK\n2\nOK\n-5\n=-5\n')
protocol('dynamic-transitive-recalculation','SET A1 1\nSET B1 =A1+1\nSET C1 =B1+A1\nGET C1\nSET A1 5\nGET C1\nCLEAR B1\nGET C1\nSHOW B1\n','OK\nOK\nOK\n3\nOK\n11\nOK\n5\nEMPTY\n')
protocol('range-reversed-two-dimensional','SET A1 1\nSET A2 2\nSET B1 3\nSET B2 4\nSET C1 =SUM(B2:A1)\nGET C1\nSET B2 -4\nGET C1\nSET C2 =SUM(A2:B1)-SUM(B1:A2)\nGET C2\n','OK\n'*5+'10\nOK\n2\nOK\n0\n')
protocol('range-overlap-counts-twice','SET A1 3\nSET B1 4\nSET C1 =SUM(A1:B1)+SUM(B1:B1)+A1\nGET C1\n','OK\nOK\nOK\n14\n')
protocol('self-cycle-in-zero-coefficient','SET A1 5\nSET A1 =A1-A1\nSHOW A1\nGET A1\nSET B1 =SUM(B1:B1)\nSHOW B1\n','OK\nERR cycle\n5\n5\nERR cycle\nEMPTY\n')
protocol('transitive-cycle-rejected-old-kept','SET A1 2\nSET B1 =A1\nSET C1 =B1\nSET A1 =C1\nSHOW A1\nGET C1\nCLEAR B1\nSET A1 =C1\nGET A1\n','OK\nOK\nOK\nERR cycle\n2\n2\nOK\nOK\n0\n')
protocol('range-references-empty-cells','SET C3 =SUM(A1:B2)\nSET A2 =C3\nSHOW A2\nSET A2 5\nGET C3\n','OK\nERR cycle\nEMPTY\nOK\n5\n')
# All values and expected overflows are closed-form powers of ten.
POWER='SET A1 100000000\n'+''.join(f'SET A{i} {TEN("A"+str(i-1))}\n' for i in range(2,6))
protocol('overflow-inclusive-boundaries',POWER+'GET A5\nSET B1 =A5+1\nGET B1\nSET B2 =-A5\nGET B2\nSET B3 =B2-1\nGET B3\n', 'OK\n'*5+'1000000000000\nOK\nERR overflow\nOK\n-1000000000000\nOK\nERR overflow\n')
protocol('intermediate-large-final-valid',POWER+'SET B1 =A5+A5-A5\nGET B1\n', 'OK\n'*6+'1000000000000\n')
protocol('range-overflow-propagates-and-recovers',POWER+'SET B1 =A5+1\nSET C1 =SUM(B1:B2)-SUM(B1:B2)\nGET C1\nCLEAR B1\nGET C1\n', 'OK\n'*7+'ERR overflow\nOK\n0\n')
bad=['A0','A01','A100','a1','AA1','Z00','1A','A-1']
protocol('invalid-cell-names',''.join('SET '+c+' 1\n' for c in bad),'ERR bad command\n'*len(bad))
bad=['=','=+A1','=--A1','=A1+','=A1+-1','=A1*2','=sum(A1:A2)','=SUM(A1)','=SUM(A0:A2)','=SUM(A1:A2)+-1','+1','1000000000','-1000000000','=1234567890','=SUM(A1:A2))']
protocol('invalid-formula-grammar',''.join('SET A1 '+x+'\n' for x in bad)+'SHOW A1\n','ERR bad command\n'*len(bad)+'EMPTY\n')
bad=['','GET','GET A1 x','GET  A1',' GET A1','GET A1 ','CLEAR','CLEAR A1 x','SHOW A1 ','SET A1  1','SET A1 = A2','get A1']
protocol('exact-spacing-command-forms','\n'.join(bad)+'\n','ERR bad command\n'*len(bad))
protocol('crlf-final-command','SET Z99 =007\r\nSHOW Z99\r\nGET Z99','OK\n=007\n7\n')
CELLS=[chr(c)+str(r) for c in range(65,91) for r in range(1,100)]
protocol('all-cells-deep-chain','SET A1 1\n'+''.join(f'SET {c} ={p}\n' for p,c in zip(CELLS,CELLS[1:]))+'GET Z99\nSET Z99 =SUM(Z98:A1)\nGET Z99\nSET Z99 =SUM(Z99:A1)\nGET Z99\n','OK\n'*2574+'1\nOK\n2548\nERR cycle\n2548\n')
protocol('command-and-line-limits','SET Z99 ='+'+'.join(['1']*96)+'\n'+'GET Z99\n'*19999,'OK\n'+'96\n'*19999)
multi('flush-and-usage', [([], 'SET A1 1\nGET A1\nCLEAR A1\nGET A1\n','OK\n1\nOK\n0\n',None,4),([''], '','',2),(['-x'],'','',2)])

TASK='09-todo'
protocol('example-1','ADD 2 buy milk\nADD 1 fix the roof\nADD 2 call mom\nLIST\nNEXT\nDONE 2\nDONE 2\nDONE 9\nLIST\nSHOW 2\nPURGE\nSTATS\nADD 3 water plants\nSHOW 04\n','ADDED 1\nADDED 2\nADDED 3\nOPEN 2 1 3\n2 1 open fix the roof\nOK\nERR already done\nERR no such item\nOPEN 1 3\n2 1 done fix the roof\nPURGED 1\nopen=2 done=0 next_id=4\nADDED 4\n4 3 open water plants\n',['data'])
multi('example-2',[(['d'],'ADD 1 alpha\nADD 2 beta\nDONE 1\nADD 3 gamma\n','ADDED 1\nADDED 2\nOK\n',None,3),(['d'],'STATS\nLIST\nADD 1 delta\n','open=1 done=1 next_id=3\nOPEN 2\nADDED 3\n',0)])
multi('example-3',[(['d'],'ADD 1 a\nDONE 1\nPURGE\nSTATS\n','ADDED 1\nOK\nPURGED 1\nopen=0 done=0 next_id=2\n',0),(['d'],'ADD 1 b\nSHOW 1\nLIST\n','ADDED 2\nERR no such item\nOPEN 2\n',0)])
STATE='TODO 1\nnext 8\n3 2 o water plants\n5 1 d pay rent\n7 1 o book flights\n'
protocol('example-4','LIST\nNEXT\nSTATS\nADD 5 later\nSHOW 5\n','OPEN 7 3\n7 1 open book flights\nopen=2 done=1 next_id=8\nADDED 8\n5 1 done pay rent\n',['d'],{'d/todo.db':STATE,'d/todo.db.tmp':'garbage'})
multi('example-5',[(['bad-id'],'LIST\n','',1),(['bad-eof'],'LIST\n','',1),([], '','',2),(['a','b'],'','',2),(['f'],'','',1),(['d'],'ADD 0 x\nADD 10 x\nADD 1 \nadd 1 x\nDONE x\n','ERR bad command\n'*5,0)],{'bad-id/todo.db':'TODO 1\nnext 3\n5 1 o x\n','bad-eof/todo.db':'TODO 1\nnext 3\n1 1 o x','f':'file'})
multi('empty-start-and-restart',[(['d'],'','',0),(['d'],'','',0)])
protocol('empty-state-queries','LIST\nNEXT\nSTATS\nPURGE\nSHOW 0\nDONE 1\n','OPEN\nNONE\nopen=0 done=0 next_id=1\nPURGED 0\nERR no such item\nERR no such item\n',['d'])
protocol('priority-then-id','ADD 9 z\nADD 1 a\nADD 2 b\nADD 1 c\nLIST\nDONE 2\nLIST\nNEXT\nDONE 4\nNEXT\n','ADDED 1\nADDED 2\nADDED 3\nADDED 4\nOPEN 2 4 3 1\nOK\nOPEN 4 3 1\n4 1 open c\nOK\n3 2 open b\n',['d'])
TEXT=' !"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~  '
multi('text-spaces-and-length',[(['d'],'ADD 1  \nADD 2 '+TEXT+'\nADD 3 '+'x'*200+'\nSHOW 1\nSHOW 2\nSHOW 3\n','ADDED 1\nADDED 2\nADDED 3\n1 1 open  \n2 2 open '+TEXT+'\n3 3 open '+'x'*200+'\n',0),(['d'],'SHOW 1\nSHOW 2\nSHOW 3\n','1 1 open  \n2 2 open '+TEXT+'\n3 3 open '+'x'*200+'\n',0)])
bad=[b'',b'ADD',b'ADD 1',b'ADD 1 ',b'ADD 01 x',b'ADD 0 x',b'ADD 10 x',b'ADD  1 x',b'ADD 1 x\t',b'ADD 1 \x7f',b'ADD 1 \x80',b'ADD 1 \x00',b'add 1 x',b'LIST ',b'NEXT x',b'PURGE 1',b'STATS x',b'SHOW 1 extra',b' DONE 1']
protocol('malformed-commands-and-bytes',b'\n'.join(bad)+b'\nSTATS\n','ERR bad command\n'*len(bad)+'open=0 done=0 next_id=1\n',['d'])
protocol('id-grammar-and-zero-padding','ADD 1 a\nSHOW 000000001\nDONE 01\nSHOW 1\nDONE 0001\nSHOW 0\nDONE 999999999\nSHOW +1\nSHOW -1\nSHOW 0000000001\nSHOW\n','ADDED 1\n1 1 open a\nOK\n1 1 done a\nERR already done\nERR no such item\nERR no such item\nERR bad command\nERR bad command\nERR bad command\nERR bad command\n',['d'])
multi('done-purge-normal-restart',[(['d'],'ADD 1 a\nADD 2 b\nADD 3 c\nDONE 1\nDONE 3\n','ADDED 1\nADDED 2\nADDED 3\nOK\nOK\n',0),(['d'],'SHOW 1\nSHOW 3\nPURGE\nPURGE\nSTATS\n','1 1 done a\n3 3 done c\nPURGED 2\nPURGED 0\nopen=1 done=0 next_id=4\n',0),(['d'],'SHOW 1\nSHOW 2\nADD 1 d\nSTATS\n','ERR no such item\n2 2 open b\nADDED 4\nopen=2 done=0 next_id=5\n',0)])
multi('kill-after-add',[(['d'],'ADD 9 original\nADD 1 unsent\n','ADDED 1\n',None,1),(['d'],'SHOW 1\nSHOW 2\nSTATS\nADD 1 next\n','1 9 open original\nERR no such item\nopen=1 done=0 next_id=2\nADDED 2\n',0)])
multi('kill-after-done',[(['d'],'ADD 1 x\nDONE 1\nPURGE\n','ADDED 1\nOK\n',None,2),(['d'],'SHOW 1\nLIST\nNEXT\nSTATS\nDONE 1\n','1 1 done x\nOPEN\nNONE\nopen=0 done=1 next_id=2\nERR already done\n',0)])
multi('kill-after-purge',[(['d'],'ADD 1 x\nDONE 1\nPURGE\nADD 2 unsent\n','ADDED 1\nOK\nPURGED 1\n',None,3),(['d'],'STATS\nSHOW 1\nADD 2 y\n','open=0 done=0 next_id=2\nERR no such item\nADDED 2\n',0),(['d'],'SHOW 2\nSTATS\n','2 2 open y\nopen=1 done=0 next_id=3\n',0)])
multi('repeated-kill-recovery',[(['d'],'ADD 2 a\nADD 9 unsent\n','ADDED 1\n',None,1),(['d'],'ADD 1 b\nDONE 1\n','ADDED 2\n',None,1),(['d'],'LIST\nSHOW 1\nSHOW 2\nSTATS\n','OPEN 2 1\n1 2 open a\n2 1 open b\nopen=2 done=0 next_id=3\n',0)])
multi('kill-after-read-and-error',[(['d'],'ADD 1 a\nSHOW 1\nBAD\nDONE 1\n','ADDED 1\n1 1 open a\nERR bad command\n',None,3),(['d'],'SHOW 1\nSTATS\n','1 1 open a\nopen=1 done=0 next_id=2\n',0)])
multi('temp-only-deleted-not-promoted',[(['d'],'LIST\nSTATS\n','OPEN\nopen=0 done=0 next_id=1\n',0),(['d/todo.db.tmp'],'STATS\n','open=0 done=0 next_id=1\n',0)],{'d/todo.db.tmp':b'TODO 1\nnext 2\n1 1 o stolen\n\x00garbage'})
multi('valid-db-beats-newer-temp',[(['d'],'LIST\nSHOW 3\nSTATS\n','OPEN 3\n3 9 open real\nopen=1 done=0 next_id=5\n',0),(['d/todo.db.tmp'],'LIST\n','OPEN\n',0)],{'d/todo.db':'TODO 1\nnext 5\n3 9 o real\n','d/todo.db.tmp':'TODO 1\nnext 8\n1 1 o fake\n'})
invalid=['', 'TODO 1\n','TODO 2\nnext 1\n','TODO 1\r\nnext 1\r\n','TODO 1\nnext 0\n','TODO 1\nnext 01\n','TODO 1\nnext +2\n','TODO 1\nnext 1000000000\n','TODO 1\nnext 2','TODO 1\nnext 1\n\n','TODO 1\nnext  2\n']
multi('strict-state-header-grammar',[(['d'+str(i)],'LIST\n','',1) for i in range(len(invalid))],{'d'+str(i)+'/todo.db':s for i,s in enumerate(invalid)})
invalid=[b'01 1 o x\n',b'0 1 o x\n',b'1 0 o x\n',b'1 10 o x\n',b'1 1 open x\n',b'1 1 O x\n',b'1 1 o \n',b'1 1 o x\r\n',b'1 1 o x\t\n',b'1 1 o \x80\n',b' 1 1 o x\n',b'1  1 o x\n',b'1 1 o x']
multi('strict-state-item-grammar',[(['d'+str(i)],'LIST\n','',1) for i in range(len(invalid))],{'d'+str(i)+'/todo.db':b'TODO 1\nnext 3\n'+s for i,s in enumerate(invalid)})
invalid=['TODO 1\nnext 3\n1 1 o a\n1 2 d b\n','TODO 1\nnext 3\n2 1 o a\n1 1 o b\n','TODO 1\nnext 3\n3 1 o a\n','TODO 1\nnext 3\n4 1 o a\n']
multi('strict-state-order-and-next',[(['d'+str(i)],'STATS\n','',1) for i in range(len(invalid))],{'d'+str(i)+'/todo.db':s for i,s in enumerate(invalid)})
multi('invalid-state-remains-invalid',[(['d'],'ADD 1 repair\n','',1),(['d'],'LIST\n','',1),(['d/todo.db.tmp'],'STATS\n','open=0 done=0 next_id=1\n',0)],{'d/todo.db':'TODO 1\nnext 2\n2 1 o invalid\n','d/todo.db.tmp':'anything'})
# Planting 10000 items avoids an irrelevant quadratic snapshot-writing workload.
LARGE='TODO 1\nnext 10001\n'+''.join(f'{i} 1 o x\n' for i in range(1,10001))
multi('state-and-command-limits',[(['large'],'STATS\nLIST\nSHOW 10000\n','open=10000 done=0 next_id=10001\nOPEN '+' '.join(map(str,range(1,10001)))+'\n10000 1 open x\n',0),(['wide'],'ADD 9 end\nSHOW 999999998\nSTATS\n','ADDED 999999998\n999999998 9 open end\nopen=1 done=0 next_id=999999999\n',0),(['wide'],'STATS\n'*10000,'open=1 done=0 next_id=999999999\n'*10000,0)],{'large/todo.db':LARGE,'wide/todo.db':'TODO 1\nnext 999999998\n'})
multi('directory-errors-and-crlf',[(['missing/child'],'LIST\n','',1),(['file'],'','',1),(['with spaces'],'ADD 1 x\r\nSHOW 1','ADDED 1\n1 1 open x\n',0),(['-x'],'LIST\n','OPEN\n',0)],{'file':'x'})

TASK='10-cachesim'
def cache(name,args,trace,decisions,counts):
    accesses=trace.splitlines()
    labels=decisions.split() if isinstance(decisions,str) else decisions
    assert len(accesses)==len(labels),(name,len(accesses),len(labels))
    h1,m1,w1,h2,m2,w2=counts
    out=''.join(a+' '+d+'\n' for a,d in zip(accesses,labels))
    out+=f'L1 hits={h1} misses={m1} writebacks={w1}\nL2 hits={h2} misses={m2} writebacks={w2}\n'
    case(name,args,trace,out)
cache('example-1',['-b','16','-1','1:2','-2','2:2'],'R 0x00\nR 0x04\nW 0x10\nR 0x20\nR 0x00\nR 0x14\nR 0x30\nW 0x50\nR 0x58\n','MEM L1 MEM MEM L2 L2 MEM MEM L1',(2,7,1,2,5,1))
cache('example-2',['-b','4','-1','1:1','-2','1:1'],'W 0x0\nR 0x4\nR 0x0\nR 0x8\n','MEM MEM L2 MEM',(0,4,1,1,3,1))
cache('example-3',[],'R 0xABC\nR 0xab0\n','MEM L1',(1,1,0,0,1,0))
cache('example-4',['-2','1:1'],'','',(0,0,0,0,0,0))
multi('example-5',[(a,'','',2) for a in [['-b','12'],['-1','0:2'],['-1','4'],['-b'],['trace.txt']]]+[([],s,'',1) for s in ['R 0x10\nX 0x10\n','R 10\n','W 0x123456789\n']])
case('blank-trace',stdin='\n  \r\n\r\n   ',out='L1 hits=0 misses=0 writebacks=0\nL2 hits=0 misses=0 writebacks=0\n')
multi('same-block-write-no-final-flush',[([], 'R 0x00\nW 0x0F\nR 0x00000001\nW 0x0\n','R 0x00 MEM\nW 0x0F L1\nR 0x00000001 L1\nW 0x0 L1\nL1 hits=3 misses=1 writebacks=0\nL2 hits=0 misses=1 writebacks=0\n',0),(['-b','1','-1','1:1','-2','1:1'],'R 0x0\nW 0x0\nR 0x1\nR 0x2\n','R 0x0 MEM\nW 0x0 L1\nR 0x1 MEM\nR 0x2 MEM\nL1 hits=1 misses=3 writebacks=1\nL2 hits=0 misses=3 writebacks=1\n',0)])
cache('l1-hit-refreshes-lru',['-b','1','-1','1:2','-2','1:8'],'R 0x0\nR 0x1\nR 0x0\nR 0x2\nR 0x1\n','MEM MEM L1 MEM L2',(1,4,0,1,3,0))
cache('l2-hit-refreshes-lru',['-b','1','-1','1:1','-2','1:2'],'R 0x0\nR 0x1\nR 0x0\nR 0x2\nR 0x1\n','MEM MEM L2 MEM MEM',(0,5,0,1,4,0))
cache('l1-hit-leaves-l2-lru-alone',['-b','1','-1','1:2','-2','1:2'],'R 0x0\nR 0x1\nR 0x0\nR 0x2\nR 0x0\n','MEM MEM L1 MEM L1',(2,3,0,0,3,0))
cache('noninclusive-l2-eviction',['-b','1','-1','1:2','-2','1:1'],'R 0x0\nR 0x1\nR 0x0\n','MEM MEM L1',(1,2,0,0,2,0))
cache('writeback-existing-refreshes-l2-lru',['-b','1','-1','1:1','-2','1:2'],'W 0x0\nR 0x1\nR 0x2\nR 0x0\n','MEM MEM MEM L2',(0,4,1,1,3,0))
cache('l2-read-hit-preserves-dirty',['-b','1','-1','1:1','-2','1:2'],'W 0x0\nR 0x1\nR 0x0\nR 0x2\nR 0x3\n','MEM MEM L2 MEM MEM',(0,5,1,1,4,1))
cache('write-allocate-l2-clean-first',['-b','1','-1','1:1','-2','1:1'],'W 0x0\nW 0x1\nW 0x1\n','MEM MEM L1',(1,2,1,0,2,0))
cache('non-power-of-two-sets',['-b','1','-1','3:1','-2','5:1'],'R 0x0\nR 0x3\nR 0x1\nR 0x4\nR 0x0\n','MEM MEM MEM MEM L2',(0,5,0,1,4,0))
cache('max-block-sets-address',['-b','4096','-1','4096:64','-2','4096:64'],'R 0xFFFFFFFF\nR 0xfffff000\nW 0x0\nR 0x00000fff\n','MEM L1 MEM L1',(2,2,0,0,2,0))
cache('block-one-adjacency',['-b','1'],'R 0x0\nR 0x1\nR 0x0\n','MEM MEM L1',(1,2,0,0,2,0))
cache('maximum-ways',['-b','1','-1','1:64','-2','1:64'],''.join(f'R 0x{i:x}\n' for i in range(64))+'R 0x0\nR 0x40\nR 0x1\n',['MEM']*64+['L1','MEM','L2'],(1,66,0,1,65,0))
cache('repeated-options-leading-zeros',['-b','16','-1','4:2','-2','16:4','-b','0001','-1','0001:01','-2','0001:02'],'R 0x0\nR 0x1\nR 0x0\n','MEM MEM L2',(0,3,0,1,2,0))
bad=['R 0X10','r 0x10','R  0x10',' R 0x10','R 0x10 ','R\t0x10','R 0x','R 0xg','R -0x1','R 0x1 extra','# comment','\t']
multi('strict-trace-atomicity',[([], 'R 0x0\n'+s+'\n','',1) for s in bad])
case('crlf-and-final-address-echo',stdin=' \r\nR 0xAbC\r\n\nR 0x00000aBf',out='R 0xAbC MEM\nR 0x00000aBf L1\nL1 hits=1 misses=1 writebacks=0\nL2 hits=0 misses=1 writebacks=0\n')
errors('usage-block-grammar',[['-b',s] for s in ['0','3','12','4097','8192','00001','+1','-1','','1.0',' 2']])
errors('usage-geometry-grammar',[[flag,s] for flag in ['-1','-2'] for s in ['0:1','4097:1','1:0','1:65','1','1:2:3','00001:1','1:001','+1:2','1:-1',':1','1:','1 :2']])
errors('usage-missing-unknown-early-invalid',[['-1'],['-2'],['-x'],['--'],[''],['-b16'],['-b','-1']])
cache('access-count-limit',[],'R 0x0\n'*200000,['MEM']+['L1']*199999,(199999,1,0,0,1,0))
