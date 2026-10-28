#!/usr/bin/env python3
"""Use the unmodified study harness with hidden2 as its root."""
import importlib.util
from pathlib import Path
import sys
sys.dont_write_bytecode = True
path = Path(__file__).resolve().parents[1] / 'harness.py'
spec = importlib.util.spec_from_file_location('study_harness', path)
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
harness.ROOT = Path(__file__).resolve().parent
if __name__ == '__main__':
    try:
        sys.exit(harness.main())
    except (ValueError, IndexError) as exc:
        print('harness: %s' % exc, file=sys.stderr)
        sys.exit(2)
