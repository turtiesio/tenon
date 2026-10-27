"""Set 5 fixtures independently worked from the frozen task specifications.

Never imports, reads, or runs any reference/solution. Expected results are
literals or closed-form boundary constructions. Formatting helpers accept
already-worked results, rather than computing task behavior from input.
"""
from pathlib import Path
import shutil
ROOT = Path(__file__).resolve().parent
TASK = ''

def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value,bytes) else value.encode('utf-8'))

def base(name, setup):
    p = ROOT/TASK/'cases'/name
    if p.exists(): shutil.rmtree(p)
    p.mkdir(parents=True)
    for filename,value in (setup or {}).items():
        if value is None: (p/'setup'/filename).mkdir(parents=True,exist_ok=True)
        else: put(p/'setup'/filename,value)
    return p

def files(p,args,stdin,out,code):
    put(p/'cmd',''.join(a+'\n' for a in args))
    if stdin: put(p/'stdin',stdin)
    put(p/'expected_stdout',out)
    if code is not None: put(p/'expected_exit',str(code)+'\n')

def case(name,args=(),stdin='',out='',code=0,setup=None):
    files(base(name,setup),args,stdin,out,code)

def multi(name,steps,setup=None):
    p = base(name,setup)
    manifest = []
    for i,(args,stdin,out,code,*kill) in enumerate(steps,1):
        label = f'step-{i}'
        manifest.append(label+(f' kill-after={kill[0]}' if kill else ''))
        files(p/label,args,stdin,out,None if kill else code)
    put(p/'steps','\n'.join(manifest)+'\n')

def errors(name,variants,code=2,setup=None):
    multi(name,[(a,'','',code) for a in variants],setup)

def bad_inputs(name,inputs,args=(),setup=None):
    multi(name,[(args,text,'',1) for text in inputs],setup)

def lines(items): return ''.join(x+'\n' for x in items)

TASK = '01-seqx'
case('example-1',['1','5'],out='1\n2\n3\n4\n5\n')
case('example-2',['-s',',','10','-3','1'],out='10,7,4,1\n')
multi('example-3',[(['-w','-s',' ','-10','4','3'],'','-10 -06 -02 002\n',0),(['3','-1','-2','-w'],'','03\n02\n01\n00\n-1\n-2\n',0)])
multi('example-4',[(['-s','','-n','4','7','1000'],'','78910\n',0),(['5','1'],'','',0),(['-n','0','1','5'],'','',0)])
errors('example-5',[['1'],['1','0','5'],['1','x'],['1','+2'],['1','2','3','4'],['-n','-1','1','5'],['1','5','-s']])
case('single-equal',['-w','-s','x','-007','-007'],out='-7\n')
case('negative-wrong-direction',['1','-1','5'])
case('nondivisible-positive',['-s',':','-5','4','6'],out='-5:-1:3\n')
case('nondivisible-negative',['-s',',','5','-4','-6'],out='5,1,-3\n')
case('canonical-zero-leading-zeros',['-s',' ','-000','0001','0003'],out='0 1 2 3\n')
case('width-after-limit',['-w','-n','2','-s',',','8','1000'],out='8,9\n')
case('width-negative-sign',['-w','-s',',','-2','-9','-20'],out='-02,-11,-20\n')
case('width-through-zero',['-w','-s',',','-1','1','10'],out='-1,00,01,02,03,04,05,06,07,08,09,10\n')
case('literal-option-separator',['1','-s','-w','2'],out='1-w2\n')
case('repeated-mixed-options',['-s',',','-n','000000001','-w','9','-s',' / ','-n','000000003','12','-w'],out='09 / 10 / 11\n')
case('separator-empty',['-s','','-1','1'],out='-101\n')
case('limit-exceeds-sequence',['-n','999999999','-s',' ','2','2','6'],out='2 4 6\n')
case('eighteen-digit-numbers',['-s',',','999999999999999997','999999999999999999'],out='999999999999999997,999999999999999998,999999999999999999\n')
case('large-negative-step',['-s',',','999999999999999999','-999999999999999999','-999999999999999999'],out='999999999999999999,0,-999999999999999999\n')
case('stdin-ignored',['2','3'],stdin='not a sequence\n',out='2\n3\n')
errors('usage-number-grammar',[[v,'2'] for v in ['','+1',' 1','1 ','1.0','-x','--','1234567890123456789']])
errors('usage-limit-grammar',[['-n',v,'1','2'] for v in ['','-0','+1','1.0',' 1','1000000000','-w']]+[['-n']])
errors('usage-count-and-zero-step',[[],['1','2','3','4','5'],['1','-0','2'],['1','000','2']])
case('zero-limit-still-validates',['-n','0','1','x'],code=2)
case('maximum-output-count',['-s',',','0','99999'],out=','.join(str(i) for i in range(100000))+'\n')

TASK = '02-trx'
multi('example-1',[(['a-z','A-Z'],'hello, world\n','HELLO, WORLD\n',0),(['abc','xy'],'aabbcc-cab\n','xxyyyy-yxy\n',0),(['aa','xy'],'abcabc\n','ybcybc\n',0)])
multi('example-2',[(['-d','aeiou'],'programming language\n','prgrmmng lngg\n',0),(['-s',' \\n'],'a   b\n\n\nc  d\n','a b\nc d\n',0),(['-s','abc','xy'],'aabbcc-cab\n','xy-yxy\n',0),(['-d','-s','0-9','a-z'],'aa1a2bb33b\n','ab\n',0)])
multi('example-3',[(['--','-d','x'],'a-d\n','axx\n',0),(['a-c-e','0-4'],'a-c-e!\n','03234!\n',0),(['\\t',' '],'x\ty\n','x y\n',0)])
errors('example-4',[['a'],['-d'],['-d','a','b'],['z-a','x'],['-x','a','b'],['a\\q','b'],['a','']])
case('empty-stream',['a-z','A-Z'])
case('empty-first-set',['','X'],stdin='abc\n',out='abc\n')
case('empty-delete-set',['-d',''],stdin='abc\n',out='abc\n')
case('empty-squeeze-set',['-s',''],stdin='aa\n\n',out='aa\n\n')
case('delete-squeeze-empty-second',['-d','-s','x',''],stdin='axxxaa\n',out='aaa\n')
case('translate-extra-targets',['ab','XYZ'],stdin='aabbcc',out='XXYYcc')
case('last-duplicate-after-range',['a-ca','1234'],stdin='abcabc',out='423423')
case('squeeze-identical-only',['-s','ab'],stdin='aaabbbaabbbccccc\n',out='ababccccc\n')
case('delete-bridges-runs',['-d','-s','x','a'],stdin='aaxxaaabxxb\n',out='abb\n')
case('squeeze-after-translation',['-s','ab','x'],stdin='abbaXaa\n',out='xXx\n')
case('newlines-ordinary',['-s','\\n'],stdin='\n\nA\n\n\nB\n',out='\nA\nB\n')
case('all-ascii-identity',['','x'],stdin=bytes(range(128)),out=bytes(range(128)))
case('all-ascii-delete',['-d',' -~'],stdin=bytes(range(128)),out=bytes(range(32))+b'\x7f')
case('escapes-all',['\\n\\t\\\\\\-','1234'],stdin=b'\n\t\\-x',out='1234x')
case('escaped-hyphen-no-range',['a\\-c','123'],stdin='a-bc',out='12b3')
multi('literal-dash-at-ends',[(['--','-ac-','1234'],'-ac','423',0),(['-','x'],'a-b','axb',0),(['a-a','X'],'aab','XXb',0)])
case('sets-after-first-are-literal',['a','-d'],stdin='aa-d',out='---d')
case('repeat-options',['-s','-d','-d','-s','0-9','a'],stdin='a1aa2bbb',out='abbb')
errors('malformed-sets',[['a\\','x'],['a','\\q'],['-s','z-a'],['-d','\\0'],['a-\\t','x']])
errors('usage-counts-and-unknown',[[],['--'],['-s'],['-d','-s','a'],['a','b','c'],['-d','a','b','c'],['--','a'],['-x']])
case('million-byte-stream',['-s','a'],stdin='a'*1000000,out='a')

