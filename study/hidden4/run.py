#!/usr/bin/env python3
"""Run the unchanged study harness with hidden4 as its in-memory root."""
import importlib.util
from pathlib import Path
import sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('study_harness', Path(__file__).resolve().parents[1] / 'harness.py')
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
harness.ROOT = Path(__file__).resolve().parent
if __name__ == '__main__':
    try:
        sys.exit(harness.main())
    except (ValueError, IndexError) as exc:
        print('harness: %s' % exc, file=sys.stderr)
        sys.exit(2)
