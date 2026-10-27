#!/usr/bin/env python3
"""Black-box study runner (Python 3, stdlib only).

python3 study/harness.py TASK_DIR_OR_ALL [--json FILE] -- CMD...

A task id is also accepted. 'all' visits hidden/NN-*/cases/ (or the README's
flat hidden/NN-*/ layout). {task} in CMD expands to the current task id.
Existing relative CMD paths are made absolute before entering the temporary
working directory; case arguments are preserved byte-for-byte as UTF-8 text.
JSON includes base64 stdout/stderr for lossless diagnostic logs.
"""
import base64
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time

TIMEOUT = 10
NAME = re.compile(r'[a-z0-9][a-z0-9_-]*\Z')
ROOT = Path(__file__).resolve().parent / 'hidden'


def arguments(path):
    raw = path.read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('%s: cmd must end in newline' % path)
    return raw.decode('utf-8').split('\n')[:-1] if raw else []


def terminate(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        # macOS may report EPERM for a group containing only an exited,
        # unreaped child. Still attempt group cleanup even if the parent has
        # exited, because its descendants may retain the pipes.
        if proc.poll() is None:
            raise


def short_diff(want, got):
    if want == got:
        return ''
    pos = next((i for i, (a, b) in enumerate(zip(want, got)) if a != b), min(len(want), len(got)))
    return 'stdout byte %d: expected %r, got %r (length %d/%d)' % (
        pos, want[pos:pos+55], got[pos:pos+55], len(want), len(got))


def execute(directory, cwd, command, kill_after=None):
    expected = (directory / 'expected_stdout').read_bytes()
    argv = command + arguments(directory / 'cmd')
    data = (directory / 'stdin').read_bytes() if (directory / 'stdin').exists() else b''
    expected_exit = None if kill_after else int((directory / 'expected_exit').read_text())
    proc = None
    out, err = b'', b''
    failure = ''
    code = None
    started = time.monotonic()
    try:
        proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, start_new_session=True)
        if kill_after is None:
            try:
                out, err = proc.communicate(data, timeout=TIMEOUT)
            except subprocess.TimeoutExpired:
                failure = 'timeout after 10 s'
                terminate(proc)
                out, err = proc.communicate()
        else:
            # Only LF delimits the protocol; splitlines also recognizes CR.
            lines = data.split(b'\n')
            lines = [line + b'\n' for line in lines[:-1]] + ([lines[-1]] if lines[-1] else [])
            if len(lines) < kill_after or any(not x.endswith(b'\n') for x in lines[:kill_after]):
                raise ValueError('kill step needs N complete stdin lines')
            if expected.count(b'\n') != kill_after or not expected.endswith(b'\n'):
                raise ValueError('kill expected_stdout needs exactly N complete lines')
            pending = b''
            stderr_chunks = []
            selector = selectors.DefaultSelector()
            selector.register(proc.stdout, selectors.EVENT_READ, 'stdout')
            selector.register(proc.stderr, selectors.EVENT_READ, 'stderr')
            try:
                for line in lines[:kill_after]:
                    try:
                        proc.stdin.write(line)
                        proc.stdin.flush()
                    except BrokenPipeError:
                        failure = 'process exited before N responses'
                        break
                    deadline = time.monotonic() + TIMEOUT
                    while b'\n' not in pending and not failure:
                        left = deadline - time.monotonic()
                        if left <= 0:
                            failure = 'timeout waiting for response line (10 s)'
                            break
                        events = selector.select(left)
                        if not events:
                            failure = 'timeout waiting for response line (10 s)'
                            break
                        for key, _ in events:
                            chunk = os.read(key.fileobj.fileno(), 65536)
                            if not chunk:
                                selector.unregister(key.fileobj)
                                if key.data == 'stdout':
                                    failure = 'stdout closed before N responses'
                            elif key.data == 'stdout':
                                pending += chunk
                            else:
                                stderr_chunks.append(chunk)
                    if failure:
                        break
                    response, pending = pending.split(b'\n', 1)
                    out += response + b'\n'
                # Never send the remaining input or close stdin before SIGKILL.
                terminate(proc)
                _, tailerr = proc.communicate(timeout=TIMEOUT)
                err = b''.join(stderr_chunks) + tailerr
            finally:
                selector.close()
        code = proc.returncode
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        failure = '%s: %s' % (type(exc).__name__, exc)
    finally:
        if proc is not None:
            terminate(proc)
            if proc.poll() is None:
                proc.wait()
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream and not stream.closed:
                    try:
                        stream.close()
                    except BrokenPipeError:
                        pass
    reasons = [failure] if failure else []
    if expected != out:
        reasons.append(short_diff(expected, out))
    if kill_after is None and code != expected_exit:
        reasons.append('exit expected %s, got %s' % (expected_exit, code))
    return dict(step=directory.name, passed=not reasons, detail='; '.join(reasons),
                exit=code, expected_exit=expected_exit, kill_after=kill_after,
                stdout_b64=base64.b64encode(out).decode(), stderr_b64=base64.b64encode(err).decode(),
                seconds=round(time.monotonic()-started, 4))


