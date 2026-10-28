# Weekly hygiene review

The hygiene review of tenon.md §6 ("No staleness"). Read tenon.md (§2: KISS
and DRY, at most about 5 process mechanisms, files up to about 1000 lines,
functions up to about 80; §3; §5-6), README.md, docs/ and
docs/dev/cleanup_plan.md (do not redo finished items). The open issues
listed at the end of this brief are already recorded: do not record them
again (reuse an issue's key, the part of its title in brackets, to update it).

Audit what changed since the last review (`git log --since='8 days ago'`)
and the repository as a whole for drift:

- duplicated code (DRY); needless complexity or dead code (KISS); modules
  mixing responsibilities;
- docs that no longer match behaviour or name paths that do not exist;
  a stale STATUS.md or tools/unmet.md;
- scripts still using the frozen seed where the self-hosted compiler is
  meant;
- tools that could now be written in Tenon (dogfooding);
- files and functions over the size limits without a stated reason.

Fix what is small and safe directly, all in this run's one pull request
(`.agent/pr.md` lists each fix with its reason). Never edit `bootstrap/`
(frozen) or `study/` (published evidence). Record larger items in
`.agent/issues.json`, key `hygiene:<short-name>`, label `hygiene`, plus
`agent-ok` when the change is mechanical and has a clear acceptance test, or
`needs-owner` when it needs a product decision. Give each issue the files
involved, the goal, the acceptance test and what not to touch (tenon.md
§2.4), so a fixer can work from the issue alone.
