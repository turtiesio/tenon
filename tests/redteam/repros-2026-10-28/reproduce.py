#!/usr/bin/env python3
"""Replay the report without modifying sources. Optional: --sanitize.

Run from any directory; TENON may select another compiler. These repros expose
bugs, so accepted builds and matching backends do not mean conformance passes.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TENON = os.environ.get("TENON", str(ROOT / "target/tenon"))
SOURCES = {
    "01": ["v2/01-specialized-show.tn"],
    "02": ["v2/02-show-impl-bound.tn"],
    "03": ["03a-div-euclid.tn", "03b-rem-euclid.tn"],
    "04": ["04-fmt-fixed-min.tn"],
    "05": ["v2/05-derived-show-bound.tn"],
    "06": ["06-lsp-field.tn"],
}


def run(args, **kwargs):
    return subprocess.run(args, cwd=ROOT, capture_output=True, timeout=30, **kwargs)


def display(label, result):
    print(f"  {label}: {json.dumps({'status': result.returncode, 'stdout': result.stdout.decode(errors='replace'), 'stderr': result.stderr.decode(errors='replace')}, ensure_ascii=False)}")


def frame(message):
    body = json.dumps(message).encode()
    return b"Content-Length: %d\r\n\r\n" % len(body) + body


def lsp(source):
    text = source.read_text()
    uri = source.as_uri()
    lines = text.splitlines()
    line = next(i for i, s in enumerate(lines) if "p.x" in s)
    character = lines[line].index("p.x") + 2
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"textDocument": {"uri": uri, "languageId": "tenon", "version": 1, "text": text}}},
        {"jsonrpc": "2.0", "id": 2, "method": "textDocument/definition", "params": {"textDocument": {"uri": uri}, "position": {"line": line, "character": character}}},
        {"jsonrpc": "2.0", "id": 3, "method": "shutdown", "params": {}},
        {"jsonrpc": "2.0", "method": "exit", "params": {}},
    ]
    result = run([TENON, "lsp"], input=b"".join(map(frame, messages)))
    responses = []
    remaining = result.stdout
    while remaining:
        header, remaining = remaining.split(b"\r\n\r\n", 1)
        length = int(header.split(b":", 1)[1])
        responses.append(json.loads(remaining[:length]))
        remaining = remaining[length:]
    print("  definition request:", json.dumps(messages[2]))
    print("  definition response:", json.dumps(next(m for m in responses if m.get("id") == 2)))
    print("  expected range: line 2, characters 4..5 (zero-based); server status:", result.returncode)
    if result.stderr:
        print("  server stderr:", result.stderr.decode(errors="replace"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("finding", nargs="?", choices=list(SOURCES))
    parser.add_argument("--sanitize", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="tenon-conformance-") as temp:
        for finding in [args.finding] if args.finding else SOURCES:
            for name in SOURCES[finding]:
                source = HERE / name
                exe = Path(temp) / source.stem
                print(name)
                display("check", run([TENON, "check", str(source)]))
                display("run", run([TENON, "run", str(source)]))
                build = run([TENON, "build", str(source), "-o", str(exe), "-O0"], env=dict(os.environ, TENON_KEEP_C="1"))
                display("build -O0", build)
                if build.returncode == 0:
                    display("native", run([str(exe)]))
                    if args.sanitize:
                        sanitized = str(exe) + ".asan"
                        cc = run(["cc", "-g", "-O0", "-DTN_POOL_MAX=0", "-fsanitize=address,undefined", "-fno-sanitize-recover=undefined", "-w", "-pthread", str(exe) + ".c", "-o", sanitized, "-lm"])
                        display("sanitizer build", cc)
                        if cc.returncode == 0:
                            display("ASan/UBSan", run([sanitized], env=dict(os.environ, ASAN_OPTIONS="detect_leaks=0")))
                if finding == "06":
                    lsp(source)


if __name__ == "__main__":
    main()
