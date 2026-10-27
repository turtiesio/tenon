- **Usability study**: wave 1 (1 author per language) passed 100% of hidden
  tests in all three languages, but Tenon needed ~1.7x Python's tokens and its
  task-time measurement was invalid (clocks started late; fixed: specifications
  are now revealed only by `try.sh --start`). The full study (3 authors per
  language, two model families, a new task set) has not run yet. Goal not met.
- **Performance**: wordfreq at ~1.7x C (insertion-ordered two-level map plus two
  lookups per update); fib and trees within 1.5x. Rust/TypeScript baselines missing.
- **Self-hosted checker**: in progress (lexer and parser agree on the full corpus).
- **Loop-time history**: less than a week of measurements exists.
- Not implemented: concurrency (servers handle one connection at a time).
