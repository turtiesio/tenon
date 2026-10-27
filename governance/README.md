# Governance

Start minimal; grow only from incidents (tenon.md §2.5).

1. **The tests are the contract.** A landing passes `./check --fast`
   (`tools/land.sh`); main passes the evidence suite.
2. **Approvals log** (`governance/approvals.log`, append-only). A change that
   removes or weakens a guarantee-bearing test must add, in the same change,
   an approval line naming each such file:

       DATE | APPROVER | PATH | reason

   Guarantee-bearing tests are listed in `governance/guarded.txt` (globs).
   "Weakening" = deleting the file, changing its expected diagnostic
   (`// error:` line) or changing its golden output. `tools/approvals.py`
   checks this on every landing, and also refuses any edit to existing log
   lines (history is never rewritten). Its own test: `tools/approvals_test.sh`.
3. **Mutation testing** is evidence, not a gate (not running yet).

Mechanisms added from incidents:

- `tools/land.sh` (2026-10-28, red main from a landing path that ignored the
  check's exit status).
