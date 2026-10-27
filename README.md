# Tenon

A small, fast, capability-safe language whose programs compose only when their
contracts fit. See [`tenon.md`](tenon.md) for the goals, [`docs/reference.md`](docs/reference.md)
for the language, [`STATUS.md`](STATUS.md) for measured results, and
[`docs/log.md`](docs/log.md) for decisions.

```sh
./check --fast                 # build + full differential test corpus (budget: 60 s)
target/release/tenon run  prog.tn [args]    # reference interpreter
target/release/tenon build prog.tn -o prog  # native executable via C
```
