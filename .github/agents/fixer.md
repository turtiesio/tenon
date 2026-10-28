# Fixer

Fix the one issue given at the end of this brief (it has the label
`agent-ok`, so it was judged clear and mechanical), with the smallest
sufficient change, on main's rules (the common rules above).

1. Reproduce it first. If it no longer reproduces on this commit, say so in
   `.agent/blocked.md` with the command you ran and its output, and change
   nothing.
2. Fix it at its owner: the lowest boundary where the concern belongs
   (tenon.md §1.2, complexity localization), not by special-casing the
   symptom.
3. **A regression test, guarded.** A fix for an issue labeled `regression`
   or `redteam` adds a test that fails before the fix and passes after it
   (`tests/run/NAME.tn` with its `.out`, `tests/reject/NAME.tn`, or the `v2/`
   counterpart; docs/dev/testing.md, "Adding a test"), and adds the test's
   path(s) to `governance/guarded.txt`, so that weakening it later needs the
   owner's approval. Show both runs in `.agent/pr.md`: the test failing on
   the unfixed compiler and passing on the fixed one. For a surviving
   mutant (`mutation survived at FILE:LINE`) the test is one that fails with
   the mutant applied: apply it, show the failure, undo it. The workflow
   refuses a fix for such an issue that adds no line to
   `governance/guarded.txt`.
4. `./check` passes. Update the docs the fix makes stale.
5. Write `.agent/pr.md`: the title `Fix #N: <what>`, then what was wrong,
   the fix, the regression test by path (name it explicitly), and the
   before and after evidence.

If you cannot fix it, or the fix would weaken a guarantee (delete or relax
a guarded test, change a rule of the language) or needs a product decision,
undo your changes and write `.agent/blocked.md`: what you found, why it
needs the owner, and 2-4 options with a recommendation and what each costs.
The workflow then labels the issue `needs-owner` and posts your explanation.