TASK = '03-colalign'
case('example-1',['-r','2,3'],'name qty price\napple 3 1.25\nkiwi 12 0.5\n','name   qty  price\napple    3   1.25\nkiwi    12    0.5\n')
case('example-2',stdin='  a   bb  c\n\nddd e\n\t\n x\n',out='a    bb  c\n\nddd  e\n\nx\n')
case('example-3',['-s',',','-o',' | ','-r','3'],'id,city,pop\n1,Zürich,421878\n22,,9\n333,Bern\n','id  | city   |    pop\n1   | Zürich | 421878\n22  |        |      9\n333 | Bern\n')
case('example-4',['-s',':','-o','-'],'a:b\r\n:c:\n','a-b\n -c-\n')
errors('example-5',[['-s'],['-s','ab'],['-r','0'],['-r','1,,2'],['-x'],['file.txt']])
case('empty')
case('blank-lines-whitespace',stdin='\n \t \n\t\n',out='\n\n\n')
case('single-column-last-unpadded',stdin='a\nlong\nx',out='a\nlong\nx\n')
case('right-aligned-last',['-r','1'],'a\nlong\nx','   a\nlong\n   x\n')
case('ragged-widths-global',stdin='a b c\nlong xy\nz\n',out='a     b   c\nlong  xy\nz\n')
case('fields-empty-and-empty-lines',['-s',':','-o','|'],'::\na:b:c\n\n:',' | |\na|b|c\n\n |\n')
case('spaces-retained-explicit',['-s',':','-o','|'],' a : b\nx:y ',' a | b\nx  |y \n')
case('unicode-codepoints',['-r','1'],'界 x\nabc y\né z\n','  界  x\nabc  y\n é  z\n')
case('unicode-separator',['-s','💠','-o',':'],'a💠bb\nlong💠c','a   :bb\nlong:c\n')
case('empty-output-separator',['-o',''],'a bb\nccc d\n','a  bb\ncccd\n')
case('option-looking-output-separator',['-o','-r'],'a b\ncc d\n','a -rb\ncc-rd\n')
case('last-options-win',['-s',',','-o','!','-r','1','-s',':','-o','|','-r','2'],'a:b\nxx:yyy\n','a |  b\nxx|yyy\n')
case('duplicate-and-outside-right-columns',['-r','2,2,999'],'a b\nx xxx\n','a    b\nx  xxx\n')
case('one-cr-only',['-s',':','-o','|'],b'a\r\r\nb\r\n',b'a\r\nb\n')
case('tab-explicit-separator',['-s','\t','-o','|'],'a\t\tb\nxx\ty\t','a | |b\nxx|y|\n')
errors('usage-separator-and-missing-values',[['-s',''],['-s','é'],['-o'],['-r'],['--'],['']])
errors('usage-right-list',[['-r',v] for v in ['','01','1,02','1000','-1','+1','1,',' 1','1 2','1\t2']])
case('max-lines',stdin='x y\n'*10000,out='x  y\n'*10000)
case('max-fields',['-r','100','-o','|'],' '.join(['a']*100)+'\n'+' '.join(['bb']*100)+'\n', '|'.join(['a ']*99+[' a'])+'\n'+'|'.join(['bb']*100)+'\n')
case('no-fields-with-explicit-space',['-s',' ','-o','|'],'\n \n  \na','\n |\n ||\na\n')

TASK = '04-splitbill'
case('example-1',stdin='expense ann 30.00 ann bob cy\nexpense bob 10.00 bob cy\ntransfer cy ann 5.00\n',out='ann +15.00\nbob -5.00\ncy -10.00\n--\ncy pays ann 10.00\nbob pays ann 5.00\n')
case('example-2',stdin='# trip\nexpense dan 10.00 dan eve fay\n\n  expense\t eve 0.05   fay dan  \n',out='dan +6.64\neve -3.28\nfay -3.36\n--\nfay pays dan 3.36\neve pays dan 3.28\n')
case('example-3',stdin='expense ann 90.00 ann bob cy\nexpense bob 60.00 bob cy dee\n',out='ann +60.00\nbob +10.00\ncy -50.00\ndee -20.00\n--\ncy pays ann 50.00\ndee pays ann 10.00\ndee pays bob 10.00\n')
multi('example-4',[([], 'expense gus 12.00 hal\ntransfer hal gus 12.00\n','gus 0.00\nhal 0.00\n--\n',0),([], '', '--\n',0)])
multi('example-5',[([],s,'',1) for s in ['expense ann 5 bob\n','expense ann 5.00 bob bob\n','expense ann 0.00 bob\n','transfer ann ann 1.00\n','refund ann 1.00\n']]+[(['x'],'','',2)])
case('empty',out='--\n')
case('ignored-comments',stdin=' \t\n  #comment nonsense !\n#foo\n',out='--\n')
case('payer-only',stdin='expense a 9999999.99 a\n',out='a 0.00\n--\n')
case('payer-not-participant',stdin='expense z 0.01 b\n',out='b -0.01\nz +0.01\n--\nb pays z 0.01\n')
case('remainders-input-order',stdin='expense z 0.02 cy bob ann\n',out='ann 0.00\nbob -0.01\ncy -0.01\nz +0.02\n--\nbob pays z 0.01\ncy pays z 0.01\n')
case('payer-remainder-share',stdin='expense a 0.05 a b c\n',out='a +0.03\nb -0.02\nc -0.01\n--\nb pays a 0.02\nc pays a 0.01\n')
case('transfer-direction',stdin='transfer a b 1.23\n',out='a +1.23\nb -1.23\n--\nb pays a 1.23\n')
case('debtor-and-creditor-ties',stdin='transfer a c 1.00\ntransfer b d 1.00\n',out='a +1.00\nb +1.00\nc -1.00\nd -1.00\n--\nc pays a 1.00\nd pays b 1.00\n')
case('greedy-reselects-every-payment',stdin='transfer a d 5.00\ntransfer b d 4.00\ntransfer c e 3.00\n',out='a +5.00\nb +4.00\nc +3.00\nd -9.00\ne -3.00\n--\nd pays a 5.00\nd pays b 4.00\ne pays c 3.00\n')
case('name-byte-order',stdin='expense z9_ 0.03 a_ a0 a\n',out='a -0.01\na0 -0.01\na_ -0.01\nz9_ +0.03\n--\na pays z9_ 0.01\na0 pays z9_ 0.01\na_ pays z9_ 0.01\n')
case('leading-zero-money-crlf-final',stdin='\ttransfer\t abcdefghijklmno1  z  0000001.02 \r\nexpense z 0000001.02 z',out='abcdefghijklmno1 +1.02\nz -1.02\n--\nz pays abcdefghijklmno1 1.02\n')
case('largest-amount',stdin='transfer a z 9999999.99\ntransfer a z 9999999.99\n',out='a +19999999.98\nz -19999999.98\n--\nz pays a 19999999.98\n')
bad_inputs('malformed-names',['expense '+v+' 1.00 b\n' for v in ['A','1a','_a','abcdefghijklmnopq','a-b']]+['transfer a B 1.00\n','expense a 1.00 b #x\n'])
bad_inputs('malformed-amounts',['expense a '+v+' b\n' for v in ['0.00','0000000.00','1','1.0','1.000','.01','+1.00','-1.00','12345678.00','x.00']])
bad_inputs('record-arity-keywords',['expense a 1.00\n','expense\n','transfer a b\n','transfer a b 1.00 x\n','Expense a 1.00 b\n'])
bad_inputs('atomic-validation-late-error',['transfer a b 1.00\nexpense a 1.00 b b\n','transfer a b 1.00\nx\n','expense a 0.01 a\ntransfer b b 1.00\n'])
case('max-participants',stdin='expense z 0.01 '+' '.join(f'p{i:02}' for i in range(50))+'\n',out='p00 -0.01\n'+lines(f'p{i:02} 0.00' for i in range(1,50))+'z +0.01\n--\np00 pays z 0.01\n')
case('max-people',stdin=lines(f'expense p{i:03} 0.01 p{i:03}' for i in range(1000)),out=lines(f'p{i:03} 0.00' for i in range(1000))+'--\n')
case('max-lines',stdin='expense a 0.01 b\n'*10000,out='a +100.00\nb -100.00\n--\nb pays a 100.00\n')
errors('usage-before-stdin',[[''],['--'],['x','y']])

