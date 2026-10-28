/-
TODO (formal/README.md, "What remains"): statements without proofs yet.
This module is not built by the gate (ops/gates/formal_check.sh builds the
default targets of lakefile.toml; `Todo` is not one of them), so its `sorry`
does not count as a proof. Build it alone with `lake build Todo`.
-/
import TenonCore.Typing

namespace Tenon.Todo
open Tenon

/-- **Type and obligation soundness** (definitional-interpreter style, with
fuel). A well-typed expression of a well-typed program, run in an environment
that matches its context, never gets stuck: neither a type error nor a broken
obligation rule (`Stuck.linear`: a copy, a drop or a use after a move), and it
never reaches a construct outside the core. A value it returns has its type
and the environment matches the context the judgement leaves; an early return
carries a value of the function's return type; `break`/`continue` happen only
inside a loop. Running out of fuel and traps are allowed.

Together with `Theorems.obligations_exactly_once` this gives the static
guarantee of reference §12 (every linear value consumed exactly once) for
every program the type system accepts. -/
theorem type_soundness (P : Prog) (prim : String → List Ty → Ty → Prop)
    (hP : ProgOk P prim) (hprim : PrimsOk P prim)
    (Δ : Sig) (hΔ : Δ.P = P ∧ Δ.prim = prim)
    (Γ Γ' : Ctx) (e : Expr) (t : Ty) (h : HasTy Δ Γ e t Γ')
    (ρ : Env) (hρ : EnvOk P ρ Γ) (n : Nat) (st : St) :
    match eval P n ρ st e with
    | .ok v ρ' _ => ValTy P v t ∧ EnvOk P ρ' Γ'
    | .ctl (.ret v) _ _ => ValTy P v Δ.ret
    | .ctl _ _ _ => Δ.loop.isSome
    | .err (.stuck _ _) => False
    | .err (.unsup _) => False
    | .err _ => True := by
  sorry

/-- Substitution in a context (the types of its entries). -/
def Ctx.subst (σ : List Ty) (Γ : Ctx) : Ctx := Γ.map fun e => { e with ty := e.ty.subst σ }

/-- **Parametricity of the checker** (the bridge from checking a generic
function once to `ProgOk`, which asks for every instance): typing is stable
under substituting the type parameters, provided the builtins' signatures are. -/
theorem typing_subst (Δ : Sig) (Γ Γ' : Ctx) (e : Expr) (t : Ty) (σ : List Ty)
    (hprim : ∀ p ts r, Δ.prim p ts r → Δ.prim p (substL σ ts) (r.subst σ))
    (hkind : ∀ t : Ty, (t.subst σ).kind Δ.P = t.kind Δ.P)
    (h : HasTy Δ Γ e t Γ') :
    HasTy { Δ with ret := Δ.ret.subst σ } (Ctx.subst σ Γ) e (t.subst σ) (Ctx.subst σ Γ') := by
  sorry

end Tenon.Todo
