/-
Parametricity of the checker (formal/README.md, "Theorems"): the typing
judgement is stable under substituting type parameters, so checking a generic
function once, at its type parameters, types every instance (`ProgOk` asks for
every instance, as monomorphization does).

What makes it work: a type parameter counts as linear (Typing.lean,
`Ty.kind`), so substitution only makes a type less restrictive
(`kind_subst_le`), and every kind premise of the rules is preserved.
-/
import TenonCore.TypingPaths

namespace Tenon

/-! ## Scoping and composition -/

mutual
/-- The type's parameters are among the first `k`. -/
def Ty.Scoped (k : Nat) : Ty → Prop
  | .tup ts => ScopedL k ts
  | .list t => t.Scoped k
  | .map a b => a.Scoped k ∧ b.Scoped k
  | .adt _ as => ScopedL k as
  | .fn ps r => ScopedL k ps ∧ r.Scoped k
  | .var i => i < k
  | _ => True
def ScopedL (k : Nat) : List Ty → Prop
  | [] => True
  | t :: ts => t.Scoped k ∧ ScopedL k ts
end

theorem ScopedL.of_mem {k : Nat} : ∀ {ts : List Ty}, (∀ t ∈ ts, t.Scoped k) → ScopedL k ts
  | [], _ => trivial
  | t :: ts, h => ⟨h t (by simp), ScopedL.of_mem (fun u hu => h u (by simp [hu]))⟩