# Cue formatter receives explicit timing strings and text; no shifts/sorts here.
def cue(index,start,end,text):
    return f'{index}\n{start} --> {end}\n{text}\n\n'
T0,T1,T2 = '00:00:00,000','00:00:01,000','00:00:02,000'
TASK = '05-srtfix'
case('example-1',['+1500'],cue(1,T1,'00:00:03,500','Hello there.')+cue(2,'00:00:04,000','00:00:05,250','Line one\nLine two'),cue(1,'00:00:02,500','00:00:05,000','Hello there.')+cue(2,'00:00:05,500','00:00:06,750','Line one\nLine two'))
case('example-2',['-1000'],'7\n00:00:02,000 --> 00:00:04,000\nsecond\n\n\n3\n00:00:00,500 --> 00:00:01,200\nfirst\n\n5\n00:00:00,100 --> 00:00:01,000\ngone\n  \n9\n00:01:00,000 --> 00:01:02,000\n  third, indented\n',cue(1,T0,'00:00:00,200','first')+cue(2,T1,'00:00:03,000','second')+cue(3,'00:00:59,000','00:01:01,000','  third, indented'))
multi('example-3',[(['99999'],cue(1,'00:00:05,000','00:00:06,000','late')+cue(2,'00:00:05,000','00:00:05,001','same start'),cue(1,'00:01:44,999','00:01:45,999','late')+cue(2,'00:01:44,999','00:01:45,000','same start'),0),(['0'],'1\r\n00:59:59,999 --> 01:00:00,999\r\nA\r\n\r\n2\r\n00:00:01,000 --> 00:00:02,000\r\nB\r\n',cue(1,T1,T2,'B')+cue(2,'00:59:59,999','01:00:00,999','A'),0)])
bad_inputs('example-4',['1\n00:00:01,000 -> 00:00:02,000\nx\n','1\n00:00:03,000 --> 00:00:02,000\nx\n','1\n00:00:01,000 --> 00:00:02,000\n','1\n00:00:61,000 --> 00:00:62,000\nx\n'],['0'])
errors('example-5',[[],['1.5'],['++1'],['1','2']])
case('empty',['0'])
case('only-blank-lines',['-999999999'],' \n\t\n\r\n  \t ')
case('ignored-index-boundaries',['-0'],cue('000000000',T1,T2,'zero')+cue('999999999',T0,T1,'max'),cue(1,T0,T1,'max')+cue(2,T1,T2,'zero'))
case('one-millisecond-clamp',['-999'],cue(42,T0,T1,'x'),cue(1,T0,'00:00:00,001','x'))
case('end-exactly-zero-dropped',['-1000'],cue(1,T0,T1,'drop'))
case('all-before-zero',['-999999999'],cue(1,T0,T1,'drop'))
case('clamped-start-tie-stable',['-1000'],cue(8,'00:00:00,900',T2,'first')+cue(9,T0,'00:00:01,001','second'),cue(1,T0,T1,'first')+cue(2,T0,'00:00:00,001','second'))
case('overlapping-cues-preserved',['0'],cue(9,T1,'00:00:09,000','long')+cue(8,T2,'00:00:03,000','overlap'),cue(1,T1,'00:00:09,000','long')+cue(2,T2,'00:00:03,000','overlap'))
case('text-preserved-utf8',['000000000'],'001\n00:00:00,000 --> 00:00:00,001\n  café \n\tline\t',cue(1,T0,'00:00:00,001','  café \n\tline\t'))
case('hour-carry',['+1'],cue(1,'00:59:59,999','01:59:59,999','carry'),cue(1,'01:00:00,000','02:00:00,000','carry'))
case('time-upper-bound',['1'],cue(1,'99:59:59,997','99:59:59,998','near limit'),cue(1,'99:59:59,998','99:59:59,999','near limit'))
case('one-cr-only',['0'],b'1\r\n00:00:00,000 --> 00:00:00,001\r\nx\r\r\n',cue(1,T0,'00:00:00,001','x\r'))
bad_inputs('invalid-index',[cue(v,T0,T1,'x') for v in ['-1','+1','','1 ',' 1','1234567890','a']],['0'])
bad_inputs('invalid-times',[f'1\n{v} --> {T2}\nx\n' for v in ['0:00:00,000','00:60:00,000','00:00:60,000','00:00:00.000','00:00:00,00','000:00:00,000']],['0'])
bad_inputs('invalid-timing-spaces',['1\n'+v+'\nx\n' for v in [T0+'  --> '+T1,T0+' -->  '+T1,' '+T0+' --> '+T1,T0+' --> '+T1+' ',T0+'\t--> '+T1]],['0'])
bad_inputs('invalid-equal-and-missing-text',[cue(1,T1,T1,'x'),'1\n'+T0+' --> '+T1+'\n \t\n','1\n','1\n'+T0+' --> '+T1+'\n\ntext\n'],['0'])
case('atomic-late-invalid',['0'],cue(1,T0,T1,'valid')+'bad\n',code=1)
case('max-cues',['0'],stdin=''.join(cue(99,T0,T1,'x') for _ in range(10000)),out=''.join(cue(i,T0,T1,'x') for i in range(1,10001)))
errors('usage-offset-grammar',[[v] for v in ['','+','-',' 1','1 ','1234567890','--1','+0000000000']])
case('max-offset-empty',['+999999999'])

