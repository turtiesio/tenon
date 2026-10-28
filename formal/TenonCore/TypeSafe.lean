/-
Type soundness (formal/README.md, "Theorems"): a well-typed expression of a
well-typed program, run in an environment that matches its context, never
gets stuck — neither a type error nor a broken obligation rule — and never
reaches a construct outside the core; a value it returns has its type and the
environment matches the context the judgement leaves; an early exit is one
the judgement allows. Running out of fuel and traps remain possible.

The proof is an induction on fuel over the evaluator's mutually recursive
functions (as `capSafe` and `linSafe`), with inversion of the typing
judgement (Typing.lean) at each step.
-/
import TenonCore.TypeSafeHelpers

namespace Tenon

section
variable (X : Ext) (P : Prog) (prim : PrimSig)

/-- Evaluated builtin operands: typed values; a place operand's resolved path,
its variable still in scope. -/
inductive OpndsOk (Γ : Ctx) : List (Val × Option (String × List Step)) → List Ty → Prop
  | nil : OpndsOk Γ [] []
  | cons {o os t ts} : ValTyX X P prim o.1 t →
      (∀ x ss, o.2 = some (x, ss) → ∃ en, Γ.find x = some en ∧ en.avail = true ∧ StepsTy X P prim en.ty ss t) →
      OpndsOk Γ os ts → OpndsOk Γ (o :: os) (t :: ts)

/-- A builtin's receiver: none (the operands are its arguments), a place still
in scope, or a value without obligations. -/
def RecvOk (Γ : Ctx) (ts tsA : List Ty) : Option (Sum (String × List Step) Val) → Prop
  | none => tsA = ts
  | some (.inl (x, ss)) => ∃ en t0, tsA = t0 :: ts ∧ Γ.find x = some en ∧ en.avail = true ∧ StepsTy X P prim en.ty ss t0
  | some (.inr v0) => ∃ t0, tsA = t0 :: ts ∧ ValTyX X P prim v0 t0 ∧ t0.copyable P