def cases_in(task):
    parent = task / 'cases' if (task / 'cases').is_dir() else task
    return sorted(p for p in parent.iterdir() if p.is_dir() and NAME.fullmatch(p.name)
                  and ((p / 'cmd').exists() or (p / 'steps').exists()))


def run_case(case, command):
    with tempfile.TemporaryDirectory(prefix='study-') as cwd:
        if (case / 'setup').is_dir():
            shutil.copytree(case / 'setup', cwd, dirs_exist_ok=True)
        if (case / 'steps').exists():
            steps = []
            for line in (case / 'steps').read_text().split('\n'):
                if not line.strip():
                    continue
                m = re.fullmatch(r'([a-z0-9][a-z0-9_-]*)(?: kill-after=([1-9][0-9]*))?', line)
                if not m:
                    raise ValueError('invalid steps line: %r' % line)
                steps.append((case / m[1], int(m[2]) if m[2] else None))
            if not steps:
                raise ValueError('empty steps file')
        else:
            steps = [(case, None)]
        return [execute(step, cwd, command, kill) for step, kill in steps]


def main():
    args = sys.argv[1:]
    if '--' not in args:
        raise ValueError('usage: harness.py TASK_DIR_OR_ALL [--json FILE] -- CMD...')
    split = args.index('--')
    opts, command = args[:split], args[split+1:]
    result_file = None
    if '--json' in opts:
        i = opts.index('--json')
        result_file = Path(opts[i+1]).resolve()
        del opts[i:i+2]
    if len(opts) != 1 or not command:
        raise ValueError('one task directory or all, and a solution command, are required')
    if opts[0] == 'all':
        tasks = sorted(p for p in ROOT.glob('[0-9][0-9]-*') if p.is_dir())
    else:
        path = Path(opts[0])
        if not path.is_dir():
            path = ROOT / opts[0]
        if not path.is_dir():
            raise ValueError('task directory does not exist: %s' % opts[0])
        tasks = [path.resolve()]
    results = []
    for task in tasks:
        task_id = task.parent.name if task.name == 'cases' else task.name
        cmd = [arg.replace('{task}', task_id) for arg in command]
        cmd = [str(Path(arg).resolve()) if arg and Path(arg).exists() else arg for arg in cmd]
        for case in cases_in(task):
            try:
                steps = run_case(case, cmd)
                passed = all(step['passed'] for step in steps)
                detail = '; '.join(step['step'] + ': ' + step['detail'] for step in steps if not step['passed'])
            except (OSError, ValueError) as exc:
                steps, passed, detail = [], False, 'invalid case: %s' % exc
            result = dict(task=task_id, case=case.name, passed=passed, detail=detail, steps=steps)
            results.append(result)
            print('%s %s/%s%s' % ('PASS' if passed else 'FAIL', task_id, case.name,
                                 ': ' + detail if detail else ''), flush=True)
    passed = sum(r['passed'] for r in results)
    print('%d/%d passed; %d failed' % (passed, len(results), len(results)-passed))
    if result_file:
        result_file.write_text(json.dumps(dict(passed=passed, total=len(results), results=results), indent=2)+'\n')
    return 0 if results and passed == len(results) else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, IndexError) as exc:
        print('harness: %s' % exc, file=sys.stderr)
        sys.exit(2)