TASK = '06-libfines'
BOOKS = '# id|title|rate|cap\nB1|Dune|25|500\nB2|The Hobbit|10|100\nB3|SICP|50|2000\n'
LOANS = 'ann|B1|1|15|20\nann|B2|3|17|-\nbob|B3|5|19|19\ncy|B9|2|16|30\nbob|B2|20|34|39\n\ndee|B1|40|54|-\n'
case('example-1',['books.txt','loans.txt','40'],out='ann loans=2 late=2 fine=2.25\n  B1 Dune days=5 fine=1.25\n  B2 The Hobbit days=23 fine=1.00\nbob loans=2 late=1 fine=0.50\n  B2 The Hobbit days=5 fine=0.50\ndee loans=1 late=0 fine=0.00\ntotal=2.75 skipped=1\n',setup={'books.txt':BOOKS,'loans.txt':LOANS})
case('example-2',['b.txt','l.txt','9'],out='zed loans=1 late=1 fine=3.00\n  Y Big Book days=4 fine=3.00\namy loans=2 late=2 fine=1.00\n  Y Big Book days=1 fine=1.00\n  X-1 Café Stories days=7 fine=0.00\ntotal=4.00 skipped=1\n',setup={'b.txt':'X-1|Café Stories|0|0\nY|Big Book|100|300\n','l.txt':'zed|Y|1|2|6\namy|Y|1|2|3\namy|X-1|1|2|-\nzed|Q|1|2|3\r\n'})
case('example-3',['books.txt','empty.txt','0'],out='total=0.00 skipped=0\n',setup={'books.txt':BOOKS,'empty.txt':''})
multi('example-4',[(['short.txt','loans.txt','1'],'','',1),(['books.txt','early.txt','1'],'','',1),(['dup.txt','loans.txt','1'],'','',1),(['books.txt','missing.txt','1'],'','',1),(['books.txt','loans.txt'],'','',2),(['books.txt','loans.txt','-1'],'','',2)],{'books.txt':BOOKS,'loans.txt':LOANS,'short.txt':'B1|Dune|25\n','early.txt':'ann|B1|10|5|-\n','dup.txt':'B1|Dune|25|500\nB1|Again|1|1\n'})
case('empty-files',['b','l','000000'],out='total=0.00 skipped=0\n',setup={'b':'','l':''})
case('only-comments',['b','l','1'],out='total=0.00 skipped=0\n',setup={'b':'# anything\n\n#x\r\n','l':'\n#bad|fields\n'})
case('all-skipped',['b','l','9'],out='total=0.00 skipped=2\n',setup={'b':'','l':'ann|X|0|0|-\nbob|Y|1|1|9\n'})
case('matched-not-late-members',['b','l','5'],out='ann loans=1 late=0 fine=0.00\nzed loans=2 late=0 fine=0.00\ntotal=0.00 skipped=0\n',setup={'b':'X|T|1|99\n','l':'zed|X|0|5|-\nann|X|0|5|1\nzed|X|0|9|-\n'})
case('zero-rate-zero-cap-late',['b','l','5'],out='a loans=2 late=2 fine=0.00\n  X Zero rate days=5 fine=0.00\n  Y Zero cap days=5 fine=0.00\ntotal=0.00 skipped=0\n',setup={'b':'X|Zero rate|0|99\nY|Zero cap|99|0\n','l':'a|X|0|0|-\na|Y|0|0|-\n'})
case('cap-below-at-above',['b','l','0'],out='a loans=4 late=4 fine=0.18\n  X T days=1 fine=0.02\n  X T days=2 fine=0.04\n  X T days=3 fine=0.06\n  X T days=4 fine=0.06\ntotal=0.18 skipped=0\n',setup={'b':'X|T|2|6\n','l':'a|X|0|0|1\na|X|0|0|2\na|X|0|0|3\na|X|0|0|4\n'})
case('returned-after-today',['b','l','1'],out='a loans=1 late=1 fine=1.00\n  X T days=10 fine=1.00\ntotal=1.00 skipped=0\n',setup={'b':'X|T|10|999\n','l':'a|X|0|0|10\n'})
case('fine-order-and-late-file-order',['b','l','20'],out='a loans=2 late=2 fine=0.30\n  Y Why days=2 fine=0.20\n  X Ex days=1 fine=0.10\nz loans=1 late=1 fine=0.30\n  X Ex days=3 fine=0.30\nb loans=1 late=1 fine=0.10\n  X Ex days=1 fine=0.10\ntotal=0.70 skipped=0\n',setup={'b':'X|Ex|10|999\nY|Why|10|999\n','l':'z|X|0|0|3\na|Y|0|0|2\nb|X|0|0|1\na|X|0|0|1\n'})
case('exact-ids-case-sensitive',['b','l','1'],out='a loans=2 late=2 fine=0.03\n  A Upper days=1 fine=0.01\n  a Lower days=1 fine=0.02\ntotal=0.03 skipped=1\n',setup={'b':'A|Upper|1|9\na|Lower|2|9\n','l':'a|A|0|0|-\na|a|0|0|-\nz|B|0|0|-\n'})
case('titles-leading-zero-crlf-final',['book file','loan file','000002'],out='a12345678901 loans=1 late=1 fine=0.02\n  ABCdef0123--   Café   days=2 fine=0.02\ntotal=0.02 skipped=0\n',setup={'book file':'ABCdef0123--|  Café  |000001|000099\r\n','loan file':'a12345678901|ABCdef0123--|000000|000000|-'})
case('maximum-day-rate-cap',['b','l','999999'],out='a loans=1 late=1 fine=9999.99\n  X T days=999999 fine=9999.99\ntotal=9999.99 skipped=0\n',setup={'b':'X|T|999999|999999\n','l':'a|X|0|0|-\n'})
# Each malformed file is a separate argv run under a shared setup tree.
BAD_BOOKS = ['X|T|1\n','X||1|1\n','X|T|1|1|x\n','X|T|-1|1\n','X|T|1|1000000\n','X_|T|1|1\n','ABCDEFGHIJKLM|T|1|1\n',' X|T|1|1\n','X|T| 1|1\n',' \n','X|T|1|1\nX|T|2|2\n']
multi('invalid-books',[([f'b{i}','l','1'],'','',1) for i in range(len(BAD_BOOKS))],{'l':'',**{f'b{i}':v for i,v in enumerate(BAD_BOOKS)}})
BAD_LOANS = ['a|X|1|0|-\n','a|X|2|3|1\n','a|X|0|0\n','A|X|0|0|-\n','a_|X|0|0|-\n','abcdefghijklm|X|0|0|-\n','a|X_|0|0|-\n','a|X|+1|2|-\n','a|X|0|0|x\n','a|X|0|0|1000000\n','a|X|0|0|-|extra\n',' \n']
multi('invalid-loans',[(['b',f'l{i}','1'],'','',1) for i in range(len(BAD_LOANS))],{'b':'X|T|1|1\n',**{f'l{i}':v for i,v in enumerate(BAD_LOANS)}})
case('invalid-unknown-loan-still-invalid',['b','l','0'],code=1,setup={'b':'','l':'a|Unknown|10|0|-\n'})
case('late-invalid-atomic',['b','l','5'],code=1,setup={'b':'X|T|1|9\n','l':'a|X|0|0|-\nbad\n'})
errors('file-errors',[['missing','l','1'],['b','missing','1'],['dir','l','1'],['b','dir','1']],1,{'b':'','l':'','dir':None})
errors('usage-before-files',[[],['missing'],['missing','missing'],['missing','missing','1','x']]+[['missing','missing',v] for v in ['','-1','+1',' 1','1.0','1234567']])
case('stdin-ignored',['b','l','1'],stdin='bad data\n',out='total=0.00 skipped=0\n',setup={'b':'','l':''})
case('max-books',['b','l','0'],out='total=0.00 skipped=0\n',setup={'b':lines(f'B{i}|T|0|0' for i in range(10000)),'l':''})
case('max-loans',['b','l','0'],out='a loans=100000 late=0 fine=0.00\ntotal=0.00 skipped=0\n',setup={'b':'X|T|1|1\n','l':'a|X|0|0|0\n'*100000})
case('large-total',['b','l','999999'],out='a loans=10000 late=10000 fine=99999900.00\n'+'  X T days=999999 fine=9999.99\n'*10000+'total=99999900.00 skipped=0\n',setup={'b':'X|T|999999|999999\n','l':'a|X|0|0|-\n'*10000})