/-- The statement for every function of the evaluator at fuel `n`. -/
structure TySafe (n : Nat) : Prop where
  eval : ∀ Δ Γ Γ' e t ρ st, HasTyX X P prim Δ Γ e t Γ' → EnvOkX X P prim ρ Γ → SigOk Δ Γ →
    OutTy X P prim Δ Γ Γ' (ValTyX X P prim · t) (eval P n ρ st e)
  list : ∀ Δ Γ Γ' es ts ρ st, ListTyX X P prim Δ Γ es ts Γ' → EnvOkX X P prim ρ Γ → SigOk Δ Γ →
    OutTy X P prim Δ Γ Γ' (fun vs => vs.length = ts.length ∧ ∀ q ∈ vs.zip ts, ValTyX X P prim q.1 q.2)
      (evalList P n ρ st es)
  steps : ∀ Δ Γ Γ' T ps t ρ st, PathTyX X P prim Δ Γ T ps t Γ' → EnvOkX X P prim ρ Γ → SigOk Δ Γ →
    OutTy X P prim Δ Γ Γ' (fun ss => StepsTy X P prim T ss t ∧ ss.length = ps.length) (evalSteps P n ρ st ps)
  argv : ∀ Δ Γ Γ' e t ρ st, HasTyX X P prim Δ Γ e t Γ' → EnvOkX X P prim ρ Γ → SigOk Δ Γ →
    OutTy X P prim Δ Γ Γ' (fun a : ArgV => ValTyX X P prim a.v t ∧ a.wb = .none) (evalArg P n ρ st .val e)
  argr : ∀ Δ Γ Γ' m x ps en t ρ st, m ≠ .val → Γ.find x = some en → en.avail = true → PathTyX X P prim Δ Γ en.ty ps t Γ' →
    Γ'.Avail x → t.copyable P → EnvOkX X P prim ρ Γ → SigOk Δ Γ →
    OutTy X P prim Δ Γ Γ' (fun a : ArgV => ValTyX X P prim a.v t ∧ ∃ ss, a.wb = .place x ss ∧ StepsTy X P prim en.ty ss t)
      (evalArg P n ρ st m (.place x ps))
  args : ∀ Δ Γ Γ' ms es ts ρ st, ArgsTyX X P prim Δ Γ ms es ts Γ' → EnvOkX X P prim ρ Γ → SigOk Δ Γ →
    OutTy X P prim Δ Γ Γ' (fun as => ArgsOk X P prim Γ' ms as ts) (evalArgs P n ρ st ms es)
  opp : ∀ Δ Γ Γ' x ps en t ρ st, Γ.find x = some en → en.avail = true → PathTyX X P prim Δ Γ en.ty ps t Γ' →
    Γ'.Avail x → EnvOkX X P prim ρ Γ → SigOk Δ Γ →
    OutTy X P prim Δ Γ Γ' (fun o => ValTyX X P prim o.1 t ∧ ∃ ss, o.2 = some (x, ss) ∧ StepsTy X P prim en.ty ss t)
      (evalOpnd P n ρ st (.place x ps))
  opv : ∀ Δ Γ Γ' e t ρ st, (∀ x ps, e ≠ .place x ps) → HasTyX X P prim Δ Γ e t Γ' → t.copyable P →
    EnvOkX X P prim ρ Γ → SigOk Δ Γ →
    OutTy X P prim Δ Γ Γ' (fun o => ValTyX X P prim o.1 t ∧ o.2 = none) (evalOpnd P n ρ st e)
  opnds : ∀ Δ Γ Γ' es ts ρ st, OpndsTyX X P prim Δ Γ es ts Γ' → EnvOkX X P prim ρ Γ → SigOk Δ Γ →
    OutTy X P prim Δ Γ Γ' (fun os => OpndsOk X P prim Γ' os ts) (evalOpnds P n ρ st es)
  arms : ∀ Δ Γ Γ' t0 arms t v ρ st, ArmsTyX X P prim Δ Γ t0 arms t Γ' → ValTyX X P prim v t0 → EnvOkX X P prim ρ Γ → SigOk Δ Γ →
    OutTy X P prim Δ Γ Γ' (ValTyX X P prim · t) (evalArms P n ρ st v arms)
  call : ∀ Δ Δ' Γ Γ' ρ st owner ps names cvs body pre args tys r Δb Γt Γb,
    names.length = cvs.length → toksL cvs = [] → tys.length = ps.length →
    FrameSig P owner ps r Δb Γt.length → (∀ e ∈ Γt, ¬ e.ty.linear P) → EnvOkX X P prim (capEnv names cvs) Γt →
    HasTyX X P prim Δb (paramsCtx ps tys ++ Γt) body r Γb → FinFn P owner ps (Γb.take ps.length) →
    pre.length ≤ ps.length →
    ArgsOk X P prim Γ' ((ps.take pre.length).map (·.2)) pre (tys.take pre.length) →
    ArgsTyX X P prim Δ' Γ ((ps.drop pre.length).map (·.2)) args (tys.drop pre.length) Γ' →
    (Δ' = Δ.noExit ∨ (Δ' = Δ ∧ ∀ a ∈ pre, a.v.hasLin = false)) →
    EnvOkX X P prim ρ Γ → SigOk Δ Γ →
    OutTy X P prim Δ Γ Γ' (ValTyX X P prim · r) (callWith P n ρ st owner ps names cvs body pre args)
  prim : ∀ Δ Γ Γ' pf recv args ts t tsA ρ st, PfOkX X P prim pf tsA t → t.copyable P →
    OpndsTyX X P prim Δ Γ args ts Γ' → RecvOk X P prim Γ' ts tsA recv → EnvOkX X P prim ρ Γ → SigOk Δ Γ →
    OutTy X P prim Δ Γ Γ' (ValTyX X P prim · t) (primCall P n ρ st pf recv args)

end

section
variable {X : Ext} {P : Prog} {prim : PrimSig}

/-! ## Small facts -/

theorem SigOk.shape {Δ : Sig} {Γ Γ' : Ctx} (h : SigOk Δ Γ) (hs : Shape Γ' Γ) : SigOk Δ Γ' := by
  rw [SigOk, hs.length]; exact h

theorem SigOk.cons {Δ : Sig} {Γ : Ctx} (h : SigOk Δ Γ) (e : Entry) : SigOk Δ (e :: Γ) :=
  ⟨by have := h.1; simp; omega, fun Γl hl => by have := h.2 Γl hl; simp; omega⟩

theorem SigOk.append {Δ : Sig} {Γ : Ctx} (h : SigOk Δ Γ) (Γb : Ctx) : SigOk Δ (Γb ++ Γ) :=
  ⟨by have := h.1; simp; omega, fun Γl hl => by have := h.2 Γl hl; simp; omega⟩

theorem SigOk.noExit {Δ : Sig} {Γ : Ctx} (h : SigOk Δ Γ) : SigOk Δ.noExit Γ :=
  ⟨h.1, fun Γl hl => by simp [Sig.noExit] at hl⟩

