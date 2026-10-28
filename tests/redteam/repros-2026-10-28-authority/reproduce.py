#!/usr/bin/env python3
"""Replay the authority findings: for every repro, `check`, `run` and a native `build` + run.

Usage: python3 reproduce.py [NN ...] [--sanitize]   (NN = finding number, e.g. 01 05)
TENON selects another compiler. These programs expose bugs, so "accepted" and "backends
agree" do not mean the property holds; compare with FINDINGS-2026-10-28-authority.md.
Programs that may hang (07c) run under a timeout. --sanitize also builds the generated C
with the flags of tools/asan.sh.
"""
import os, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TENON = os.environ.get("TENON", str(ROOT / "target/tenon"))
FILES = {
    "01": ["01a-linear-lost-method-arg.tn", "01b-linear-lost-call-return-break.tn", "01c-linear-lost-tuple-match-interp.tn", "01d-linear-lost-continue-struct-literal.tn"],
    "02": ["02-ref-param-erased-by-fn-value.tn"],
    "03": ["03a-const-linear-copied.tn", "03b-const-unique-copied.tn"],
    "04": ["04-private-enum-forged.tn"],
    "05": ["05a-unique-moved-listener-stays-open.tn", "v2/05b-unique-moved-to-worker-still-readable.tn"],
    "06": ["06-run-with-timeout-leaves-descendants.tn"],
    "07": ["07a-run-keeps-dropped-listener-open.tn", "07c-run-conn-drop-never-signals-peer.tn"],
}


def sh(args, timeout=20, **kw):
    try:
        r = subprocess.run(args, cwd=HERE, capture_output=True, timeout=timeout, **kw)
        return r.returncode, r.stdout.decode(errors="replace"), r.stderr.decode(errors="replace")
    except subprocess.TimeoutExpired:
        return 124, "", "(timeout)"


def show(label, res):
    code, out, err = res
    print(f"  {label}: exit {code}")
    for line in (out + err).rstrip().splitlines()[:12]:
        print(f"    {line}")


def main():
    sanitize = "--sanitize" in sys.argv
    want = [a for a in sys.argv[1:] if not a.startswith("--")] or sorted(FILES)
    tmp = tempfile.mkdtemp(prefix="tenon-authority-")
    env = dict(os.environ, TENON_ROOT=str(ROOT))
    for key in want:
        for f in FILES[key]:
            print(f"== {f}")
            show("check", sh([TENON, "check", f]))
            show("run", sh([TENON, "run", f], timeout=10))
            exe = os.path.join(tmp, Path(f).stem)
            b = sh([TENON, "build", f, "-o", exe], timeout=120)
            if b[0] != 0:
                show("build", b)
                continue
            show("native", sh([exe], timeout=10))
            if sanitize:
                sh([TENON, "build", f, "-o", exe + ".o0", "-O0"], timeout=120, env=dict(env, TENON_KEEP_C="1"))
                cc = sh(["cc", "-g", "-O0", "-DTN_POOL_MAX=0", "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined",
                         "-w", "-pthread", exe + ".o0.c", "-o", exe + ".asan", "-lm"], timeout=120)
                if cc[0] == 0:
                    show("asan", sh([exe + ".asan"], timeout=10, env=dict(os.environ, ASAN_OPTIONS="detect_leaks=0")))
                else:
                    show("asan build", cc)


if __name__ == "__main__":
    main()
