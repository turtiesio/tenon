#!/usr/bin/env python3
"""Use the original harness with hidden7 fixtures and local temporary runs."""
import importlib.util
from pathlib import Path
import sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('study_harness',Path(__file__).resolve().parents[1]/'harness.py')
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
harness.ROOT=Path(__file__).resolve().parent
# Keep harness-created working directories inside the authorized tree too.
harness.tempfile.tempdir=str(harness.ROOT)
if __name__=='__main__':
    try: sys.exit(harness.main())
    except (ValueError,IndexError) as exc:
        print('harness: %s'%exc,file=sys.stderr)
        sys.exit(2)