theorem SigOk.tail {Δ Δ' : Sig} {t : Ty} {Γ : Ctx} (h : SigOk Δ Γ) (hΔ : TailSig P Δ Δ' t) : SigOk Δ' Γ := by
  rcases hΔ with ⟨rfl, -⟩ | rfl
  · exact h
  · exact h.noExit

theorem SigOk.withLoop {Δ : Sig} {Γ : Ctx} (h : SigOk Δ Γ) : SigOk (Δ.withLoop Γ) Γ :=
  ⟨h.1, fun Γl hl => by simp [Sig.withLoop] at hl; subst hl; exact Nat.le_refl _⟩

theorem SigOk.frame {Δb : Sig} {owner : Option String} {ps : List (String × Mode)} {tys : List Ty} {r : Ty}
    {Γt : Ctx} (h : FrameSig P owner ps r Δb Γt.length) (hl : tys.length = ps.length) :
    SigOk Δb (paramsCtx ps tys ++ Γt) :=
  ⟨by rw [h.2.2.1]; simp [paramsCtx_length ps tys hl], fun Γl hl' => by rw [h.2.1] at hl'; cases hl'⟩

theorem FinFn.length {P : Prog} {owner : Option String} :
    ∀ {ps : List (String × Mode)} {Γ : Ctx}, FinFn P owner ps Γ → Γ.length = ps.length
  | [], [], _ => rfl
  | _ :: _, _ :: _, h => by simp [FinFn.length h.2]
  | [], _ :: _, h | _ :: _, [], h => h.elim

theorem FinFn.take {P : Prog} {owner : Option String} {ps : List (String × Mode)} {Γ : Ctx}
    (h : FinFn P owner ps Γ) : FinFn P owner ps (Γ.take ps.length) := by
  rw [List.take_of_length_le (by rw [h.length]; exact Nat.le_refl _)]; exact h

theorem SigOk.fn (owner : Option String) (ps : List (String × Mode)) (tys : List Ty) (r : Ty)
    (hl : tys.length = ps.length) : SigOk (fnSig P owner ps r) (paramsCtx ps tys) :=
  ⟨by simp [Tenon.fnSig, paramsCtx_length ps tys hl], fun Γl hl => by simp [Tenon.fnSig] at hl⟩

theorem Lit.valTy (l : Lit) : ValTyX X P prim l.val l.ty := by
  cases l <;> constructor