TASK = '07-leaderboard'
case('example-1',stdin='SCORE ann 50\nSCORE bob 70\nSCORE cy 50\nSCORE dee 20\nSCORE ann 5\nTOP 3\nRANK cy\nRANK ann\nSCORE ann -5\nTOP 10\nRANK dee\nRANK zed\nCOUNT\n',out='TOTAL 50\nTOTAL 70\nTOTAL 50\nTOTAL 20\nTOTAL 55\nTOP 1:bob:70 2:ann:55 3:cy:50\nRANK 3 50\nRANK 2 55\nTOTAL 50\nTOP 1:bob:70 2:ann:50 2:cy:50 4:dee:20\nRANK 4 20\nERR unknown player\nCOUNT 4\n')
case('example-2',stdin='SCORE a 10\nSCORE b 20\nSCORE c 30\nSCORE d 40\nSCORE e 50\nAROUND c 1\nAROUND e 2\nAROUND a 0\nREMOVE c\nAROUND b 1\nREMOVE c\nSCORE f 0\nSCORE g -3\nTOP 9\nCOUNT\n',out='TOTAL 10\nTOTAL 20\nTOTAL 30\nTOTAL 40\nTOTAL 50\nAROUND 2:d:40 3:c:30 4:b:20\nAROUND 1:e:50 2:d:40 3:c:30\nAROUND 5:a:10\nOK\nAROUND 2:d:40 3:b:20 4:a:10\nERR unknown player\nTOTAL 0\nTOTAL -3\nTOP 1:e:50 2:d:40 3:b:20 4:a:10 5:f:0 6:g:-3\nCOUNT 6\n')
case('example-3',stdin='TOP 5\nscore a 1\nSCORE A 1\nSCORE a 1.5\nSCORE a 1234567\nSCORE a\nTOP 0\nTOP 1000\nAROUND a\nCOUNT \n\nSCORE  a 1\nSCORE a +1\nRANK a b\nSCORE a -0\nTOP 1\n',out='TOP\n'+'ERR bad command\n'*13+'TOTAL 0\nTOP 1:a:0\n')
case('example-4',['x'],code=2)
case('empty')
case('unknown-and-empty-queries',stdin='TOP 999\nCOUNT\nRANK a\nAROUND a 0\nREMOVE a\n',out='TOP\nCOUNT 0\n'+'ERR unknown player\n'*3)
case('top-cuts-through-tie',stdin='SCORE c 5\nSCORE b 5\nSCORE a 5\nTOP 2\nRANK c\n',out='TOTAL 5\n'*3+'TOP 1:a:5 1:b:5\nRANK 1 5\n')
case('around-by-position-in-tie',stdin='SCORE d 1\nSCORE c 1\nSCORE b 1\nSCORE a 1\nAROUND c 1\nAROUND a 000\nAROUND d 999\n',out='TOTAL 1\n'*4+'AROUND 1:b:1 1:c:1 1:d:1\nAROUND 1:a:1\nAROUND 1:a:1 1:b:1 1:c:1 1:d:1\n')
case('competition-rank-gaps',stdin='SCORE a 9\nSCORE b 9\nSCORE c 7\nSCORE d 7\nSCORE e -1\nTOP 9\n',out='TOTAL 9\nTOTAL 9\nTOTAL 7\nTOTAL 7\nTOTAL -1\nTOP 1:a:9 1:b:9 3:c:7 3:d:7 5:e:-1\n')
case('remove-recreate-from-zero',stdin='SCORE a 100\nREMOVE a\nCOUNT\nSCORE a -2\nRANK a\nREMOVE a\nREMOVE a\n',out='TOTAL 100\nOK\nCOUNT 0\nTOTAL -2\nRANK 1 -2\nOK\nERR unknown player\n')
case('remove-recomputes-ranks',stdin='SCORE a 5\nSCORE b 5\nSCORE c 1\nREMOVE a\nRANK c\nREMOVE b\nRANK c\n',out='TOTAL 5\nTOTAL 5\nTOTAL 1\nOK\nRANK 2 1\nOK\nRANK 1 1\n')
case('score-up-down-reorders',stdin='SCORE a 2\nSCORE b 1\nSCORE b 2\nTOP 2\nSCORE b -4\nTOP 2\n',out='TOTAL 2\nTOTAL 1\nTOTAL 3\nTOP 1:b:3 2:a:2\nTOTAL -1\nTOP 1:a:2 2:b:-1\n')
case('zero-leading-zeros',stdin='SCORE a -0\nSCORE b 000001\nSCORE b -000001\nTOP 9\n',out='TOTAL 0\nTOTAL 1\nTOTAL 0\nTOP 1:a:0 1:b:0\n')
case('name-length-byte-order',stdin='SCORE z 0\nSCORE a_ 0\nSCORE a0 0\nSCORE abcdefghijklmnop 0\nSCORE a 0\nTOP 999\n',out='TOTAL 0\n'*5+'TOP 1:a:0 1:a0:0 1:a_:0 1:abcdefghijklmnop:0 1:z:0\n')
case('crlf-and-final-line',stdin=b'SCORE a 1\r\nRANK a\r\nCOUNT',out='TOTAL 1\nRANK 1 1\nCOUNT 1\n')
case('strict-spacing-state',stdin='SCORE a 5\n SCORE a 9\nSCORE a 9 \nSCORE\ta 9\nSCORE  a 9\nCOUNT\r\r\nTOP 1\n',out='TOTAL 5\n'+'ERR bad command\n'*5+'TOP 1:a:5\n')
case('malformed-names',stdin=lines('SCORE '+v+' 1' for v in ['A','1a','_a','a-b','abcdefghijklmnopq'])+'COUNT\n',out='ERR bad command\n'*5+'COUNT 0\n')
case('malformed-numbers',stdin=lines(['SCORE a '+v for v in ['+1','1.0','1234567','--1']]+['TOP '+v for v in ['0','01','1000','-1']]+['AROUND a '+v for v in ['-1','+1','1000']]),out='ERR bad command\n'*11)
case('wrong-count-unknown-commands',stdin=lines(['SCORE','RANK','AROUND a','REMOVE a b','TOP 1 x','COUNT x','NEW','count','']),out='ERR bad command\n'*9)
case('around-clipped-both-ends',stdin='SCORE a 3\nSCORE b 2\nSCORE c 1\nAROUND a 1\nAROUND c 1\nAROUND b 999\n',out='TOTAL 3\nTOTAL 2\nTOTAL 1\nAROUND 1:a:3 2:b:2\nAROUND 2:b:2 3:c:1\nAROUND 1:a:3 2:b:2 3:c:1\n')
multi('flush-lockstep',[([], 'SCORE a 1\nRANK a\nCOUNT\nSCORE b 9\n','TOTAL 1\nRANK 1 1\nCOUNT 1\n',None,3),([], 'COUNT\nTOP 1\n','COUNT 0\nTOP\n',0)])
case('max-players-top-and-around',stdin=lines(f'SCORE p{i:03} 0' for i in range(1000))+'TOP 999\nAROUND p500 999\nCOUNT\n',out='TOTAL 0\n'*1000+'TOP'+''.join(f' 1:p{i:03}:0' for i in range(999))+'\nAROUND'+''.join(f' 1:p{i:03}:0' for i in range(1000))+'\nCOUNT 1000\n')
case('max-commands',stdin='COUNT\n'*20000,out='COUNT 0\n'*20000)
multi('billion-total-boundaries',[([], 'SCORE a 999999\n'*1000+'SCORE a 1000\nRANK a\n',lines(f'TOTAL {i*999999}' for i in range(1,1001))+'TOTAL 1000000000\nRANK 1 1000000000\n',0),([], 'SCORE a -999999\n'*1000+'SCORE a -1000\nRANK a\n',lines(f'TOTAL {-i*999999}' for i in range(1,1001))+'TOTAL -1000000000\nRANK 1 -1000000000\n',0)])
errors('usage-arguments',[[''],['--'],['1','2']])

