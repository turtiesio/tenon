/-
Decision procedures for the side conditions of the typing judgement
(Typing.lean), each proved sound, for the checker (Check.lean): equality of
types and contexts, kinds, the end of a frame (`FinFn`), `RetOk`, `LoopOk`,
pattern typing, and the well-formedness of declarations (`AdtsOk`, `StdOk`).
-/
import TenonCore.TypeSafeRest

namespace Tenon

/-! ## Equality of types -/

mutual
def Ty.beq : Ty → Ty → Bool
  | .int, .int | .bool, .bool | .str, .str | .unit, .unit => true
  | .tup a, .tup b => tysBeq a b
  | .list a, .list b => a.beq b
  | .map a b, .map c d => a.beq c && b.beq d
  | .adt s a, .adt t b => s == t && tysBeq a b
  | .fn a r, .fn b q => tysBeq a b && r.beq q
  | .cap k, .cap k' => k == k'
  | .var i, .var j => i == j
  | _, _ => false
def tysBeq : List Ty → List Ty → Bool
  | [], [] => true
  | a :: as, b :: bs => a.beq b && tysBeq as bs
  | _, _ => false
end

mutual
theorem Ty.eq_of_beq : ∀ {a b : Ty}, a.beq b = true → a = b
  | .int, .int, _ | .bool, .bool, _ | .str, .str, _ | .unit, .unit, _ => rfl
  | .tup a, .tup b, h => by simp only [Ty.beq] at h; rw [tys_eq_of_beq h]
  | .list a, .list b, h => by simp only [Ty.beq] at h; rw [Ty.eq_of_beq h]
  | .map a b, .map c d, h => by
    simp only [Ty.beq, Bool.and_eq_true] at h; rw [Ty.eq_of_beq h.1, Ty.eq_of_beq h.2]
  | .adt s a, .adt t b, h => by
    simp only [Ty.beq, Bool.and_eq_true, beq_iff_eq] at h; rw [h.1, tys_eq_of_beq h.2]
  | .fn a r, .fn b q, h => by
    simp only [Ty.beq, Bool.and_eq_true] at h; rw [tys_eq_of_beq h.1, Ty.eq_of_beq h.2]
  | .cap k, .cap k', h => by simp only [Ty.beq, beq_iff_eq] at h; rw [h]
  | .var i, .var j, h => by simp only [Ty.beq, beq_iff_eq] at h; rw [h]
  | .int, .bool, h | .int, .str, h | .int, .unit, h | .int, .tup _, h | .int, .list _, h | .int, .map _ _, h
  | .int, .adt _ _, h | .int, .fn _ _, h | .int, .cap _, h | .int, .var _, h => by simp [Ty.beq] at h
  | .bool, .int, h | .bool, .str, h | .bool, .unit, h | .bool, .tup _, h | .bool, .list _, h | .bool, .map _ _, h
  | .bool, .adt _ _, h | .bool, .fn _ _, h | .bool, .cap _, h | .bool, .var _, h => by simp [Ty.beq] at h
  | .str, .int, h | .str, .bool, h | .str, .unit, h | .str, .tup _, h | .str, .list _, h | .str, .map _ _, h
  | .str, .adt _ _, h | .str, .fn _ _, h | .str, .cap _, h | .str, .var _, h => by simp [Ty.beq] at h
  | .unit, .int, h | .unit, .bool, h | .unit, .str, h | .unit, .tup _, h | .unit, .list _, h | .unit, .map _ _, h
  | .unit, .adt _ _, h | .unit, .fn _ _, h | .unit, .cap _, h | .unit, .var _, h => by simp [Ty.beq] at h
  | .tup _, .int, h | .tup _, .bool, h | .tup _, .str, h | .tup _, .unit, h | .tup _, .list _, h
  | .tup _, .map _ _, h | .tup _, .adt _ _, h | .tup _, .fn _ _, h | .tup _, .cap _, h | .tup _, .var _, h => by
    simp [Ty.beq] at h
  | .list _, .int, h | .list _, .bool, h | .list _, .str, h | .list _, .unit, h | .list _, .tup _, h
  | .list _, .map _ _, h | .list _, .adt _ _, h | .list _, .fn _ _, h | .list _, .cap _, h | .list _, .var _, h => by
    simp [Ty.beq] at h
  | .map _ _, .int, h | .map _ _, .bool, h | .map _ _, .str, h | .map _ _, .unit, h | .map _ _, .tup _, h
  | .map _ _, .list _, h | .map _ _, .adt _ _, h | .map _ _, .fn _ _, h | .map _ _, .cap _, h
  | .map _ _, .var _, h => by simp [Ty.beq] at h
  | .adt _ _, .int, h | .adt _ _, .bool, h | .adt _ _, .str, h | .adt _ _, .unit, h | .adt _ _, .tup _, h
  | .adt _ _, .list _, h | .adt _ _, .map _ _, h | .adt _ _, .fn _ _, h | .adt _ _, .cap _, h
  | .adt _ _, .var _, h => by simp [Ty.beq] at h
  | .fn _ _, .int, h | .fn _ _, .bool, h | .fn _ _, .str, h | .fn _ _, .unit, h | .fn _ _, .tup _, h
  | .fn _ _, .list _, h | .fn _ _, .map _ _, h | .fn _ _, .adt _ _, h | .fn _ _, .cap _, h
  | .fn _ _, .var _, h => by simp [Ty.beq] at h
  | .cap _, .int, h | .cap _, .bool, h | .cap _, .str, h | .cap _, .unit, h | .cap _, .tup _, h
  | .cap _, .list _, h | .cap _, .map _ _, h | .cap _, .adt _ _, h | .cap _, .fn _ _, h
  | .cap _, .var _, h => by simp [Ty.beq] at h
  | .var _, .int, h | .var _, .bool, h | .var _, .str, h | .var _, .unit, h | .var _, .tup _, h
  | .var _, .list _, h | .var _, .map _ _, h | .var _, .adt _ _, h | .var _, .fn _ _, h
  | .var _, .cap _, h => by simp [Ty.beq] at h