theorem Ctx.Avail.get {Γ' Γ : Ctx} {x : String} {en : Entry} (h : Γ'.Avail x) (hs : Shape Γ' Γ)
    (hf : Γ.find x = some en) : ∃ en', Γ'.find x = some en' ∧ en'.avail = true ∧ en'.ty = en.ty := by
  obtain ⟨e1, h1, ha⟩ := h
  obtain ⟨e2, h2, hk⟩ := hs.symm.find h1
  rw [hf] at h2; cases h2
  exact ⟨e1, h1, ha, (Entry.key_ty hk).symm⟩

theorem ArgsTyX.length : ∀ {Δ : Sig} {Γ Γ' : Ctx} {ms : List Mode} {es : List Expr} {ts : List Ty},
    ArgsTyX X P prim Δ Γ ms es ts Γ' → ms.length = es.length ∧ ts.length = es.length
  | _, _, _, _, _, _, .nil => ⟨rfl, rfl⟩
  | _, _, _, _, _, _, .val _ _ h => by have := ArgsTyX.length h; simp [this.1, this.2]
  | _, _, _, _, _, _, .byRef _ _ _ _ _ _ _ h _ => by have := ArgsTyX.length h; simp [this.1, this.2]

theorem modes_all_val {ps : List (String × Mode)} (h : ∀ p ∈ ps, p.2 = .val) {args : List Expr}
    (hl : ps.length = args.length) : ps.map (·.2) = args.map fun _ => Mode.val := by
  apply List.ext_getElem (by simp [hl])
  intro i h1 h2
  simp only [List.getElem_map]
  exact h _ (List.getElem_mem _)

theorem eval_mcall_val {recv : Expr} (h : ∀ x ps, recv ≠ .place x ps) (n : Nat) (ρ : Env) (st : St) (m : String)
    (args : List Expr) : eval P (n + 1) ρ st (.mcall m recv args) =
    (eval P n ρ st recv).bind fun v0 ρ1 st1 => match resolve P v0.head m with
      | .tenon d => match d.params with
        | (_, .val) :: _ => callWith P n ρ1 st1 d.owner d.params [] [] d.body [⟨v0, .none⟩] args
        | _ => stuckT "a ref or mut receiver must be a place"
      | .prim pf =>
        if v0.toks = [] then primCall P n ρ1 st1 pf (some (.inr v0)) args
        else stuckL "an obligation passed to a builtin"
      | .none => stuckT s!"no method {m}" := by
  cases recv <;> first | rfl | exact absurd rfl (h _ _)

theorem evalOpnd_val {e : Expr} (h : ∀ x ps, e ≠ .place x ps) (n : Nat) (ρ : Env) (st : St) :
    evalOpnd P (n + 1) ρ st e = (eval P n ρ st e).bind fun v ρ1 st1 =>
      if v.toks = [] then .ok (v, none) ρ1 st1 else stuckL "an obligation passed to a builtin" := by
  cases e <;> first | rfl | exact absurd rfl (h _ _)

theorem evalSteps_nil (n : Nat) (ρ : Env) (st : St) :
    evalSteps P n ρ st [] = .err .timeout ∨ evalSteps P n ρ st [] = .ok [] ρ st := by
  cases n <;> simp [evalSteps]

theorem resolve_tenon {h m : String} {d : FnDecl} (hd : P.fns (h ++ "." ++ m) = some d) :
    resolve P h m = .tenon d := by simp [resolve, hd]

theorem resolve_prim {h m : String} {pf : List Val → Nat → PrimRes} (hd : P.fns (h ++ "." ++ m) = none)
    (hp : P.prim (h ++ "." ++ m) = some pf) : resolve P h m = .prim pf := by simp [resolve, hd, hp]

theorem kindL_copy {ts : List Ty} (h : kindL P ts = .copy) : ∀ t ∈ ts, t.copyable P := fun t ht =>
  Kind.le_copy (h ▸ kindL_le P ht)

mutual
theorem PatTy.copyable_binds (hA : AdtsOk P) : ∀ {p : Pat} {t : Ty} {bs : List (String × Ty)}, PatTy P p t bs →
    t.copyable P → ∀ b ∈ bs, b.2.copyable P
  | _, _, _, .wild _, _ => by simp
  | _, _, _, .bind, hc => by intro b hb; simp at hb; subst hb; exact hc
  | _, _, _, .lit, _ => by simp
  | _, _, _, .tup hps, hc => PatsTy.copyable_binds hA hps (kindL_copy hc)
  | _, _, _, @PatTy.con _ c ps s args d tag ts bs hd _ hvar ha hps, hc => by
    refine PatsTy.copyable_binds hA hps ?_
    intro u hu
    obtain ⟨ft, hft, rfl⟩ := mem_substL hu
    have hb := (hA s d hd).2.2 args ha _ (List.mem_of_getElem? hvar) ft hft
    have : Kind.join d.kind (kindL P args) = .copy := by simpa [Ty.copyable, Ty.kind, hd, Option.elim] using hc
    rw [this] at hb; exact Kind.le_copy hb
  | _, _, _, .alt halt, hc => AltTy.copyable_binds hA halt hc

theorem PatsTy.copyable_binds (hA : AdtsOk P) : ∀ {ps : List Pat} {ts : List Ty} {bs : List (String × Ty)},
    PatsTy P ps ts bs → (∀ t ∈ ts, t.copyable P) → ∀ b ∈ bs, b.2.copyable P
  | _, _, _, .nil, _ => by simp
  | _, _, _, .cons hp hps, hc => by
    intro b hb
    rcases List.mem_append.1 hb with hb | hb
    · exact PatTy.copyable_binds hA hp (hc _ (by simp)) b hb
    · exact PatsTy.copyable_binds hA hps (fun t ht => hc t (by simp [ht])) b hb

theorem AltTy.copyable_binds (hA : AdtsOk P) : ∀ {ps : List Pat} {t : Ty} {bs : List (String × Ty)},
    AltTy P ps t bs → t.copyable P → ∀ b ∈ bs, b.2.copyable P
  | _, _, _, .one hp, hc => PatTy.copyable_binds hA hp hc
  | _, _, _, .cons hp _, hc => PatTy.copyable_binds hA hp hc
end

theorem bindCtx_length (bs : List (String × Ty)) : (bindCtx bs).length = bs.length := by simp [bindCtx]

theorem noLinear_bindCtx_of_copyable {bs : List (String × Ty)} (h : ∀ b ∈ bs, b.2.copyable P) :
    Ctx.noLinear P (bindCtx bs) := by
  intro e he _ hl
  obtain ⟨b, hb, rfl⟩ := List.mem_map.1 he
  have := h b hb
  simp only [Ty.copyable] at this; simp only [Ty.linear] at hl; rw [this] at hl; cases hl

end

end Tenon