TASK = '08-connect4'
EMPTY_BOARD = '......./......./......./......./......./.......\n'
def drops(columns): return lines('DROP '+c for c in columns.split())
def played(rows,suffix=''):
    # Explicit landing rows; parity formats the already-worked player sequence.
    rows = rows.split()
    return lines(f'PLAYED {"XO"[i%2]} {r}'+(suffix if i == len(rows)-1 else '') for i,r in enumerate(rows))
case('example-1',stdin='DROP 4\nDROP 4\nDROP 3\nDROP 3\nDROP 5\nDROP 5\nSTATUS\nDROP 2\nDROP 1\nSTATUS\nBOARD\nUNDO\nSTATUS\nDROP 6\nNEW\nBOARD\nUNDO\n',out='PLAYED X 1\nPLAYED O 2\nPLAYED X 1\nPLAYED O 2\nPLAYED X 1\nPLAYED O 2\nTURN X\nPLAYED X 1 WIN\nERR game over\nWIN X\n......./......./......./......./..OOO../.XXXX..\nUNDONE 2\nTURN X\nPLAYED X 1 WIN\nOK\n'+EMPTY_BOARD+'ERR nothing to undo\n')
DIAG = '1 2 2 3 3 4 3 4 4 7 4'
case('example-2',stdin=drops(DIAG)+'BOARD\nSTATUS\n',out=played('1 1 2 1 2 1 3 2 3 1 4',' WIN')+'......./......./...X.../..XX.../.XXO.../XOOO..O\nWIN X\n')
case('example-3',stdin=drops('1 1 1 1 1 1 1')+'BOARD\nDROP 0\nDROP 8\ndrop 1\nDROP 01\nDROP  2\nUNDO 1\n\nSTATUS\n',out=played('1 2 3 4 5 6')+'ERR column full\nO....../X....../O....../X....../O....../X......\n'+'ERR bad command\n'*7+'TURN X\n')
case('example-4',['7'],code=2)
case('empty')
case('initial-board-status-undo',stdin='STATUS\nBOARD\nUNDO\nSTATUS\n',out='TURN X\n'+EMPTY_BOARD+'ERR nothing to undo\nTURN X\n')
case('vertical-x',stdin=drops('1 2 1 2 1 2 1')+'BOARD\nSTATUS\n',out=played('1 1 2 2 3 3 4',' WIN')+'......./......./X....../XO...../XO...../XO.....\nWIN X\n')
case('vertical-o',stdin=drops('1 2 1 2 3 2 3 2')+'STATUS\nBOARD\n',out=played('1 1 2 2 1 3 2 4',' WIN')+'WIN O\n......./......./.O...../.O...../XOX..../XOX....\n')
case('horizontal-o',stdin=drops('7 1 7 2 6 3 6 4')+'STATUS\n',out=played('1 1 2 1 1 1 2 1',' WIN')+'WIN O\n')
case('opposite-diagonal-x',stdin=drops('7 6 6 5 5 4 5 4 4 1 4')+'BOARD\nSTATUS\n',out=played('1 1 2 1 2 1 3 2 3 1 4',' WIN')+'......./......./...X.../...XX../...OXX./O..OOOX\nWIN X\n')
case('diagonal-o',stdin=drops('7 '+DIAG)+'STATUS\nBOARD\n',out=played('1 1 1 2 1 2 1 3 2 3 2 4',' WIN')+'WIN O\n......./......./...O.../..OO.../.OOX..X/OXXX..X\n')
case('five-in-row-bridge',stdin=drops('1 6 2 7 4 6 5 7 3')+'BOARD\n',out=played('1 1 1 1 1 2 1 2 1',' WIN')+'......./......./......./......./.....OO/XXXXXOO\n')
case('undo-all-reverse-history',stdin=drops('3 4 3')+'UNDO\nUNDO\nUNDO\nUNDO\nBOARD\nSTATUS\n',out=played('1 1 2')+'UNDONE 3\nUNDONE 4\nUNDONE 3\nERR nothing to undo\n'+EMPTY_BOARD+'TURN X\n')
case('undo-reuses-row-turn',stdin=drops('2 2')+'UNDO\nSTATUS\nDROP 2\nBOARD\n',out=played('1 2')+'UNDONE 2\nTURN O\nPLAYED O 2\n......./......./......./......./.O...../.X.....\n')
case('full-column-error-preserves-turn',stdin=drops('7 7 7 7 7 7 7')+'STATUS\nDROP 6\nUNDO\nUNDO\nDROP 7\n',out=played('1 2 3 4 5 6')+'ERR column full\nTURN X\nPLAYED X 1\nUNDONE 6\nUNDONE 7\nPLAYED O 6\n')
case('win-error-priority-and-undo',stdin=drops('1 2 1 2 1 2 1')+'DROP 0\nDROP 2\nUNDO\nSTATUS\nDROP 3\nSTATUS\n',out=played('1 1 2 2 3 3 4',' WIN')+'ERR bad command\nERR game over\nUNDONE 1\nTURN X\nPLAYED X 1\nTURN O\n')
case('new-clears-history-and-winner',stdin=drops('1 2 1 2 1 2 1')+'NEW\nUNDO\nSTATUS\nBOARD\nDROP 7\n',out=played('1 1 2 2 3 3 4',' WIN')+'OK\nERR nothing to undo\nTURN X\n'+EMPTY_BOARD+'PLAYED X 1\n')
case('new-running-and-repeated',stdin='DROP 1\nNEW\nNEW\nBOARD\nUNDO\n',out='PLAYED X 1\nOK\nOK\n'+EMPTY_BOARD+'ERR nothing to undo\n')
DRAW_COLUMNS = '1 1 1 1 1 1 2 2 2 2 2 2 5 3 3 3 3 3 3 4 4 4 4 4 4 5 5 5 5 5 6 6 6 6 6 7 7 7 7 7 7 6'
DRAW_ROWS = '1 2 3 4 5 6 1 2 3 4 5 6 1 1 2 3 4 5 6 1 2 3 4 5 6 2 3 4 5 6 1 2 3 4 5 1 2 3 4 5 6 6'
DRAW_BOARD = 'OOXXOOX/XXOOXXO/OOXXOOX/XXOOXXO/OOXXOOX/XXOOXXO\n'
case('full-board-draw',stdin=drops(DRAW_COLUMNS)+'STATUS\nBOARD\nDROP 1\nUNDO\nSTATUS\nDROP 6\nSTATUS\n',out=played(DRAW_ROWS,' DRAW')+'DRAW\n'+DRAW_BOARD+'ERR game over\nUNDONE 6\nTURN O\nPLAYED O 6 DRAW\nDRAW\n')
case('malformed-drop-grammar',stdin=lines(['DROP '+v for v in ['0','8','-1','+1','01','1.0','a','1 2','']])+ 'STATUS\n',out='ERR bad command\n'*9+'TURN X\n')
case('malformed-other-commands-state',stdin='DROP 1\n'+lines([' BOARD','BOARD ','status','NEW x','UNDO x','DROP\t2','DROP  2','','UNKNOWN'])+'BOARD\nSTATUS\n',out='PLAYED X 1\n'+'ERR bad command\n'*9+'......./......./......./......./......./X......\nTURN O\n')
case('crlf-final-one-cr',stdin=b'DROP 7\r\nSTATUS\r\nBOARD\r\r\nUNDO',out='PLAYED X 1\nTURN O\nERR bad command\nUNDONE 7\n')
multi('flush-lockstep',[([], 'DROP 1\nSTATUS\nBOARD\nDROP 2\n','PLAYED X 1\nTURN O\n......./......./......./......./......./X......\n',None,3),([], 'STATUS\n','TURN X\n',0)])
case('max-commands',stdin='NEW\n'*100000,out='OK\n'*100000)
errors('usage-arguments',[[''],['--'],['x','y']])

