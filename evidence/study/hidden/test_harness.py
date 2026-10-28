"""Focused runner contract checks; run with python3 study/hidden/test_harness.py."""
import base64
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import unittest

HIDDEN=Path(__file__).resolve().parent
SCOPE={'__name__':'study_harness_test_module','__file__':str(HIDDEN.parent/'harness.py')}
exec(compile((HIDDEN.parent/'harness.py').read_text(),str(HIDDEN.parent/'harness.py'),'exec'),SCOPE)

class HarnessChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='runner-check-',dir=HIDDEN)
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.work=self.root/'work'; self.work.mkdir()

    def fixture(self,name='case',args=(),data=b'',out=b'',code=0):
        p=self.root/name; p.mkdir(parents=True)
        (p/'cmd').write_text(''.join(a+'\n' for a in args))
        (p/'stdin').write_bytes(data)
        (p/'expected_stdout').write_bytes(out)
        if code is not None: (p/'expected_exit').write_text(str(code)+'\n')
        return p

    def execute(self,p,source,kill=None):
        return SCOPE['execute'](p,self.work,[sys.executable,'-c',source],kill)

    def test_arguments_bytes_stderr_and_eof(self):
        p=self.fixture(args=['',' a b ','é','x\r'],data=b'input\x00',out=b'\x00\xff\n',code=7)
        source="import sys; assert sys.argv[1:]==['',' a b ','é','x\\r']; assert sys.stdin.buffer.read()==b'input\\x00'; sys.stderr.buffer.write(b'ignored\\xff'); sys.stdout.buffer.write(b'\\x00\\xff\\n'); sys.exit(7)"
        r=self.execute(p,source)
        self.assertTrue(r['passed'],r)
        self.assertEqual(base64.b64decode(r['stderr_b64']),b'ignored\xff')

    def test_no_stdin_file_is_immediate_eof(self):
        p=self.fixture(); (p/'stdin').unlink()
        self.assertTrue(self.execute(p,"import sys; assert sys.stdin.buffer.read()==b''")['passed'])

    def test_exact_stdout_and_exit_both_required(self):
        p=self.fixture(out=b'yes\n',code=2)
        r=self.execute(p,"print('yes ',end=''); raise SystemExit(0)")
        self.assertFalse(r['passed']); self.assertIn('stdout byte',r['detail']); self.assertIn('exit expected',r['detail'])

    def test_setup_shared_steps_and_continue_after_failure(self):
        case=self.root/'multi'; case.mkdir()
        (case/'steps').write_text('\none\n\ntwo\n')
        p=case/'setup'/'nested'; p.mkdir(parents=True); (p/'input').write_bytes(b'x')
        for name,mode,out in [('one','write',b'intentionally wrong\n'),('two','read',b'x\n')]:
            self.fixture('multi/'+name,args=[mode],out=out)
        source="from pathlib import Path; import sys; p=Path('nested/input'); assert p.read_bytes()==b'x'; m=Path('state'); m.write_bytes(b'x') if sys.argv[1]=='write' else print(m.read_text())"
        results=SCOPE['run_case'](case,[sys.executable,'-c',source])
        self.assertFalse(results[0]['passed']); self.assertTrue(results[1]['passed'],results)
        self.assertFalse((case/'setup'/'state').exists())

    def test_cases_are_fresh(self):
        case=self.fixture()
        source="from pathlib import Path; p=Path('marker'); assert not p.exists(); p.write_text('x')"
        for _ in range(2): self.assertTrue(SCOPE['run_case'](case,[sys.executable,'-c',source])[0]['passed'])

    def test_kill_lockstep_stderr_and_process_group(self):
        marker=self.root/'survived'
        child="import time; from pathlib import Path; time.sleep(.6); Path(%r).write_text('bad')"%str(marker)
        source="import sys, subprocess; subprocess.Popen([sys.executable,'-c',%r]); a=sys.stdin.buffer.readline(); assert a==b'one\\n'; sys.stderr.buffer.write(b'e'*300000); sys.stderr.flush(); print('ok',flush=True); b=sys.stdin.buffer.readline(); print('EXTRA INPUT',flush=True)"%child
        p=self.fixture(data=b'one\nnever sent\n',out=b'ok\n',code=None)
        r=self.execute(p,source,1)
        self.assertTrue(r['passed'],r)
        self.assertEqual(r['exit'],-signal.SIGKILL)
        self.assertEqual(len(base64.b64decode(r['stderr_b64'])),300000)
        time.sleep(.8)
        self.assertFalse(marker.exists(),'descendant survived SIGKILL')

    def test_timeout_kills_process_group(self):
        marker=self.root/'timeout-survived'
        child="import time; from pathlib import Path; time.sleep(.7); Path(%r).write_text('bad')"%str(marker)
        source="import sys,subprocess,time; subprocess.Popen([sys.executable,'-c',%r]); time.sleep(5)"%child
        p=self.fixture()
        old=SCOPE['TIMEOUT']; SCOPE['TIMEOUT']=.2
        try: r=self.execute(p,source)
        finally: SCOPE['TIMEOUT']=old
        self.assertFalse(r['passed']); self.assertIn('timeout',r['detail'])
        time.sleep(.9)
        self.assertFalse(marker.exists(),'descendant survived timeout')

    def test_kill_requires_newline_and_flush(self):
        p=self.fixture(data=b'one\n',out=b'ok\n',code=None)
        old=SCOPE['TIMEOUT']; SCOPE['TIMEOUT']=.2
        try: r=self.execute(p,"import sys,time; sys.stdin.readline(); sys.stdout.write('ok'); sys.stdout.flush(); time.sleep(5)",1)
        finally: SCOPE['TIMEOUT']=old
        self.assertFalse(r['passed']); self.assertIn('timeout',r['detail'])

    def test_early_exit_fails_kill(self):
        p=self.fixture(data=b'one\ntwo\n',out=b'ok\nok\n',code=None)
        r=self.execute(p,"import sys; sys.stdin.readline(); print('ok',flush=True)",2)
        self.assertFalse(r['passed'])

    def test_flat_and_cases_layouts(self):
        self.fixture('flat/example')
        self.fixture('nested/cases/example')
        self.assertEqual([p.name for p in SCOPE['cases_in'](self.root/'flat')],['example'])
        self.assertEqual([p.name for p in SCOPE['cases_in'](self.root/'nested')],['example'])

    def test_cmd_keeps_empty_argument_and_requires_final_newline(self):
        p=self.fixture(args=['',' spaced '])
        self.assertEqual(SCOPE['arguments'](p/'cmd'),['',' spaced '])
        (p/'cmd').write_bytes(b'invalid')
        with self.assertRaises(ValueError): SCOPE['arguments'](p/'cmd')

if __name__=='__main__': unittest.main(verbosity=2)