theorem tys_eq_of_beq : ∀ {a b : List Ty}, tysBeq a b = true → a = b
  | [], [], _ => rfl
  | a :: as, b :: bs, h => by
    simp only [tysBeq, Bool.and_eq_true] at h; rw [Ty.eq_of_beq h.1, tys_eq_of_beq h.2]
  | [], _ :: _, h | _ :: _, [], h => by simp [tysBeq] at h
end

mutual
theorem Ty.beq_refl : ∀ (a : Ty), a.beq a = true
  | .int | .bool | .str | .unit => rfl
  | .tup a => by simp only [Ty.beq]; exact tys_beq_refl a
  | .list a => by simp only [Ty.beq]; exact Ty.beq_refl a
  | .map a b => by simp only [Ty.beq, Bool.and_eq_true]; exact ⟨Ty.beq_refl a, Ty.beq_refl b⟩
  | .adt s a => by simp only [Ty.beq, Bool.and_eq_true, beq_self_eq_true, true_and]; exact tys_beq_refl a
  | .fn a r => by simp only [Ty.beq, Bool.and_eq_true]; exact ⟨tys_beq_refl a, Ty.beq_refl r⟩
  | .cap k => by simp [Ty.beq]
  | .var i => by simp [Ty.beq]
theorem tys_beq_refl : ∀ (a : List Ty), tysBeq a a = true
  | [] => rfl
  | a :: as => by simp only [tysBeq, Bool.and_eq_true]; exact ⟨Ty.beq_refl a, tys_beq_refl as⟩
end

instance : DecidableEq Ty := fun a b =>
  if h : a.beq b = true then isTrue (Ty.eq_of_beq h)
  else isFalse fun e => h (e ▸ Ty.beq_refl a)

def Entry.beq (a b : Entry) : Bool :=
  a.name == b.name && a.ty == b.ty && a.mutable == b.mutable && a.avail == b.avail

instance : DecidableEq Entry := fun a b =>
  if h : a.name = b.name ∧ a.ty = b.ty ∧ a.mutable = b.mutable ∧ a.avail = b.avail then
    isTrue (by cases a; cases b; simp_all)
  else isFalse fun e => h (by subst e; exact ⟨rfl, rfl, rfl, rfl⟩)

