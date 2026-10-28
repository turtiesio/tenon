/-
The guarantees, as theorem statements (formal/README.md, "Theorems").

This file is guarded (ops/governance/guarded.txt, `theorems` rule): changing
or removing a statement below needs an owner approval line in
ops/governance/approvals.log, like weakening a guarded test
(ops/repo/approvals.py). Proofs may change freely; new theorems may be added.
Each statement is proved from the development in the other modules.
-/
import TenonCore.Capability
import TenonCore.LinearSafe
import TenonCore.Workers

namespace Tenon.Theorems
open Tenon

/-! ## Capabilities (reference §10) -/

/-- Attenuation only narrows: `Fs.within` and `Fs.read_only` give a capability below the one they start from. -/
theorem within_narrows (c : Cap) (segs : List String) : c.within segs ≤ c := Cap.within_le c segs

theorem readOnly_narrows (c : Cap) : c.readOnly ≤ c := Cap.readOnly_le c

/-- The attenuation order is transitive (so attenuating twice still narrows). -/
theorem attenuation_trans {a b c : Cap} (h1 : a ≤ b) (h2 : b ≤ c) : a ≤ c := Cap.le_trans h1 h2

/-- No forging: whatever an expression (of any program, typed or not) returns,
keeps in its environment, or uses for an effect, is an attenuation of a
capability it was given. -/
theorem capability_safety (P : Prog) (A : List Cap) (n : Nat) (ρ : Env) (st : St) (e : Expr)
    (hρ : ∀ c ∈ envCaps ρ, ∃ a ∈ A, c ≤ a) (hst : ∀ ev ∈ st.out, ∃ a ∈ A, ev.cap ≤ a) :
    match eval P n ρ st e with
    | .ok v ρ' st' =>
      (∀ c ∈ v.caps, ∃ a ∈ A, c ≤ a) ∧ (∀ c ∈ envCaps ρ', ∃ a ∈ A, c ≤ a) ∧
      (∀ ev ∈ st'.out, ∃ a ∈ A, ev.cap ≤ a)
    | .ctl _ ρ' st' => (∀ c ∈ envCaps ρ', ∃ a ∈ A, c ≤ a) ∧ (∀ ev ∈ st'.out, ∃ a ∈ A, ev.cap ≤ a)
    | .err (.trap _ st') => ∀ ev ∈ st'.out, ∃ a ∈ A, ev.cap ≤ a
    | .err _ => True :=
  Tenon.capability_safety P A n ρ st e hρ hst

/-- A program started with the capabilities `A` (its `Sys`) performs every
effect through an attenuation of one of them. -/
theorem no_authority_escalation (P : Prog) (A : List Cap) (n : Nat) (ρ : Env) (e : Expr)
    (hρ : envCaps ρ ⊆ A) :
    match eval P n ρ {} e with
    | .ok _ _ st' | .ctl _ _ st' | .err (.trap _ st') => ∀ ev ∈ st'.out, ∃ a ∈ A, ev.cap ≤ a
    | .err _ => True :=
  Tenon.no_authority_escalation P A n ρ e hρ

/-! ## Obligations (reference §12) -/

/-- Conservation: along any evaluation that ends with a value or an early exit,
every token is held, discharged or dropped exactly as often as it was held
before or minted; only unique tokens are dropped; minted tokens are distinct. -/
theorem obligations_conserved (P : Prog) (n : Nat) (ρ : Env) (st : St) (e : Expr) (hs : StOk st) :
    match eval P n ρ st e with
    | .ok v ρ' st' => Bal v.toks ρ' st' [] ρ st ∧ StOk st'
    | .ctl c ρ' st' => Bal (ctlToks c) ρ' st' [] ρ st ∧ StOk st'
    | .err _ => True :=
  Tenon.obligations_conserved P n ρ st e hs

/-- Exactly once: from a start holding no obligation, every token minted occurs
exactly once among the result, the final environment, the discharged and the
dropped ones; no other token occurs; a linear token is never dropped. -/
theorem obligations_exactly_once (P : Prog) (n : Nat) (ρ : Env) (e : Expr) (v : Val) (ρ' : Env) (st' : St)
    (hρ : envToks ρ = []) (h : eval P n ρ {} e = .ok v ρ' st') :
    (∀ t ∈ st'.minted, (v.toks ++ envToks ρ' ++ st'.burned ++ st'.dropped).count t = 1) ∧
    (∀ t, t ∉ st'.minted → (v.toks ++ envToks ρ' ++ st'.burned ++ st'.dropped).count t = 0) ∧
    (∀ t ∈ st'.minted, t.lin = true → st'.dropped.count t = 0 ∧
      st'.burned.count t + (v.toks ++ envToks ρ').count t = 1) :=
  Tenon.obligations_exactly_once P n ρ e v ρ' st' hρ h

/-- A complete program (result and final environment hold no obligation) has
discharged every linear value it created exactly once. -/
theorem linear_discharged_exactly_once (P : Prog) (n : Nat) (ρ : Env) (e : Expr) (v : Val) (ρ' : Env) (st' : St)
    (hρ : envToks ρ = []) (h : eval P n ρ {} e = .ok v ρ' st') (hv : v.toks = []) (hρ' : envToks ρ' = []) :
    ∀ t ∈ st'.minted, t.lin = true → st'.burned.count t = 1 ∧ st'.dropped.count t = 0 :=
  Tenon.linear_discharged_exactly_once P n ρ e v ρ' st' hρ h hv hρ'

/-! ## Workers (reference §18) -/

/-- Every step of the worker machine keeps every worker's reachable cells its own. -/
theorem step_isolated {cfg cfg' : Workers.Cfg} (hi : Workers.Isolated cfg) (hs : Workers.Step cfg cfg') :
    Workers.Isolated cfg' :=
  Workers.step_isolated hi hs

/-- Every configuration a program reaches from its start is isolated. -/
theorem run_isolated (rs : List Workers.HV) (hrs : ∀ v ∈ rs, v.locs = []) {cfg' : Workers.Cfg}
    (hs : Workers.Steps ⟨fun _ => none, 0, fun w => if w = 0 then some rs else none, fun _ => []⟩ cfg') :
    Workers.Isolated cfg' :=
  Workers.run_isolated rs hrs hs

/-- No data races: in an isolated configuration no cell is reachable from two workers. -/
theorem no_shared_cell {cfg : Workers.Cfg} (hi : Workers.Isolated cfg) {w1 w2 : Nat} {rs1 rs2 : List Workers.HV}
    {l : Nat} (h1 : cfg.workers w1 = some rs1) (h2 : cfg.workers w2 = some rs2)
    (r1 : Workers.Reach cfg.heap rs1 l) (r2 : Workers.Reach cfg.heap rs2 l) : w1 = w2 :=
  Workers.no_shared_cell hi h1 h2 r1 r2

/-- The `Send` rule matters: handing another worker a pointer instead of a copy breaks isolation. -/
theorem unchecked_sharing_breaks_isolation :
    ∃ cfg : Workers.Cfg, Workers.Isolated cfg ∧
      ¬ Workers.Isolated ⟨cfg.heap, cfg.next, Workers.upd cfg.workers 1 (some [.ptr 0]), cfg.chans⟩ :=
  Workers.unchecked_sharing_breaks_isolation

end Tenon.Theorems
