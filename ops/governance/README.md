# Governance

Start minimal; grow only from incidents (tenon.md §2.5).

1. **The tests are the contract.** A landing passes `./check --fast`
   (`ops/repo/land.sh`); main passes the evidence suite.
2. **Approvals log** (`ops/governance/approvals.log`, append-only). A change that
   removes or weakens a guarantee-bearing test must add, in the same change,
   an approval line naming each such file:

       DATE | APPROVER | PATH | reason

   Guarantee-bearing tests are listed in `ops/governance/guarded.txt` (globs).
   "Weakening" = deleting the file, changing its expected diagnostic
   (`// error:` line) or changing its golden output. `ops/repo/approvals.py`
   checks this on every landing, and also refuses any edit to existing log
   lines (history is never rewritten). Its own test: `ops/gates/approvals_test.sh`.
3. **Frozen seed.** The Rust bootstrap (`seed/`, all of it) is the seed
   that builds the self-hosted compiler (tenon.md §5); the compiler is
   developed in Tenon (`compiler/`). `frozen GLOB` lines in
   `ops/governance/guarded.txt` (`frozen seed/*`) make `ops/repo/approvals.py`
   refuse any change under the glob (an added, changed or deleted file)
   unless the same change adds an approval line naming the file, or a glob
   covering it (`DATE | APPROVER | seed/* | reason`). Independently, the
   total line count of the frozen files may only shrink: growth is refused
   even with an approval (a needed fix pays for its lines elsewhere in the
   seed). The rules of the base and of the change apply together, so a
   rename (as `bootstrap/` to `seed/`, 2026-10-28) needs approval lines for
   the old and the new paths, and the line count is compared across it; a
   guarded test moved unchanged to a path that is still guarded is not a
   weakening. Its test: `ops/gates/approvals_test.sh`.
4. **Theorem statements.** `theorems GLOB` lines in
   `ops/governance/guarded.txt` (`theorems formal/TenonCore/Theorems.lean`,
   tenon.md §6) guard the statements of Lean theorems: a change that alters
   or removes a statement (the text from the theorem's name to its `:=`,
   comments and layout ignored) that no guarded file still states needs an
   approval line naming the file, as a weakened test does. Proofs may change
   and theorems may be added freely. Its test: `ops/gates/approvals_test.sh`.
5. **Mutation testing** is evidence, not a gate (`ops/evidence/mutate.py`; survivors
   go to .evidence/mutation.json as tasks).

Mechanisms added from incidents:

- `ops/repo/land.sh` (2026-10-28, red main from a landing path that ignored the
  check's exit status).
  Amended (2026-10-28): it commits tracked changes plus the new paths named
  on its command line, after it swept another agent's unfinished drafts
  (evidence/study/tasks3) into two unrelated commits.
- `ops/repo/approvals.py --pr` and the `owner GLOB` lines of
  `ops/governance/guarded.txt` (2026-10-28, user decision: unattended agents
  land only through pull requests that merge when CI passes). CI runs the
  base's checker on every pull request; it refuses any change to the
  approvals log (a pull request cannot approve itself), a removed rule, and
  any change under an `owner` path (the gate, this checker, CI). Its test:
  four scenarios of `ops/gates/approvals_test.sh`. docs/dev/automation.md.
