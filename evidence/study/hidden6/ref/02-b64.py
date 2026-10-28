import base64
import binascii
import sys
from common import match, fail
args = sys.argv[1:]
decode, width, i = False, 76, 0
while i < len(args):
    a = args[i]
    if a == '-d': decode = True
    elif a == '-w':
        i += 1
        if i == len(args) or not match(r'[0-9]{1,4}',args[i]): fail(2)
        width = int(args[i])
    else: fail(2)
    i += 1
data = sys.stdin.buffer.read()
if decode:
    data = data.replace(b'\r',b'').replace(b'\n',b'')
    try:
        result = base64.b64decode(data, validate=True)
        if base64.b64encode(result) != data: fail()
    except (ValueError,binascii.Error): fail()
else:
    text = base64.b64encode(data)
    n = width or len(text) or 1
    result = b''.join(text[i:i+n]+b'\n' for i in range(0,len(text),n))
sys.stdout.buffer.write(result)
