/-
Linear and unique soundness, the theorem (Linear.lean has the invariant and
the lemmas about the evaluator's helpers): induction on fuel over the ten
mutually recursive functions of the evaluator.
-/
import TenonCore.Linear

namespace Tenon

variable (P : Prog)

/-! ## The theorem -/

def RecvT : Option (Sum (String × List Step) Val) → Prop
  | some (.inr v) => v.toks = []
  | _ => True

/-- The statement for every function of the evaluator at fuel `n`. -/
def LinSafe (n : Nat) : Prop :=
  (∀ ρ st e, StOk st → OutT [] ρ st Val.toks (eval P n ρ st e)) ∧
  (∀ ρ st es, StOk st → OutT [] ρ st toksL (evalList P n ρ st es)) ∧
  (∀ ρ st ps, StOk st → OutT [] ρ st (fun _ => []) (evalSteps P n ρ st ps)) ∧
  (∀ ρ st m e, StOk st → OutT [] ρ st (·.v.toks) (evalArg P n ρ st m e)) ∧
  (∀ ρ st ms es, StOk st → OutT [] ρ st argsToks (evalArgs P n ρ st ms es)) ∧
  (∀ ρ st e, StOk st → OutT [] ρ st (fun _ => []) (evalOpnd P n ρ st e)) ∧
  (∀ ρ st es, StOk st → OutT [] ρ st (fun _ => []) (evalOpnds P n ρ st es)) ∧
  (∀ ρ st v arms, StOk st → OutT v.toks ρ st Val.toks (evalArms P n ρ st v arms)) ∧
  (∀ ρ st owner ps names cvs body pre args, StOk st →
    OutT (argsToks pre ++ toksL cvs) ρ st Val.toks (callWith P n ρ st owner ps names cvs body pre args)) ∧
  (∀ ρ st pf recv args, StOk st → RecvT recv → OutT [] ρ st Val.toks (primCall P n ρ st pf recv args))

theorem linSafe_zero : LinSafe P 0 := by
  refine ⟨?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_⟩ <;> intros <;>
    simp [eval, evalList, evalSteps, evalArg, evalArgs, evalOpnd, evalOpnds, evalArms, callWith, primCall, OutT]

/-- `Bal` facts close by arithmetic on the counts. -/
macro "bal" : tactic => `(tactic| (intro t; (try simp only [List.count_append, List.count_nil, Val.toks, toksL,
  argsToks, ctlToks, List.append_nil, List.nil_append] at *); (try omega)))
macro "bal1" h:term:max : tactic => `(tactic| (intro t; have := $h t; (try simp only [List.count_append,
  List.count_nil, Val.toks, toksL, argsToks, ctlToks, List.append_nil, List.nil_append] at *); (try omega)))
macro "bal2" h1:term:max h2:term:max : tactic => `(tactic| (intro t; have := $h1 t; have := $h2 t; (try simp only [List.count_append, List.count_nil, Val.toks, toksL, argsToks, ctlToks, List.append_nil, List.nil_append] at *); (try omega)))

theorem linSafe_succ {n : Nat} (ih : LinSafe P n) : LinSafe P (n + 1) := by
  obtain ⟨hE, hL, hS, hA, hAs, hO, hOs, hM, hC, hPc⟩ := ih
  refine ⟨?eval, ?list, ?steps, ?arg, ?args, ?opnd, ?opnds, ?arms, ?call, ?prim⟩
  case eval =>
    intro ρ st e hs
    cases e with
    | lit l => simp only [eval]; refine ⟨fun t => ?_, hs⟩; cases l <;> simp [Lit.val, Val.toks]
    | place x ps =>
      simp only [eval]
      exact OutT.bind (hS ρ st ps hs) fun ss ρ1 st1 _ _ hs1 => readPlace_T P hs1
    | proj e ps =>
      simp only [eval]
      refine OutT.bind (hE ρ st e hs) fun v ρ1 st1 _ _ hs1 => ?_
      split
      · rename_i hv
        rw [hv]
        refine OutT.bind (hS ρ1 st1 ps hs1) fun ss ρ2 st2 _ _ hs2 => ?_
        split
        · rename_i w hw
          refine ⟨fun t => ?_, hs2⟩
          have := getPath_le t P hw
          rw [hv] at this; simp at this ⊢; omega
        · rename_i pe _; cases pe <;> trivial
      · trivial
    | seq k es =>
      simp only [eval]
      exact OutT.bind (hL ρ st es hs) fun vs ρ1 st1 _ _ hs1 => ⟨Bal.refl _ _ _, hs1⟩
    | con s tag es =>
      simp only [eval]
      refine OutT.bind (hL ρ st es hs) fun vs ρ1 st1 _ _ hs1 => ?_
      split
      · obtain ⟨b, d, m, o⟩ := mint_spec st1 (by assumption : AdtDecl).kind
        refine ⟨fun t => ?_, o hs1⟩
        rw [b, d, m]; simp [Val.toks, List.count_append]; omega
      · trivial
    | lam ps body =>
      simp only [eval]
      refine ⟨fun t => ?_, hs⟩
      have := capture_toks ρ
      simp [Val.toks, this]
    | clos caps ps body =>
      simp only [eval]
      split
      · rename_i vs hc
        refine ⟨fun t => ?_, hs⟩
        have := (captureNames_toks ρ hc).1
        simp [Val.toks, this]
      · trivial
    | ann t e => simp only [eval]; exact hE ρ st e hs
    | fnref f => simp only [eval]; exact ⟨fun t => by simp [Val.toks], hs⟩
    | call f args =>
      simp only [eval]
      refine OutT.bind (hE ρ st f hs) fun fv ρ1 st1 _ _ hs1 => ?_
      split
      · split
        · exact (hC _ _ _ _ _ _ _ _ _ hs1).weaken (by bal)
        · split
          · exact (hPc _ _ _ none _ hs1 trivial).weaken (by bal)
          · trivial
      · exact (hC _ _ _ _ _ _ _ _ _ hs1).weaken (by bal)
      · trivial
    | mcall m recv args =>
      simp only [eval]
      split
      · rename_i x ps
        refine OutT.bind (hS ρ st ps hs) fun ss ρ1 st1 _ _ hs1 => ?_
        rcases peek_spec P (ρ := ρ1) (st := st1) (x := x) (ss := ss) with ⟨v0, w0, hp, -, -⟩ | ⟨e, hp⟩
        · rw [hp]
          simp only [Out.bind]
          split
          · split
            · refine OutT.bind (placeArg_T P hs1) fun a0 ρ2 st2 _ _ hs2 => ?_
              exact (hC _ _ _ _ _ _ _ _ _ hs2).weaken (by bal)
            · trivial
          · exact hPc _ _ _ _ _ hs1 trivial
          · trivial
        · rw [hp]; trivial
      · refine OutT.bind (hE ρ st _ hs) fun v0 ρ1 st1 _ _ hs1 => ?_
        split
        · split
          · exact (hC _ _ _ _ _ _ _ _ _ hs1).weaken (by bal)
          · trivial
        · split
          · rename_i h0
            exact (hPc _ _ _ (some (.inr v0)) _ hs1 h0).weaken (by intro t; simp [h0])
          · trivial
        · trivial
    | prim p args =>
      simp only [eval]
      split
      · exact hPc _ _ _ _ _ hs trivial
      · trivial
    | letE x mu e body =>
      simp only [eval]
      refine OutT.bind (hE ρ st e hs) fun v ρ1 st1 _ _ hs1 => ?_
      exact (popScope_T (hE _ _ _ hs1)).weaken (by intro t; rw [envToks_cons]; simp only [slotToks, List.count_append, List.count_nil]; omega)
    | assign x ps e =>
      simp only [eval]
      refine OutT.bind (hS ρ st ps hs) fun ss ρ1 st1 hr _ hs1 => ?_
      have hk := evalSteps_toks P n ρ st ps hr
      exact OutT.bind (hE ρ1 st1 e hs1) fun v ρ2 st2 _ _ hs2 => assignAt_T P hk hs2
    | seqE e1 e2 =>
      simp only [eval]
      refine OutT.bind (hE ρ st e1 hs) fun v ρ1 st1 _ _ hs1 => ?_
      split
      · rename_i st2 h
        exact (hE _ _ _ (StOk.discard h hs1)).weaken (discard_bal h ρ1)
      · trivial
    | ite c t f =>
      simp only [eval]
      refine OutT.bind (hE ρ st c hs) fun cv ρ1 st1 _ _ hs1 => ?_
      split
      · exact (hE _ _ _ hs1).weaken (by bal)
      · trivial
    | mtch e arms =>
      simp only [eval]
      exact OutT.bind (hE ρ st e hs) fun v ρ1 st1 _ _ hs1 => hM _ _ _ _ hs1
    | «while» c body =>
      simp only [eval]
      refine OutT.bind (hE ρ st c hs) fun cv ρ1 st1 _ _ hs1 => ?_
      split
      · exact ⟨by bal, hs1⟩
      · have hb := hE ρ1 st1 body hs1
        split
        · rename_i v ρ2 st2 heq
          rw [heq] at hb
          split
          · rename_i st3 h
            exact ((hE _ _ _ (StOk.discard h hb.2)).weaken (discard_bal h ρ2)).weaken (by bal1 hb.1)
          · trivial
        · rename_i ρ2 st2 heq; rw [heq] at hb
          exact (hE _ _ _ hb.2).weaken (by bal1 hb.1)
        · rename_i ρ2 st2 heq; rw [heq] at hb
          exact ⟨by bal1 hb.1, hb.2⟩
        · rename_i v ρ2 st2 heq; rw [heq] at hb; exact ⟨by bal1 hb.1, hb.2⟩
        · trivial
      · trivial
    | ret e =>
      simp only [eval]
      exact OutT.bind (hE ρ st e hs) fun v ρ1 st1 _ _ hs1 => ⟨Bal.refl _ _ _, hs1⟩
    | brk => simp only [eval]; exact ⟨by intro t; simp [ctlToks], hs⟩
    | cont => simp only [eval]; exact ⟨by intro t; simp [ctlToks], hs⟩
    | «try» e =>
      simp only [eval]
      refine OutT.bind (hE ρ st e hs) fun v ρ1 st1 _ _ hs1 => ?_
      split
      · rename_i x hx; have := tryVal_toks hx; exact ⟨by intro t; simp only at this; rw [this], hs1⟩
      · rename_i r hr; have := tryVal_toks hr; exact ⟨by intro t; simp only [ctlToks]; simp only at this; rw [this], hs1⟩
      · trivial
    | unsup w => simp only [eval]; trivial
  case list =>
    intro ρ st es hs
    cases es with
    | nil => simp only [evalList]; exact ⟨by intro t; simp [toksL], hs⟩
    | cons e es =>
      simp only [evalList]
      refine OutT.bind (hE ρ st e hs) fun v ρ1 st1 _ _ hs1 => ?_
      have hl := hL ρ1 st1 es hs1
      split
      · rename_i vs ρ2 st2 heq; rw [heq] at hl
        exact ⟨by bal1 hl.1, hl.2⟩
      · rename_i c ρ2 st2 heq; rw [heq] at hl
        split
        · rename_i st3 h
          have hd := discard_bal h ρ2
          exact ⟨by bal2 hl.1 hd, StOk.discard h hl.2⟩
        · trivial
      · trivial
  case steps =>
    intro ρ st ps hs
    cases ps with
    | nil => simp only [evalSteps]; exact ⟨by bal, hs⟩
    | cons s ss =>
      cases s with
      | fld f =>
        simp only [evalSteps]
        exact OutT.bind (hS ρ st ss hs) fun ss' ρ1 st1 _ _ hs1 => ⟨Bal.refl _ _ _, hs1⟩
      | tfld i =>
        simp only [evalSteps]
        exact OutT.bind (hS ρ st ss hs) fun ss' ρ1 st1 _ _ hs1 => ⟨Bal.refl _ _ _, hs1⟩
      | idx e =>
        simp only [evalSteps]
        refine OutT.bind (hE ρ st e hs) fun k ρ1 st1 _ _ hs1 => ?_
        split
        · rename_i hk
          have h2 : OutT [] ρ1 st1 (fun _ => [])
              ((evalSteps P n ρ1 st1 ss).bind fun ss' ρ2 st2 => Out.ok (Step.idx k :: ss') ρ2 st2) :=
            OutT.bind (hS ρ1 st1 ss hs1) fun ss' ρ2 st2 _ _ hs2 => ⟨Bal.refl _ _ _, hs2⟩
          exact h2.weaken (by intro t; simp [hk])
        · trivial
  case arg =>
    intro ρ st m e hs
    cases m with
    | val =>
      simp only [evalArg]
      exact OutT.bind (hE ρ st e hs) fun v ρ1 st1 _ _ hs1 => ⟨Bal.refl _ _ _, hs1⟩
    | ref =>
      cases e with
      | place x ps =>
        simp only [evalArg]
        exact OutT.bind (hS ρ st ps hs) fun ss ρ1 st1 _ _ hs1 => placeArg_T P hs1
      | _ => simp [evalArg, OutT, stuckT]
    | «mut» =>
      cases e with
      | place x ps =>
        simp only [evalArg]
        exact OutT.bind (hS ρ st ps hs) fun ss ρ1 st1 _ _ hs1 => placeArg_T P hs1
      | _ => simp [evalArg, OutT, stuckT]
  case args =>
    intro ρ st ms es hs
    cases ms with
    | nil =>
      cases es with
      | nil => simp only [evalArgs]; exact ⟨by intro t; simp [argsToks], hs⟩
      | cons e es => simp [evalArgs, OutT, stuckT]
    | cons m ms =>
      cases es with
      | nil => simp [evalArgs, OutT, stuckT]
      | cons e es =>
        simp only [evalArgs]
        refine OutT.bind (hA ρ st m e hs) fun a ρ1 st1 _ _ hs1 => ?_
        have hl := hAs ρ1 st1 ms es hs1
        split
        · rename_i as ρ2 st2 heq; rw [heq] at hl
          exact ⟨by bal1 hl.1, hl.2⟩
        · rename_i c ρ2 st2 heq; rw [heq] at hl
          split
          · rename_i ρ3 st3 h
            obtain ⟨hb, hs3⟩ := unwindArg_T h hl.2
            exact ⟨by bal2 hl.1 hb, hs3⟩
          · trivial
        · trivial
  case opnd =>
    intro ρ st e hs
    cases e with
    | place x ps =>
      simp only [evalOpnd]
      refine OutT.bind (hS ρ st ps hs) fun ss ρ1 st1 _ _ hs1 => ?_
      rcases peek_spec P (ρ := ρ1) (st := st1) (x := x) (ss := ss) with ⟨v, v0, hp, -, -⟩ | ⟨e, hp⟩
      · rw [hp]; simp only [Out.bind]; exact ⟨Bal.refl _ _ _, hs1⟩
      · rw [hp]; trivial
    | _ =>
      simp only [evalOpnd]
      refine OutT.bind (hE ρ st _ hs) fun v ρ1 st1 _ _ hs1 => ?_
      split
      · rename_i hv; exact ⟨by intro t; simp [hv], hs1⟩
      · trivial
  case opnds =>
    intro ρ st es hs
    cases es with
    | nil => simp only [evalOpnds]; exact ⟨by bal, hs⟩
    | cons e es =>
      simp only [evalOpnds]
      refine OutT.bind (hO ρ st e hs) fun o ρ1 st1 _ _ hs1 => ?_
      exact OutT.bind (hOs ρ1 st1 es hs1) fun os ρ2 st2 _ _ hs2 => ⟨Bal.refl _ _ _, hs2⟩
  case arms =>
    intro ρ st v arms hs
    cases arms with
    | nil => simp only [evalArms]; trivial
    | cons arm arms =>
      obtain ⟨p, g, body⟩ := arm
      simp only [evalArms]
      split
      · exact hM _ _ _ _ hs
      · trivial
      · rename_i bs burn drop hm
        cases g with
        | none =>
          simp only
          split
          · rename_i st1 h
            obtain ⟨b1, m1, n1, d1, o1⟩ := discardAll_spec h
            have hs1 : StOk st1 := o1 hs
            refine (popScope_T (hE _ _ _ hs1)).weaken (fun t => ?_)
            have e1 := matchPat_toks t P p v hm
            rw [pushBinds_toks, b1, m1, d1 t]
            simp [List.count_append] at e1 ⊢; omega
          · trivial
        | some ge =>
          simp only
          split
          · rename_i hv
            have hz : ∀ t, (toksL (bs.map (·.2))).count t = 0 := by
              intro t; have e1 := matchPat_toks t P p v hm; rw [hv] at e1; simp at e1; omega
            have hpush : Bal [] (pushBinds bs ρ) st v.toks ρ st := by
              intro t; have := hz t; rw [pushBinds_toks, hv]; simp [List.count_append]; omega
            have hg := hE (pushBinds bs ρ) st ge hs
            split
            · rename_i ρ1 st1 heq; rw [heq] at hg
              exact ((popScope_T (hE _ _ _ hg.2)).weaken (by bal1 hg.1)).weaken hpush
            · rename_i ρ1 st1 heq; rw [heq] at hg
              have hp := popEnv_T (k := bs.length) (ρ := ρ1) hg.2
              cases hq : popEnv bs.length ρ1 st1 with
              | ok u ρ2 st2 =>
                rw [hq] at hp; simp only [Out.bind]
                refine ((hM _ _ _ _ hp.2).weaken ?_)
                intro t; have a := hp.1 t; have b := hg.1 t; have c := hpush t
                rw [hv] at c ⊢; simp [Val.toks] at a b c ⊢; omega
              | ctl c ρ' st' => exact absurd hq popEnv_ne_ctl
              | err e => simp [Out.bind, OutT]
            · trivial
            · rename_i c ρ1 st1 heq; rw [heq] at hg
              exact (popScope_T hg).weaken hpush
            · trivial
          · trivial
  case call =>
    intro ρ st owner ps names cvs body pre args hs
    simp only [callWith]
    split
    case isFalse => trivial
    rename_i hcv
    obtain ⟨hlen, hz⟩ := hcv
    have ha := hAs ρ st ((ps.drop pre.length).map (·.2)) args hs
    split
    · rename_i as ρ1 st1 heq; rw [heq] at ha
      split
      · rename_i hl
        have hf := frameOf_toks names cvs hlen ps (pre ++ as) hl
        refine (afterCall_T P (hE _ _ _ ha.2)).weaken (fun t => ?_)
        have := ha.1 t
        rw [hf, argsToks_append, hz]
        simp [List.count_append] at this ⊢; omega
      · trivial
    · rename_i c ρ1 st1 heq; rw [heq] at ha
      split
      · rename_i ρ2 st2 h
        obtain ⟨hb, hs2⟩ := unwindArgs_T h ha.2
        exact ⟨by have := ha.1; intro t; have := this t; have := hb t; rw [hz]; simp only [List.count_append, List.count_nil] at *; omega, hs2⟩
      · trivial
    · trivial
  case prim =>
    intro ρ st pf recv args hs hr
    simp only [primCall]
    refine OutT.bind (hOs ρ st args hs) fun os ρ1 st1 _ _ hs1 => ?_
    split
    · exact primApply_T P hs1
    · rename_i x ss
      rcases peek_spec P (ρ := ρ1) (st := st1) (x := x) (ss := ss) with ⟨v1, v0, hp, -, -⟩ | ⟨e, hp⟩
      · rw [hp]; simp only [Out.bind]; exact primApply_T P hs1
      · rw [hp]; trivial
    · exact primApply_T P hs1

theorem linSafe (n : Nat) : LinSafe P n := by
  induction n with
  | zero => exact linSafe_zero P
  | succ n ih => exact linSafe_succ P ih

/-- **Conservation of obligations.** Along any evaluation that ends with a
value or an early exit (not stuck, no trap), every token is held, discharged
or dropped exactly as often as it was held before or minted; only unique
tokens are dropped; minted tokens are distinct. -/
theorem obligations_conserved (P : Prog) (n : Nat) (ρ : Env) (st : St) (e : Expr) (hs : StOk st) :
    match eval P n ρ st e with
    | .ok v ρ' st' => Bal v.toks ρ' st' [] ρ st ∧ StOk st'
    | .ctl c ρ' st' => Bal (ctlToks c) ρ' st' [] ρ st ∧ StOk st'
    | .err _ => True := by
  have h := (linSafe P n).1 ρ st e hs
  revert h
  cases eval P n ρ st e <;> exact id

theorem StOk.empty : StOk {} := ⟨by simp, by simp, by simp⟩

/-- **Each linear obligation exactly once; no unique value duplicated.**
Run an expression from the empty state in an environment holding no
obligation (as `main` is started with `Sys`). If it ends with a value, then
every token it minted occurs exactly once among the final value, the final
environment, the discharged and the dropped ones; a linear token is never
dropped, so it is discharged exactly once unless it is still held; and no
other token occurs anywhere (nothing forged). -/
theorem obligations_exactly_once (P : Prog) (n : Nat) (ρ : Env) (e : Expr) (v : Val) (ρ' : Env) (st' : St)
    (hρ : envToks ρ = []) (h : eval P n ρ {} e = .ok v ρ' st') :
    (∀ t ∈ st'.minted, (v.toks ++ envToks ρ' ++ st'.burned ++ st'.dropped).count t = 1) ∧
    (∀ t, t ∉ st'.minted → (v.toks ++ envToks ρ' ++ st'.burned ++ st'.dropped).count t = 0) ∧
    (∀ t ∈ st'.minted, t.lin = true → st'.dropped.count t = 0 ∧
      st'.burned.count t + (v.toks ++ envToks ρ').count t = 1) := by
  have hc := obligations_conserved P n ρ {} e StOk.empty
  rw [h] at hc
  obtain ⟨hb, hd, hnd, _⟩ := hc
  have key : ∀ t, (v.toks ++ envToks ρ' ++ st'.burned ++ st'.dropped).count t = st'.minted.count t := by
    intro t; have := hb t; rw [hρ] at this; simp [List.count_append] at this ⊢; omega
  refine ⟨fun t ht => ?_, fun t ht => ?_, fun t ht hl => ?_⟩
  · rw [key, List.Nodup.count hnd, if_pos ht]
  · rw [key]; exact List.count_eq_zero_of_not_mem ht
  · have h0 : st'.dropped.count t = 0 := List.count_eq_zero_of_not_mem fun hm => by
      have := hd t hm; rw [hl] at this; cases this
    refine ⟨h0, ?_⟩
    have := key t; rw [List.Nodup.count hnd, if_pos ht] at this
    simp [List.count_append] at this ⊢; omega

/-- A complete program: when the result and the final environment hold no
obligation (a `main` that returned `Unit`, an `Int` or a `Result` without
obligations), every linear value it created was discharged exactly once. -/
theorem linear_discharged_exactly_once (P : Prog) (n : Nat) (ρ : Env) (e : Expr) (v : Val) (ρ' : Env) (st' : St)
    (hρ : envToks ρ = []) (h : eval P n ρ {} e = .ok v ρ' st') (hv : v.toks = []) (hρ' : envToks ρ' = []) :
    ∀ t ∈ st'.minted, t.lin = true → st'.burned.count t = 1 ∧ st'.dropped.count t = 0 := by
  intro t ht hl
  have := (obligations_exactly_once P n ρ e v ρ' st' hρ h).2.2 t ht hl
  rw [hv, hρ'] at this
  simp at this
  exact ⟨this.2, this.1⟩

end Tenon