/-! ## Contexts and frames -/

variable (P : Prog)

def noLinearB (Γ : Ctx) : Bool := Γ.all fun e => !e.avail || !decide (e.ty.linear P)

theorem noLinearB_sound {Γ : Ctx} (h : noLinearB P Γ = true) : Ctx.noLinear P Γ := by
  intro e he ha hl
  have := List.all_eq_true.1 h e he
  simp [ha, hl] at this

def selfFinB (owner : Option String) (p : String) (t : Ty) : Bool :=
  match owner, t with
  | some o, .adt s args => p == "self" && s == o && (match P.adts o with
    | some d => d.kind != .copy && d.variants.all fun v => v.2.all fun ft => !decide ((ft.subst args).linear P)
    | none => false)
  | _, _ => false

theorem selfFinB_sound {owner : Option String} {p : String} {t : Ty} (h : selfFinB P owner p t = true) :
    SelfFin P owner p t := by
  unfold selfFinB at h
  split at h
  · rename_i o s args
    simp only [Bool.and_eq_true, beq_iff_eq] at h
    obtain ⟨⟨hp, hs⟩, h⟩ := h
    split at h
    · rename_i d hd
      simp only [Bool.and_eq_true, bne_iff_ne, ne_eq, List.all_eq_true, Bool.not_eq_true',
        decide_eq_false_iff_not] at h
      exact ⟨hp, o, d, args, rfl, by rw [hs], hd, h.1, fun v hv ft hft => h.2 v hv ft hft⟩
    · cases h
  · cases h

def finEntryB (owner : Option String) (p : String × Mode) (e : Entry) : Bool :=
  match p.2 with
  | .val => !e.avail || !decide (e.ty.linear P) || selfFinB P owner p.1 e.ty
  | _ => e.avail

def finFnB (owner : Option String) : List (String × Mode) → Ctx → Bool
  | [], [] => true
  | p :: ps, e :: Γ => finEntryB P owner p e && finFnB owner ps Γ
  | _, _ => false