TASK = '09-polls'
case('example-1',['data'],stdin='CREATE lunch pizza sushi tacos\nVOTE lunch ann sushi\nVOTE lunch bob pizza\nVOTE lunch ann pizza\nVOTE lunch ann pizza\nVOTE lunch cy salad\nVOTE dinner ann pizza\nRESULT lunch\nCLOSE lunch\nVOTE lunch dee tacos\nCLOSE lunch\nRESULT lunch\nCREATE lunch a b\nCREATE x only\nCREATE y a a\nRESULT nope\nvote lunch ann pizza\n',out='OK\nVOTED\nVOTED\nCHANGED\nUNCHANGED\nERR no such option\nERR no such poll\nlunch open pizza=2 sushi=0 tacos=0\nOK\nERR poll closed\nERR poll closed\nlunch closed pizza=2 sushi=0 tacos=0\nERR poll exists\nERR bad command\nERR bad command\nERR no such poll\nERR bad command\n')
multi('example-2',[(['d'],'CREATE p yes no\nVOTE p ann yes\nVOTE p bob no\nVOTE p cy no\n','OK\nVOTED\nVOTED\n',None,3),(['d'],'RESULT p\nVOTE p bob yes\nRESULT p\n','p open yes=1 no=1\nCHANGED\np open yes=2 no=0\n',0)])
multi('example-3',[(['d'],'RESULT a\nVOTE a ann y\n','a open x=0 y=0\nVOTED\n',0),(['d'],'RESULT a\n','a open x=0 y=1\n',0)],{'d/polls.log':'CREATE a x y\nVOTE a bob x'})
multi('example-4',[(['d1'],'RESULT a\n','',1),(['d2'],'RESULT a\n','',1),(['f'],'','',1),([], '', '',2),(['a','b'],'','',2)],{'d1/polls.log':'CREATE a x y\nVOTE a bob z\n','d2/polls.log':'CREATE a x y\nVOTE a bob x\nVOTE a bob x\n','f':'regular file'})
multi('empty-and-existing-directory',[(['d'],'','',0),(['d'],'RESULT p\n','ERR no such poll\n',0)],{'d':None})
multi('normal-restarts-and-independent-polls',[(['d'],'CREATE p b a\nCREATE q a b\nVOTE p u a\nVOTE q u b\n','OK\nOK\nVOTED\nVOTED\n',0),(['d'],'RESULT p\nRESULT q\nVOTE p u b\nCLOSE q\n','p open b=0 a=1\nq open a=0 b=1\nCHANGED\nOK\n',0),(['d'],'RESULT p\nRESULT q\n','p open b=1 a=0\nq closed a=0 b=1\n',0)])
case('option-and-name-boundaries',['-'],stdin='CREATE 0123456789ab a b c d e f g h i\nVOTE 0123456789ab abcdefghijkl i\nRESULT 0123456789ab\n',out='OK\nVOTED\n0123456789ab open a=0 b=0 c=0 d=0 e=0 f=0 g=0 h=0 i=1\n')
case('error-priority-and-no-mutation',['d'],stdin='CREATE p x y\nVOTE absent u z\nCLOSE absent\nVOTE p u z\nVOTE p u x\nCLOSE p\nVOTE p u z\nCLOSE p\nCREATE p a a\nCREATE p a b\nRESULT p\n',out='OK\nERR no such poll\nERR no such poll\nERR no such option\nVOTED\nOK\nERR poll closed\nERR poll closed\nERR bad command\nERR poll exists\np closed x=1 y=0\n')
BAD_POLL_COMMANDS = ['create p a b','CREATE p a','CREATE p a b c d e f g h i j','CREATE p a a','CREATE P a b','CREATE abcdefghijklm a b','CREATE p a b ',' CREATE p a b','CREATE  p a b','CREATE\tp a b','VOTE p u','VOTE p U a','VOTE p u a extra','CLOSE','RESULT p extra','RESULT p\r\r','','COUNT']
case('strict-command-grammar',['d'],stdin=lines(BAD_POLL_COMMANDS)+'RESULT p\n',out='ERR bad command\n'*len(BAD_POLL_COMMANDS)+'ERR no such poll\n')
multi('crlf-final-and-unchanged-restart',[(['d'],'CREATE p x y\r\nVOTE p u x\r\nVOTE p u x\r\nRESULT p','OK\nVOTED\nUNCHANGED\np open x=1 y=0\n',0),(['d'],'RESULT p\n','p open x=1 y=0\n',0)])
multi('kill-create',[(['d'],'CREATE p a b\nCREATE q x y\n','OK\n',None,1),(['d'],'RESULT p\nRESULT q\n','p open a=0 b=0\nERR no such poll\n',0)])
multi('kill-changed-and-close',[(['d'],'CREATE p a b\nVOTE p u a\nVOTE p u b\nCLOSE p\n','OK\nVOTED\nCHANGED\n',None,3),(['d'],'RESULT p\nCLOSE p\nCREATE q x y\n','p open a=0 b=1\nOK\n',None,2),(['d'],'RESULT p\nVOTE p v a\nRESULT q\n','p closed a=0 b=1\nERR poll closed\nERR no such poll\n',0)])
multi('kill-read-errors-unchanged',[(['d'],'CREATE p a b\nVOTE p u a\nVOTE p u a\nVOTE p u z\nRESULT p\nVOTE p v b\n','OK\nVOTED\nUNCHANGED\nERR no such option\np open a=1 b=0\n',None,5),(['d'],'RESULT p\nVOTE p u b\nRESULT p\n','p open a=1 b=0\nCHANGED\np open a=0 b=1\n',0)])
multi('torn-only-file',[(['d'],'RESULT p\nCREATE p a b\n','ERR no such poll\nOK\n',0),(['d'],'RESULT p\n','p open a=0 b=0\n',0)],{'d/polls.log':'CREATE p x y'})
multi('torn-close-and-killed-append',[(['d'],'RESULT p\nVOTE p u b\nCLOSE p\n','p open a=1 b=0\nCHANGED\n',None,2),(['d'],'RESULT p\nCLOSE p\n','p open a=0 b=1\nOK\n',0),(['d'],'RESULT p\n','p closed a=0 b=1\n',0)],{'d/polls.log':'CREATE p a b\nVOTE p u a\nCLOSE p'})
multi('torn-after-readonly-start',[(['d'],'RESULT p\n','p open a=0 b=0\n',0),(['d'],'VOTE p u b\n','VOTED\n',0),(['d'],'RESULT p\n','p open a=0 b=1\n',0)],{'d/polls.log':'CREATE p a b\nVOTE p torn a'})
# Complete invalid records are fatal, unlike a torn last line. All are isolated.
BAD_JOURNALS = ['\n','CREATE p a b\r\n','CREATE p a b \n','CREATE  p a b\n','create p a b\n','CREATE p a\n','CREATE p a a\n','CREATE P a b\n','CREATE p a b\nCREATE p x y\n','VOTE p u a\n','CLOSE p\n','RESULT p\n','CREATE p a b\nRESULT p\n','CREATE p a b\nVOTE p u z\n','CREATE p a b\nCLOSE p\nCLOSE p\n','CREATE p a b\nCLOSE p\nVOTE p u a\n','CREATE p a b\nVOTE p u a\nVOTE p u a\n']
multi('invalid-complete-journals',[([f'd{i}'],'RESULT p\n','',1) for i in range(len(BAD_JOURNALS))],{f'd{i}/polls.log':v for i,v in enumerate(BAD_JOURNALS)})
multi('invalid-before-valid-tail-and-torn',[(['d'],'RESULT p\n','',1),(['d'],'RESULT p\n','',1),(['e'],'RESULT p\n','',1)],{'d/polls.log':'CREATE p a b\nVOTE p u z\nCREATE q x y\n','e/polls.log':'CREATE p a b\nBAD\ntorn'})
case('valid-planted-changes-closed',['d'],stdin='RESULT p\nRESULT q\nVOTE p u a\n',out='p closed b=1 a=1\nq open x=0 y=0\nERR poll closed\n',setup={'d/polls.log':'CREATE p b a\nCREATE q x y\nVOTE p u b\nVOTE p v b\nVOTE p u a\nCLOSE p\n'})
errors('directory-errors',[['f'],['absent/d'],['f/d'],['j']],1,{'f':'file','j/polls.log':None})
errors('usage-before-directory',[[],['f','x']],2,{'f':'file'})
multi('directory-spaces-and-parent',[(['parent/a b'],'CREATE p x y\n','OK\n',0),(['parent/a b'],'RESULT p\n','p open x=0 y=0\n',0)],{'parent':None})
case('max-commands',['d'],stdin='RESULT p\n'*10000,out='ERR no such poll\n'*10000)
case('max-polls',['d'],stdin=lines(f'CREATE p{i:03} x y' for i in range(1000))+'RESULT p999\nRESULT p000\n',out='OK\n'*1000+'p999 open x=0 y=0\np000 open x=0 y=0\n')
# 1 CREATE + 99999 alternating VOTEs = 100000 valid records; final vote is a.
case('max-journal-records',['d'],stdin='RESULT p\n',out='p open a=1 b=0\n',setup={'d/polls.log':'CREATE p a b\n'+('VOTE p u a\nVOTE p u b\n'*49999)+'VOTE p u a\n'})