mutual
theorem Ty.subst_comp (σ : List Ty) {σ1 : List Ty} : ∀ (t : Ty), t.Scoped σ1.length →
    (t.subst σ1).subst σ = t.subst (substL σ σ1)
  | .tup ts, h => by simp only [Ty.subst]; rw [substL_comp σ ts h]
  | .list t, h => by simp only [Ty.subst]; rw [Ty.subst_comp σ t h]
  | .map a b, h => by simp only [Ty.subst]; rw [Ty.subst_comp σ a h.1, Ty.subst_comp σ b h.2]
  | .adt s as, h => by simp only [Ty.subst]; rw [substL_comp σ as h]
  | .fn ps r, h => by simp only [Ty.subst]; rw [substL_comp σ ps h.1, Ty.subst_comp σ r h.2]
  | .var i, h => by
    have h' : i < σ1.length := h
    simp only [Ty.subst, List.getElem?_eq_getElem h', Option.getD_some]
    rw [substL_getElem? σ (List.getElem?_eq_getElem h')]; rfl
  | .int, _ | .bool, _ | .str, _ | .unit, _ | .cap _, _ => rfl
theorem substL_comp (σ : List Ty) {σ1 : List Ty} : ∀ (ts : List Ty), ScopedL σ1.length ts →
    substL σ (substL σ1 ts) = substL (substL σ σ1) ts
  | [], _ => rfl
  | t :: ts, h => by simp only [substL]; rw [Ty.subst_comp σ t h.1, substL_comp σ ts h.2]
end

/-! ## Substitution makes kinds less restrictive -/

theorem Kind.join_mono {a a' b b' : Kind} (h1 : Kind.le a a') (h2 : Kind.le b b') :
    Kind.le (Kind.join a b) (Kind.join a' b') := by
  unfold Kind.le at *; rw [Kind.rank_join, Kind.rank_join]; omega

theorem Kind.le_linear (a : Kind) : Kind.le a .linear := by cases a <;> simp [Kind.le, Kind.rank]

section
variable (P : Prog) (σ : List Ty)

mutual
theorem Ty.kind_subst : ∀ (t : Ty), Kind.le ((t.subst σ).kind P) (t.kind P)
  | .tup ts => by simp only [Ty.subst, Ty.kind]; exact kindL_subst ts
  | .list t => by simp only [Ty.subst, Ty.kind]; exact Ty.kind_subst t
  | .map a b => by simp only [Ty.subst, Ty.kind]; exact Kind.join_mono (Ty.kind_subst a) (Ty.kind_subst b)
  | .adt s as => by simp only [Ty.subst, Ty.kind]; exact Kind.join_mono (Kind.le_refl _) (kindL_subst as)
  | .fn ps r => Kind.le_refl _
  | .var i => Kind.le_linear _
  | .int | .bool | .str | .unit | .cap _ => Kind.le_refl _
theorem kindL_subst : ∀ (ts : List Ty), Kind.le (kindL P (substL σ ts)) (kindL P ts)
  | [] => Kind.le_refl _
  | t :: ts => by simp only [substL, kindL]; exact Kind.join_mono (Ty.kind_subst t) (kindL_subst ts)
end

-- Substituting after an instantiation is no more restrictive than the instantiation.
mutual
theorem Ty.kind_subst_comp (σ1 : List Ty) : ∀ (t : Ty),
    Kind.le ((t.subst (substL σ σ1)).kind P) ((t.subst σ1).kind P)
  | .tup ts => by simp only [Ty.subst, Ty.kind]; exact kindL_subst_comp σ1 ts
  | .list t => by simp only [Ty.subst, Ty.kind]; exact Ty.kind_subst_comp σ1 t
  | .map a b => by
    simp only [Ty.subst, Ty.kind]; exact Kind.join_mono (Ty.kind_subst_comp σ1 a) (Ty.kind_subst_comp σ1 b)
  | .adt s as => by
    simp only [Ty.subst, Ty.kind]; exact Kind.join_mono (Kind.le_refl _) (kindL_subst_comp σ1 as)
  | .fn ps r => Kind.le_refl _
  | .var i => by
    simp only [Ty.subst]
    cases h : σ1[i]? with
    | none =>
      have : (substL σ σ1)[i]? = none := by
        rw [List.getElem?_eq_none_iff] at h ⊢; rw [substL_length]; exact h
      rw [this]; exact Kind.le_refl _
    | some u => rw [substL_getElem? σ h]; exact Ty.kind_subst P σ u
  | .int | .bool | .str | .unit | .cap _ => Kind.le_refl _
theorem kindL_subst_comp (σ1 : List Ty) : ∀ (ts : List Ty),
    Kind.le (kindL P (substL (substL σ σ1) ts)) (kindL P (substL σ1 ts))
  | [] => Kind.le_refl _
  | t :: ts => by
    simp only [substL, kindL]; exact Kind.join_mono (Ty.kind_subst_comp σ1 t) (kindL_subst_comp σ1 ts)
end

variable {P σ}

theorem Ty.copyable_subst {t : Ty} (h : t.copyable P) : (t.subst σ).copyable P :=
  Kind.le_copy (h ▸ Ty.kind_subst P σ t)

theorem Ty.nonlinear_subst {t : Ty} (h : ¬ t.linear P) : ¬ (t.subst σ).linear P := fun h' =>
  h (Kind.eq_linear (h' ▸ Ty.kind_subst P σ t))

theorem Ty.head_subst {t : Ty} (h : t.isVar = false) : (t.subst σ).head = t.head ∧ (t.subst σ).isVar = false := by
  cases t <;> simp_all [Ty.subst, Ty.head, Ty.isVar]

theorem Lit.ty_subst (l : Lit) : l.ty.subst σ = l.ty := by cases l <;> rfl

end

/-! ## Contexts under substitution -/

def Entry.subst (σ : List Ty) (e : Entry) : Entry := { e with ty := e.ty.subst σ }

def Ctx.subst (σ : List Ty) (Γ : Ctx) : Ctx := Γ.map (Entry.subst σ)

section
variable {P : Prog} {σ : List Ty}

theorem Ctx.subst_append (a b : Ctx) : Ctx.subst σ (a ++ b) = a.subst σ ++ b.subst σ := by simp [Ctx.subst]
theorem Ctx.subst_cons (e : Entry) (a : Ctx) : Ctx.subst σ (e :: a) = e.subst σ :: a.subst σ := rfl
theorem Ctx.subst_length (a : Ctx) : (a.subst σ).length = a.length := by simp [Ctx.subst]

theorem Ctx.find_subst : ∀ (Γ : Ctx) (x : String), (Γ.subst σ).find x = (Γ.find x).map (Entry.subst σ)
  | [], _ => rfl
  | e :: Γ, x => by
    rw [Ctx.subst_cons]; simp only [Ctx.find]
    by_cases hx : e.name = x
    · have : (e.subst σ).name = x := hx
      rw [if_pos this, if_pos hx]; rfl
    · have : ¬ (e.subst σ).name = x := hx
      rw [if_neg this, if_neg hx]; exact Ctx.find_subst Γ x

theorem Ctx.find_subst' {Γ : Ctx} {x : String} {e : Entry} (h : Γ.find x = some e) :
    (Γ.subst σ).find x = some (e.subst σ) := by rw [Ctx.find_subst, h]; rfl

theorem Ctx.setAvail_subst : ∀ (Γ : Ctx) (x : String) (a : Bool), Ctx.subst σ (Γ.setAvail x a) = (Γ.subst σ).setAvail x a
  | [], _, _ => rfl
  | e :: Γ, x, a => by
    simp only [Ctx.setAvail, Ctx.subst_cons, Entry.subst]
    split <;> simp_all [Ctx.subst_cons, Entry.subst, Ctx.setAvail_subst Γ x a]

theorem Ctx.Avail.subst {Γ : Ctx} {x : String} (h : Γ.Avail x) : (Γ.subst σ).Avail x := by
  obtain ⟨e, he, ha⟩ := h; exact ⟨_, Ctx.find_subst' he, ha⟩

theorem Ctx.AvailAt.subst {Γ : Ctx} {x : String} {T : Ty} (h : Γ.AvailAt x T) : (Γ.subst σ).AvailAt x (T.subst σ) := by
  obtain ⟨e, he, ha, ht⟩ := h; exact ⟨_, Ctx.find_subst' he, ha, by simp [Entry.subst, ht]⟩

theorem Ctx.noLinear_subst {Γ : Ctx} (h : Ctx.noLinear P Γ) : Ctx.noLinear P (Γ.subst σ) := by
  intro e he ha
  obtain ⟨e0, he0, rfl⟩ := List.mem_map.1 he
  exact Ty.nonlinear_subst (h e0 he0 ha)

theorem bindCtx_subst (bs : List (String × Ty)) :
    Ctx.subst σ (bindCtx bs) = bindCtx (bs.map fun b => (b.1, b.2.subst σ)) := by
  simp [bindCtx, Ctx.subst, Entry.subst]

theorem paramsCtx_subst : ∀ (ps : List (String × Mode)) (tys : List Ty),
    Ctx.subst σ (paramsCtx ps tys) = paramsCtx ps (substL σ tys)
  | p :: ps, t :: tys => by simp only [paramsCtx, substL, Ctx.subst_cons, Entry.subst]; rw [paramsCtx_subst ps tys]
  | [], _ => rfl
  | _ :: _, [] => rfl

theorem substL_map_const {α} (es : List α) (t : Ty) : substL σ (es.map fun _ => t) = es.map fun _ => t.subst σ := by
  induction es with
  | nil => rfl
  | cons e es ih => simp [substL, ih]

theorem FinFn.subst {owner : Option String} : ∀ {ps : List (String × Mode)} {Γ : Ctx},
    FinFn P owner ps Γ → FinFn P owner ps (Γ.subst σ)
  | [], [], _ => trivial
  | (p, m) :: ps, e :: Γ, ⟨he, h⟩ => by
    refine ⟨?_, FinFn.subst h⟩
    cases m with
    | val =>
      intro ha
      rcases he ha with hl | ⟨hp, o, d, args, ho, hty, hd, hk, hf⟩
      · exact Or.inl (Ty.nonlinear_subst hl)
      · refine Or.inr ⟨hp, o, d, substL σ args, ho, by simp [Entry.subst, hty, Ty.subst], hd, hk, ?_⟩
        intro v hv ft hft hl
        exact hf v hv ft hft (Kind.eq_linear (hl ▸ Ty.kind_subst_comp P σ args ft))
    | ref => exact he
    | «mut» => exact he
  | [], _ :: _, h | _ :: _, [], h => h.elim

/-! ## Signatures under substitution -/

/-- `Δ'` is `Δ` with its types substituted. -/
def SigRel (P : Prog) (σ : List Ty) (Δ Δ' : Sig) : Prop :=
  Δ'.ret = Δ.ret.subst σ ∧ Δ'.exitOk = Δ.exitOk ∧ Δ'.loop = Δ.loop.map (Ctx.subst σ) ∧ Δ'.fr = Δ.fr ∧
    ∀ Γ, Δ.fin Γ → Δ'.fin (Γ.subst σ)

theorem SigRel.noExit {Δ Δ' : Sig} (h : SigRel P σ Δ Δ') : SigRel P σ Δ.noExit Δ'.noExit :=
  ⟨h.1, rfl, rfl, h.2.2.2.1, h.2.2.2.2⟩

theorem SigRel.withLoop {Δ Δ' : Sig} (h : SigRel P σ Δ Δ') (Γ : Ctx) :
    SigRel P σ (Δ.withLoop Γ) (Δ'.withLoop (Γ.subst σ)) :=
  ⟨h.1, h.2.1, rfl, h.2.2.2.1, h.2.2.2.2⟩

theorem SigRel.fnSig (owner : Option String) (ps : List (String × Mode)) (r : Ty) :
    SigRel P σ (Tenon.fnSig P owner ps r) (Tenon.fnSig P owner ps (r.subst σ)) :=
  ⟨rfl, rfl, rfl, rfl, fun _ h => FinFn.subst h⟩

theorem TailSig.subst {Δ Δ1 Δ' : Sig} {t : Ty} (h : TailSig P Δ Δ1 t) (hr : SigRel P σ Δ Δ') :
    ∃ Δ1', TailSig P Δ' Δ1' (t.subst σ) ∧ SigRel P σ Δ1 Δ1' := by
  rcases h with ⟨rfl, hl⟩ | rfl
  · exact ⟨Δ', Or.inl ⟨rfl, Ty.nonlinear_subst hl⟩, hr⟩
  · exact ⟨Δ'.noExit, Or.inr rfl, hr.noExit⟩

theorem RetOk.subst {Δ Δ' : Sig} {Γ : Ctx} (h : RetOk P Δ Γ) (hr : SigRel P σ Δ Δ') : RetOk P Δ' (Γ.subst σ) := by
  unfold RetOk at *
  rw [Ctx.subst_length, hr.2.2.2.1]
  refine ⟨?_, ?_⟩
  · have := Ctx.noLinear_subst (σ := σ) h.1; simpa [Ctx.subst, List.map_take] using this
  · have := hr.2.2.2.2 _ h.2; simpa [Ctx.subst, List.map_drop] using this

theorem LoopOk.subst {Γl Γ : Ctx} (h : LoopOk P Γl Γ) : LoopOk P (Γl.subst σ) (Γ.subst σ) := by
  unfold LoopOk at *
  rw [Ctx.subst_length, Ctx.subst_length]
  refine ⟨?_, ?_⟩
  · have := Ctx.noLinear_subst (σ := σ) h.1; simpa [Ctx.subst, List.map_take] using this
  · simp only [Ctx.subst, ← List.map_drop]; rw [h.2]

end

/-! ## Programs whose types are well scoped -/

/-- Every declared type mentions only its own type parameters. -/
def ProgScoped (P : Prog) : Prop :=
  (∀ f d, P.fns f = some d → (∀ t ∈ d.ptys, t.Scoped d.tparams) ∧ d.ret.Scoped d.tparams) ∧
  (∀ s d, P.adts s = some d → ∀ v ∈ d.variants, ∀ ft ∈ v.2, ft.Scoped d.tparams)

/-- Builtin signatures are parametric. -/
def PrimStable (prim : PrimSig) (σ : List Ty) : Prop :=
  ∀ p ts t, prim p ts t → prim p (substL σ ts) (t.subst σ)

end Tenon
