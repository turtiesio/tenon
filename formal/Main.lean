/-
`lake exe tenon-core run PRELUDE.ast... -- PROGRAM.ast [ARG...]`: run a
program, translated from `tenon ast` dumps, on the core's evaluator
(TenonCore/Eval.lean, the function the theorems are about). It prints the
program's standard output and error and exits with its status, as
`tenon run` would. A run the core cannot complete (a construct outside the
core, a stuck state, no fuel left) prints one line `tenon-core: ...` on
standard error and exits with 3 (ops/gates/formal_diff.py counts it as outside
the subset).
-/
import Front

open Tenon Front

def fuel : Nat := 100000000

def outside (msg : String) : IO UInt32 := do
  IO.eprintln s!"tenon-core: {msg}"
  return 3

def emit (evs : List Event) : IO Unit := do
  let out ← IO.getStdout
  let err ← IO.getStderr
  for ev in evs.reverse do
    if ev.op == "eprintln" then
      out.flush
      err.putStr ev.arg
    else out.putStr ev.arg
  out.flush

def run (preludes : List String) (progFile : String) (args : List String) : IO UInt32 := do
  let mut pitems := []
  for p in preludes do
    pitems := pitems ++ parseDump (← IO.FS.readFile p)
  let items := parseDump (← IO.FS.readFile progFile)
  let input ← (do
    let stdin ← IO.getStdin
    let mut acc : ByteArray := .empty
    repeat
      let chunk ← stdin.read 65536
      if chunk.isEmpty then break
      acc := acc ++ chunk
    pure acc.toList)
  let tp := translate pitems items input
  unless tp.unsupported.isEmpty do
    return ← outside s!"unsupported: {tp.unsupported.head!}"
  let some m := tp.main | outside "unsupported: no main"
  let call : Expr := .call (.fnref m) (if tp.mainArity == 0 then [] else [.place "%sys" []])
  let ρ : Env := [("%sys", some (Tenon.Check.sysVal args))]
  let showTop := Prims.showV tp.prog.adts true
  match eval tp.prog fuel ρ {} call with
  | .ok v _ st =>
    emit st.out
    match v with
    | .unit => return 0
    | .int n =>
      if 0 ≤ n ∧ n ≤ 255 ∧ n ≠ 70 ∧ n ≠ 71 ∧ n ≠ 72 ∧ n ≠ 74 then return n.toNat.toUInt32
      IO.eprintln s!"trap: exit status {n} is out of range or reserved"
      return 70
    | .adt "Result" 0 _ _ => return 0
    | .adt "Result" 1 _ [e] =>
      -- with Show impls, the error is formatted by the core's `%show`
      let text := if !tp.shows then showTop e else
        match eval tp.prog fuel [("%e", some e)] st (.call (.fnref "%show") [.place "%e" [], .lit (.bool true)]) with
        | .ok (.str s) _ _ => s
        | _ => showTop e
      IO.eprintln s!"error: {text}"
      return 1
    | _ => outside "main returned an unexpected value"
  | .ctl _ _ _ => outside "stuck: main ended with a break or continue"
  | .err (.trap msg st) =>
    emit st.out
    IO.eprintln s!"trap: {msg}"
    return 70
  | .err (.stuck k why) => outside s!"stuck ({if k == .type then "type" else "linear"}): {why}"
  | .err .timeout => outside "out of fuel"
  | .err (.unsup why) => outside s!"unsupported: {why}"

/-- `tenon-core check PRELUDE.ast... -- PROGRAM.ast`: the Lean checker's verdict
(TenonCore/Check.lean, proved sound in CheckSound.lean). Prints `accepted: N
instances` (exit 0), `rejected: WHY` (exit 1) or `unsupported: WHY` (exit 3). -/
def check (preludes : List String) (progFile : String) : IO UInt32 := do
  let mut pitems := []
  for p in preludes do
    pitems := pitems ++ parseDump (← IO.FS.readFile p)
  let items := parseDump (← IO.FS.readFile progFile)
  let tp := translate pitems items []
  unless tp.unsupported.isEmpty do
    IO.println s!"unsupported: {tp.unsupported.head!}"
    return 3
  match checkProgram tp with
  | .ok L => IO.println s!"accepted: {L.length} instances"; return 0
  | .error m =>
    if (m.splitOn "unsupported:").length > 1 then IO.println s!"unsupported: {m}"; return 3
    IO.println s!"rejected: {m}"; return 1

def main (argv : List String) : IO UInt32 := do
  match argv with
  | "check" :: rest =>
    let (pre, post) := rest.span (· != "--")
    match post with
    | ["--", prog] => check pre prog
    | _ => IO.eprintln "usage: tenon-core check PRELUDE.ast... -- PROGRAM.ast"; return 2
  | "run" :: rest =>
    let (pre, post) := rest.span (· != "--")
    match post with
    | "--" :: prog :: args => run pre prog args
    | _ => IO.eprintln "usage: tenon-core run PRELUDE.ast... -- PROGRAM.ast [ARG...]"; return 2
  | _ => IO.eprintln "usage: tenon-core run PRELUDE.ast... -- PROGRAM.ast [ARG...]"; return 2
