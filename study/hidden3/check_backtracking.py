"""Check the exponential control against the unchanged harness timeout."""
from pathlib import Path
import json
import sys
from run import harness
ROOT=Path(__file__).resolve().parent
result=harness.run_case(ROOT/'03-globgrep/cases/pathological-backtracking',
                        [sys.executable,'-B',str(ROOT/'naive-glob.py')])
(ROOT/'backtracking-results.json').write_text(json.dumps(result,indent=2)+'\n')
for step in result:
    print(step['detail'])
    print('elapsed:',step['seconds'],'seconds')
assert len(result)==1 and not result[0]['passed'] and 'timeout after 10 s' in result[0]['detail']
print('EXPECTED TIMEOUT: exponential control rejected')
