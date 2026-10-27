Reject tests for checker rules added from QA findings (redteam/FINDINGS.md) that
the self-hosted checker (selfhost/) does not implement yet. Each moves to
tests/reject/ once selfhost/ agrees on it; until then `tenon check` on each
file must already fail with the `// error:` text.
