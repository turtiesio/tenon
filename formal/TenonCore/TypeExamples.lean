/-
The hypotheses of `Theorems.type_soundness` are satisfiable: a concrete
program (the prelude's `Option` and `Result`, a linear enum `Tok`) is well
formed (`ProgOk`, `PrimsOk`), and an expression that creates a linear value
and consumes it with `match` is well typed. Its run is therefore never stuck
(`ex_never_stuck`), and the evaluator indeed completes it (`ex_runs`).
-/
import TenonCore.Theorems

namespace Tenon.Examples
open Tenon

def optD : AdtDecl where
  name := "Option"
  isStruct := false
  kind := .copy
  tparams := 1
  variants := [("Some", [.var 0]), ("None", [])]
def resD : AdtDecl where
  name := "Result"
  isStruct := false
  kind := .copy
  tparams := 2
  variants := [("Ok", [.var 0]), ("Err", [.var 1])]
def tokD : AdtDecl := { name := "Tok", isStruct := false, kind := .linear, variants := [("T", [])] }

def exP : Prog where
  fns := fun _ => none
  adts := fun s => if s = "Option" then some optD else if s = "Result" then some resD
    else if s = "Tok" then some tokD else none
  prim := fun _ => none

def exPrim : PrimSig := fun _ _ _ => False

/-- `let c = Tok.T; match c { T => () }`: a linear value, created and consumed. -/
def exE : Expr :=
  .letE "c" false (.con "Tok" 0 []) (.mtch (.place "c" []) [(.con "T" [], none, .lit .unit)])

def topSig : Sig := ⟨.unit, false, none, 0, fun _ => True⟩

theorem kind_le_join_arg (P : Prog) (k : Kind) (args : List Ty) (i : Nat) (h : i < args.length) :
    Kind.le (((Ty.var i).subst args).kind P) (Kind.join k (kindL P args)) := by
  simp only [Ty.subst, List.getElem?_eq_getElem h, Option.getD_some]
  exact Kind.le_trans (kindL_le P (List.getElem_mem h)) (Kind.le_join_right _ _)

theorem ex_adts : AdtsOk exP := by
  intro s d hd
  simp only [exP] at hd
  split at hd
  · cases hd
    refine ⟨by simp [optD], fun _ => by simp [optD, resD, tokD], fun args ha v hv ft hft => ?_⟩
    simp [optD] at hv; rcases hv with rfl | rfl
    · simp at hft; subst hft; exact kind_le_join_arg _ _ _ 0 (by simp [optD] at ha; omega)
    · simp at hft
  · split at hd
    · cases hd
      refine ⟨by simp [resD], fun _ => by simp [optD, resD, tokD], fun args ha v hv ft hft => ?_⟩
      simp [resD] at hv ha; rcases hv with rfl | rfl
      · simp at hft; subst hft; exact kind_le_join_arg _ _ _ 0 (by omega)
      · simp at hft; subst hft; exact kind_le_join_arg _ _ _ 1 (by omega)
    · split at hd
      · cases hd
        refine ⟨by simp [tokD], fun _ => by simp [optD, resD, tokD], fun args ha v hv ft hft => ?_⟩
        simp [tokD] at hv; subst hv; simp at hft
      · cases hd

theorem ex_progOk : ProgOk exP exPrim :=
  ⟨ex_adts, ⟨⟨optD, rfl, rfl, rfl, rfl, rfl⟩, ⟨resD, rfl, rfl, rfl, rfl, rfl⟩⟩, fun f d h => by simp [exP] at h⟩

theorem ex_primsOk : PrimsOk exP exPrim := fun _ _ _ h => h.elim

theorem ex_tok : exP.adts "Tok" = some tokD := rfl

theorem ex_typed : HasTy exP exPrim topSig [] exE .unit [] := by
  have hcon : HasTy exP exPrim topSig [] (.con "Tok" 0 []) (.adt "Tok" []) [] :=
    .con (d := tokD) (name := "T") (ts := []) ex_tok rfl rfl .nil
  refine .letE (a := false) (Γ2 := []) hcon ?_ (by simp)
  have hmv : HasTy exP exPrim topSig [⟨"c", .adt "Tok" [], false, true⟩] (.place "c" []) (.adt "Tok" [])
      [⟨"c", .adt "Tok" [], false, false⟩] :=
    .move (en := ⟨"c", .adt "Tok" [], false, true⟩) (by simp [Ctx.find]) rfl
  refine .mtch hmv ?_
  refine .cons (bs := []) (Γb := []) (.con (d := tokD) (tag := 0) (ts := []) ex_tok rfl rfl rfl .nil)
    (by simp) (by simp) .lit rfl noLinear_nil .nil

/-- The example's run is never stuck, for every fuel. -/
theorem ex_never_stuck (n : Nat) : ∀ k w, eval exP n [] {} exE ≠ .err (.stuck k w) :=
  (Theorems.well_typed_never_stuck exP exPrim ex_progOk ex_primsOk topSig [] [] exE .unit ex_typed []
    (fun _ h => by cases h) ⟨Nat.le_refl _, fun _ h => by cases h⟩ n {}).1

/-- And the evaluator completes it, discharging the obligation it created. -/
theorem ex_runs : ∃ ρ st, eval exP 10 [] {} exE = .ok .unit ρ st ∧ st.burned = [⟨0, true⟩] := by
  refine ⟨[], _, rfl, rfl⟩

end Tenon.Examples