theorem finFnB_sound (owner : Option String) :
    ∀ {ps : List (String × Mode)} {Γ : Ctx}, finFnB P owner ps Γ = true → FinFn P owner ps Γ
  | [], [], _ => trivial
  | (p, m) :: ps, e :: Γ, h => by
    simp only [finFnB, Bool.and_eq_true] at h
    refine ⟨?_, finFnB_sound owner h.2⟩
    have h1 := h.1
    unfold finEntryB at h1
    unfold FinEntry
    cases m with
    | val =>
      simp only [Bool.or_eq_true, Bool.not_eq_true', decide_eq_false_iff_not] at h1
      intro ha
      rcases h1 with (h1 | h1) | h1
      · simp [ha] at h1
      · exact Or.inl h1
      · exact Or.inr (selfFinB_sound P h1)
    | ref => exact h1
    | «mut» => exact h1
  | [], _ :: _, h | _ :: _, [], h => by simp [finFnB] at h

def retOkB (fr : Nat) (fb : Ctx → Bool) (Γ : Ctx) : Bool :=
  noLinearB P (Γ.take (Γ.length - fr)) && fb (Γ.drop (Γ.length - fr))

theorem retOkB_sound {Δ : Sig} {fb : Ctx → Bool} (hfb : ∀ Γ, fb Γ = true → Δ.fin Γ) {Γ : Ctx}
    (h : retOkB P Δ.fr fb Γ = true) : RetOk P Δ Γ := by
  simp only [retOkB, Bool.and_eq_true] at h
  exact ⟨noLinearB_sound P h.1, hfb _ h.2⟩

def loopOkB (Γl Γ : Ctx) : Bool :=
  noLinearB P (Γ.take (Γ.length - Γl.length)) && decide (Γ.drop (Γ.length - Γl.length) = Γl)

theorem loopOkB_sound {Γl Γ : Ctx} (h : loopOkB P Γl Γ = true) : LoopOk P Γl Γ := by
  simp only [loopOkB, Bool.and_eq_true, decide_eq_true_eq] at h
  exact ⟨noLinearB_sound P h.1, h.2⟩

/-! ## Patterns -/

/-- The index of a variant by name. -/
def variantIdx (c : String) : List (String × List Ty) → Option Nat
  | [] => none
  | v :: vs => if v.1 = c then some 0 else (variantIdx c vs).map (· + 1)

theorem variantIdx_spec {c : String} : ∀ {vs : List (String × List Ty)} {i : Nat}, variantIdx c vs = some i →
    ∃ ts, vs[i]? = some (c, ts)
  | [], _, h => by simp [variantIdx] at h
  | v :: vs, i, h => by
    simp only [variantIdx] at h
    split at h
    · rename_i hv; simp at h; subst h; exact ⟨v.2, by simp [← hv]⟩
    · cases hi : variantIdx c vs with
      | none => rw [hi] at h; simp at h
      | some j => rw [hi] at h; simp at h; subst h; obtain ⟨ts, h⟩ := variantIdx_spec hi; exact ⟨ts, by simpa using h⟩

/-- The names and types a pattern binds against a type (fuel bounds the depth). -/
def patTy : Nat → Pat → Ty → Option (List (String × Ty))
  | 0, _, _ => none
  | _ + 1, .wild, t => if t.linear P then none else some []
  | _ + 1, .bind x, t => some [(x, t)]
  | _ + 1, .lit l, t => if l.ty = t then some [] else none
  | n + 1, .tup ps, .tup ts => patsTy n ps ts
  | n + 1, .con c ps, .adt s args => match P.adts s with
    | some d => if d.isStruct = false ∧ args.length = d.tparams then
        match variantIdx c d.variants with
        | some i => match d.variants[i]? with
          | some (_, ts) => patsTy n ps (substL args ts)
          | none => none
        | none => none
      else none
    | none => none
  | n + 1, .alt ps, t => altTy n ps t
  | _ + 1, _, _ => none
where
  patsTy : Nat → List Pat → List Ty → Option (List (String × Ty))
    | 0, _, _ => none
    | _ + 1, [], [] => some []
    | n + 1, p :: ps, t :: ts => match patTy n p t, patsTy n ps ts with
      | some b, some bs => some (b ++ bs)
      | _, _ => none
    | _ + 1, _, _ => none
  altTy : Nat → List Pat → Ty → Option (List (String × Ty))
    | 0, _, _ => none
    | n + 1, [p], t => patTy n p t
    | n + 1, p :: ps, t => match patTy n p t, altTy n ps t with
      | some b, some bs => if b = bs then some b else none
      | _, _ => none
    | _ + 1, [], _ => none

instance : DecidableEq (String × Ty) := inferInstance

theorem patTy_sound : ∀ (n : Nat), (∀ {p t bs}, patTy P n p t = some bs → PatTy P p t bs) ∧
    (∀ {ps ts bs}, patTy.patsTy P n ps ts = some bs → PatsTy P ps ts bs) ∧
    (∀ {ps t bs}, patTy.altTy P n ps t = some bs → AltTy P ps t bs)
  | 0 => ⟨fun h => by simp [patTy] at h, fun h => by simp [patTy.patsTy] at h, fun h => by simp [patTy.altTy] at h⟩
  | n + 1 => by
    obtain ⟨ih1, ih2, ih3⟩ := patTy_sound n
    refine ⟨fun {p t bs} h => ?_, fun {ps ts bs} h => ?_, fun {ps t bs} h => ?_⟩
    · cases p with
      | wild => simp only [patTy] at h; split at h
                · cases h
                · simp at h; subst h; exact .wild (by assumption)
      | bind x => simp only [patTy] at h; simp at h; subst h; exact .bind
      | lit l => simp only [patTy] at h; split at h
                 · rename_i he; simp at h; subst h; subst he; exact .lit
                 · cases h
      | tup ps => cases t <;> simp only [patTy] at h <;> first | cases h | exact .tup (ih2 h)
      | con c ps =>
        cases t with
        | adt s args =>
          simp only [patTy] at h
          split at h
          · rename_i d hd
            split at h
            · rename_i hc
              split at h
              · rename_i i hi
                split at h
                · rename_i nm ts hv
                  obtain ⟨ts', hv'⟩ := variantIdx_spec hi
                  rw [hv] at hv'; simp only [Option.some.injEq, Prod.mk.injEq] at hv'; obtain ⟨rfl, rfl⟩ := hv'
                  exact .con hd hc.1 hv hc.2 (ih2 h)
                · cases h
              · cases h
            · cases h
          · cases h
        | _ => simp [patTy] at h
      | alt ps => simp only [patTy] at h; exact .alt (ih3 h)
    · cases ps with
      | nil => cases ts with
        | nil => simp [patTy.patsTy] at h; subst h; exact .nil
        | cons => simp [patTy.patsTy] at h
      | cons p ps => cases ts with
        | nil => simp [patTy.patsTy] at h
        | cons t ts =>
          simp only [patTy.patsTy] at h
          split at h
          · rename_i b bs' h1 h2; simp at h; subst h; exact .cons (ih1 h1) (ih2 h2)
          · cases h
    · cases ps with
      | nil => simp [patTy.altTy] at h
      | cons p ps =>
        cases ps with
        | nil => simp only [patTy.altTy] at h; exact .one (ih1 h)
        | cons q qs =>
          simp only [patTy.altTy] at h
          split at h
          · rename_i b bs' h1 h2
            split at h
            · rename_i he; simp at h; subst h; subst he; exact .cons (ih1 h1) (ih3 h2)
            · cases h
          · cases h

/-! ## Declarations -/

mutual
/-- A type's kind, counting a type parameter as copyable. -/
def Ty.kindNV : Ty → Kind
  | .tup ts => kindNVL ts
  | .list t => t.kindNV
  | .map k v => Kind.join k.kindNV v.kindNV
  | .adt s as => Kind.join ((P.adts s).elim .copy (·.kind)) (kindNVL as)
  | _ => .copy
def kindNVL : List Ty → Kind
  | [] => .copy
  | t :: ts => Kind.join t.kindNV (kindNVL ts)
end

mutual
/-- The type parameters a type mentions are below `n`. -/
def Ty.scoped (n : Nat) : Ty → Bool
  | .tup ts => scopedL n ts
  | .list t => t.scoped n
  | .map k v => k.scoped n && v.scoped n
  | .adt _ as => scopedL n as
  | .fn ps r => scopedL n ps && r.scoped n
  | .var i => decide (i < n)
  | _ => true
def scopedL (n : Nat) : List Ty → Bool
  | [] => true
  | t :: ts => t.scoped n && scopedL n ts
end

mutual
/-- Substituting arguments raises a kind at most to the arguments' join. -/
theorem kind_subst_nv : ∀ (t : Ty) (args : List Ty), t.scoped args.length = true →
    Kind.le ((t.subst args).kind P) (Kind.join (t.kindNV P) (kindL P args))
  | .tup ts, args, h => by simp only [Ty.subst, Ty.kind, Ty.kindNV, Ty.scoped] at *; exact kindL_subst_nv ts args h
  | .list t, args, h => by simp only [Ty.subst, Ty.kind, Ty.kindNV, Ty.scoped] at *; exact kind_subst_nv t args h
  | .map k v, args, h => by
    simp only [Ty.subst, Ty.kind, Ty.kindNV, Ty.scoped, Bool.and_eq_true] at *
    have h1 := kind_subst_nv k args h.1
    have h2 := kind_subst_nv v args h.2
    unfold Kind.le at *; simp only [Kind.rank_join] at *; omega
  | .adt s as, args, h => by
    simp only [Ty.subst, Ty.kind, Ty.kindNV, Ty.scoped] at *
    have h1 := kindL_subst_nv as args h
    unfold Kind.le at *; simp only [Kind.rank_join] at *; omega
  | .fn _ _, _, _ | .int, _, _ | .bool, _, _ | .str, _, _ | .unit, _, _ | .cap _, _, _ => by
    simp only [Ty.subst, Ty.kind, Ty.kindNV]; exact Kind.le_join_left _ _
  | .var i, args, h => by
    simp only [Ty.scoped, decide_eq_true_eq] at h
    simp only [Ty.subst, List.getElem?_eq_getElem h, Option.getD_some, Ty.kindNV]
    exact Kind.le_trans (kindL_le P (List.getElem_mem h)) (Kind.le_join_right _ _)
theorem kindL_subst_nv : ∀ (ts : List Ty) (args : List Ty), scopedL args.length ts = true →
    Kind.le (kindL P (substL args ts)) (Kind.join (kindNVL P ts) (kindL P args))
  | [], _, _ => by simp only [substL, kindL, kindNVL]; exact Kind.le_join_left _ _
  | t :: ts, args, h => by
    simp only [substL, kindL, kindNVL, scopedL, Bool.and_eq_true] at *
    have h1 := kind_subst_nv t args h.1
    have h2 := kindL_subst_nv ts args h.2
    unfold Kind.le at *; simp only [Kind.rank_join] at *; omega
end

/-- One declaration is well formed (`AdtsOk`), with a decidable bound on the fields' kinds. -/
def adtOkB (d : AdtDecl) : Bool :=
  (if d.isStruct then (match d.variants with
    | [(_, ts)] => d.fields.length == ts.length
    | _ => false) else decide ((d.variants.map (·.1)).Nodup)) &&
  d.variants.all fun v => v.2.all fun ft => ft.scoped d.tparams && decide ((ft.kindNV P).rank ≤ d.kind.rank)

theorem adtOkB_sound {s : String} {d : AdtDecl} (h : adtOkB P d = true) :
    (d.isStruct = true → ∃ nm ts, d.variants = [(nm, ts)] ∧ d.fields.length = ts.length) ∧
    (d.isStruct = false → (d.variants.map (·.1)).Nodup) ∧
    ∀ args : List Ty, args.length = d.tparams → ∀ v ∈ d.variants, ∀ ft ∈ v.2,
      Kind.le ((ft.subst args).kind P) (Kind.join d.kind (kindL P args)) := by
  simp only [adtOkB, Bool.and_eq_true, List.all_eq_true, decide_eq_true_eq] at h
  obtain ⟨h1, h2⟩ := h
  refine ⟨fun hs => ?_, fun hs => ?_, fun args ha v hv ft hft => ?_⟩
  · rw [hs] at h1; simp only [ite_true] at h1
    split at h1
    · rename_i nm ts hv; exact ⟨nm, ts, hv, by simpa using h1⟩
    · cases h1
  · rw [hs] at h1; simpa using h1
  · obtain ⟨hsc, hk⟩ := h2 v hv ft hft
    have := kind_subst_nv P ft args (by rw [ha]; exact hsc)
    unfold Kind.le at *; simp only [Kind.rank_join] at *; omega

/-- `AdtsOk` from a list of the program's declarations that covers `P.adts`. -/
theorem adtsOk_of_list (keys : List (String × AdtDecl)) (hk : ∀ s d, P.adts s = some d → (s, d) ∈ keys)
    (h : keys.all (fun sd => adtOkB P sd.2) = true) : AdtsOk P := by
  intro s d hd
  exact adtOkB_sound (s := s) P (List.all_eq_true.1 h (s, d) (hk s d hd))

def stdOkB : Bool :=
  (match P.adts "Option" with
   | some d => d.kind == .copy && d.isStruct == false && d.tparams == 1 &&
       decide (d.variants = [("Some", [.var 0]), ("None", [])])
   | none => false) &&
  (match P.adts "Result" with
   | some d => d.kind == .copy && d.isStruct == false && d.tparams == 2 &&
       decide (d.variants = [("Ok", [.var 0]), ("Err", [.var 1])])
   | none => false)

theorem stdOkB_sound (h : stdOkB P = true) : StdOk P := by
  simp only [stdOkB, Bool.and_eq_true] at h
  obtain ⟨h1, h2⟩ := h
  constructor
  · split at h1
    · rename_i d hd
      simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at h1
      exact ⟨d, hd, h1.1.1.1, by simpa using h1.1.1.2, h1.1.2, h1.2⟩
    · cases h1
  · split at h2
    · rename_i d hd
      simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq] at h2
      exact ⟨d, hd, h2.1.1.1, by simpa using h2.1.1.2, h2.1.2, h2.2⟩
    · cases h2

end Tenon