TASK = '10-robots'
R1 = '#######\n#A..*.#\n#.##..#\n#..*B.#\n#######\n\nA:EEEE\nB:NNW.\n'
case('example-1',['4'],R1,'#######\n#..AB.#\n#.##..#\n#..*..#\n#######\nA 3 1 moves=2 bumps=2 coins=0\nB 4 1 moves=2 bumps=1 coins=1\n')
case('example-2',['1'],'..BA.\n.CD..\n\nA:E\nB:E\nC:E\nD:E\n','...BA\n.C.D.\nA 4 0 moves=1 bumps=0 coins=0\nB 3 0 moves=1 bumps=0 coins=0\nC 1 1 moves=0 bumps=1 coins=0\nD 3 1 moves=1 bumps=0 coins=0\n')
R3 = '.*.\n.A*\nB.C\n\nC:E\nA:N.S\n'
multi('example-3',[(['7'],R3,'.A.\n..*\nB.C\nA 1 0 moves=5 bumps=0 coins=1\nB 0 2 moves=0 bumps=0 coins=0\nC 2 2 moves=0 bumps=7 coins=0\n',0),(['0'],R3,'.*.\n.A*\nB.C\nA 1 1 moves=0 bumps=0 coins=0\nB 0 2 moves=0 bumps=0 coins=0\nC 2 2 moves=0 bumps=0 coins=0\n',0)])
multi('example-4',[(['1'],s,'',1) for s in ['..\n.\n','..BA.\n.AB..\n\nA:E\n','A.\n\nB:E\n','A.\n\nA:X\n','A?\n']]+[(a,'','',2) for a in [[],['x'],['1','2']]])
case('no-robots',['99999'],'.#*\n*..\n','.#*\n*..\n')
multi('no-program-section',[(['9'],text,'B.A\nA 2 0 moves=0 bumps=0 coins=0\nB 0 0 moves=0 bumps=0 coins=0\n',0) for text in ['B.A\n','B.A\n\n','B.A']])
case('empty-program-and-missing-program',['8'],'AB\n\nA:\n','AB\nA 0 0 moves=0 bumps=0 coins=0\nB 1 0 moves=0 bumps=0 coins=0\n')
case('wait-does-not-count',['123'],'A*\n\nA:.\n','A*\nA 0 0 moves=0 bumps=0 coins=0\n')
case('all-directions-cycle',['5'],'...\n.A.\n...\n\nA:NESW.\n','...\n.A.\n...\nA 1 1 moves=4 bumps=0 coins=0\n')
case('all-grid-edges',['4'],'A\n\nA:NESW\n','A\nA 0 0 moves=0 bumps=4 coins=0\n')
case('walls-block-all-directions',['4'],'###\n#A#\n###\n\nA:NESW\n','###\n#A#\n###\nA 1 1 moves=0 bumps=4 coins=0\n')
case('head-on-blocked',['1'],'AB\n\nA:E\nB:W\n','AB\nA 0 0 moves=0 bumps=1 coins=0\nB 1 0 moves=0 bumps=1 coins=0\n')
case('follow-freed-cell',['1'],'BA.\n\nB:E\nA:E\n','.BA\nA 2 0 moves=1 bumps=0 coins=0\nB 1 0 moves=1 bumps=0 coins=0\n')
case('later-vacates-too-late',['2'],'AB..\n\nA:E\nB:E\n','.A.B\nA 1 0 moves=1 bumps=1 coins=0\nB 3 0 moves=2 bumps=0 coins=0\n')
case('one-coin-collected-once',['4'],'A*\n\nA:EW\n','A.\nA 0 0 moves=4 bumps=0 coins=1\n')
case('coin-contention-alphabetical',['1'],'A*B\n\nB:W\nA:E\n','.AB\nA 1 0 moves=1 bumps=0 coins=1\nB 2 0 moves=0 bumps=1 coins=0\n')
case('failed-move-still-advances-program',['4'],'A*.\n\nA:WEE.\n','..A\nA 2 0 moves=2 bumps=1 coins=1\n')
case('different-program-periods',['6'],'A...\nB...\n\nA:EW\nB:E.W\n','A...\nB...\nA 0 0 moves=6 bumps=0 coins=0\nB 0 1 moves=4 bumps=0 coins=0\n')
case('crlf-final-line',['00001'],b'A*\r\n\r\nA:E',out='.A\nA 1 0 moves=1 bumps=0 coins=1\n')
bad_inputs('missing-grid-and-program-lines',['','\n','A.\n\n\n','A.\n\nA:E\n\n','A.\n\nA:E\nA:W\n','A.\n\nA :E\n','A.\n\nA:E \n','A.\n\na:E\n'],['1'])
bad_inputs('invalid-grid-atomic',[' A\n','AA\n','.\n..\n','A\r\r\n','A.\n\nB:\n','A.\n\nA:E\ninvalid\n'],['0'])
errors('usage-tick-grammar',[[v] for v in ['','-1','+1','1.0',' 1','1 ','100000','000000']]+[['1','2','3']])
case('max-program-length',['100'],'A*\n\nA:'+'EW'*50+'\n','A.\nA 0 0 moves=100 bumps=0 coins=1\n')
case('max-grid-and-ticks',['99999'],stdin='A'+'.'*49+'\n'+('.'*50+'\n')*49+'\nA:W\n',out='A'+'.'*49+'\n'+('.'*50+'\n')*49+'A 0 0 moves=0 bumps=99999 coins=0\n')
case('all-26-robots',['99999'],stdin='ZYXWVUTSRQPONMLKJIHGFEDCBA\n',out='ZYXWVUTSRQPONMLKJIHGFEDCBA\n'+lines(f'{chr(65+i)} {25-i} 0 moves=0 bumps=0 coins=0' for i in range(26)))

if __name__ == '__main__':
    total = 0
    for task in sorted(ROOT.glob('[0-9][0-9]-*')):
        count = len(list((task/'cases').iterdir()))
        assert 15 <= count <= 25, (task.name,count)
        total += count
        print(f'{task.name}: {count} cases')
    print(f'{total} cases built')
