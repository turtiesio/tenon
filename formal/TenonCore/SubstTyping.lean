/-
The substitution lemma for the typing judgement (Subst.lean has the
ingredients) and its corollary: a generic function checked once, at its own
type parameters, is well typed at every instance.
-/
import TenonCore.Subst

namespace Tenon

section
variable {P : Prog} {prim : PrimSig} {σ : List Ty}

/-- The bindings of a pattern with their types substituted. -/
def bindsSubst (σ : List Ty) (bs : List (String × Ty)) : List (String × Ty) := bs.map fun b => (b.1, b.2.subst σ)

theorem scoped_fn (hsc : ProgScoped P) {f : String} {d : FnDecl} (hd : P.fns f = some d) {σ' : List Ty}
    (hσ : σ'.length = d.tparams) : (∀ t ∈ d.ptys, t.Scoped σ'.length) ∧ d.ret.Scoped σ'.length := by
  rw [hσ]; exact hsc.1 f d hd

theorem scoped_adt (hsc : ProgScoped P) {s : String} {d : AdtDecl} (hd : P.adts s = some d) {v : String × List Ty}
    (hv : v ∈ d.variants) {args : List Ty} (ha : args.length = d.tparams) : ScopedL args.length v.2 := by
  rw [ha]; exact ScopedL.of_mem (hsc.2 s d hd v hv)

theorem fn_ty_subst {d : FnDecl} {σ' : List Ty} (h : (∀ t ∈ d.ptys, t.Scoped σ'.length) ∧ d.ret.Scoped σ'.length) :
    substL σ (substL σ' d.ptys) = substL (substL σ σ') d.ptys ∧ (d.ret.subst σ').subst σ = d.ret.subst (substL σ σ') :=
  ⟨substL_comp σ _ (ScopedL.of_mem h.1), Ty.subst_comp σ _ h.2⟩

mutual
theorem PatTy.subst (hsc : ProgScoped P) : ∀ {p : Pat} {t : Ty} {bs : List (String × Ty)}, PatTy P p t bs →
    PatTy P p (t.subst σ) (bindsSubst σ bs)
  | _, _, _, .wild hl => .wild (Ty.nonlinear_subst hl)
  | _, _, _, .bind => .bind
  | _, _, _, @PatTy.lit _ l => by rw [Lit.ty_subst]; exact .lit
  | _, _, _, .tup hps => .tup (PatsTy.subst hsc hps)
  | _, _, _, @PatTy.con _ c ps s args d tag ts bs hd hs hvar ha hps => by
    have h := PatsTy.subst hsc hps
    rw [substL_comp σ ts (scoped_adt hsc hd (List.mem_of_getElem? hvar) ha)] at h
    exact .con hd hs hvar (by rw [substL_length]; exact ha) h
  | _, _, _, .alt halt => .alt (AltTy.subst hsc halt)
theorem PatsTy.subst (hsc : ProgScoped P) : ∀ {ps : List Pat} {ts : List Ty} {bs : List (String × Ty)},
    PatsTy P ps ts bs → PatsTy P ps (substL σ ts) (bindsSubst σ bs)
  | _, _, _, .nil => .nil
  | _, _, _, .cons hp hps => by
    have := PatsTy.cons (PatTy.subst hsc hp) (PatsTy.subst hsc hps)
    simpa [bindsSubst, substL] using this
theorem AltTy.subst (hsc : ProgScoped P) : ∀ {ps : List Pat} {t : Ty} {bs : List (String × Ty)},
    AltTy P ps t bs → AltTy P ps (t.subst σ) (bindsSubst σ bs)
  | _, _, _, .one hp => .one (PatTy.subst hsc hp)
  | _, _, _, .cons hp halt => .cons (PatTy.subst hsc hp) (AltTy.subst hsc halt)
end

theorem bindCtx_bindsSubst (bs : List (String × Ty)) : Ctx.subst σ (bindCtx bs) = bindCtx (bindsSubst σ bs) :=
  bindCtx_subst bs

theorem bindsSubst_length (bs : List (String × Ty)) : (bindsSubst σ bs).length = bs.length := by simp [bindsSubst]

theorem scoped_field (hsc : ProgScoped P) {s : String} {d : AdtDecl} (hd : P.adts s = some d) {i : Nat} {ft : Ty}
    (hft : (d.variants.head?.map (·.2)).bind (·[i]?) = some ft) {args : List Ty} (ha : args.length = d.tparams) :
    ft.Scoped args.length := by
  cases hv : d.variants with
  | nil => rw [hv] at hft; simp at hft
  | cons v vs =>
    rw [hv] at hft; simp only [List.head?_cons, Option.map_some, Option.bind_some] at hft
    rw [ha]; exact hsc.2 s d hd v (by simp [hv]) ft (List.mem_of_getElem? hft)

theorem find_subst_avail {Γ : Ctx} {x : String} {en1 : Entry} (h : (Γ.subst σ).find x = some en1) :
    ∃ en0, Γ.find x = some en0 ∧ en1 = en0.subst σ := by
  rw [Ctx.find_subst] at h
  cases h' : Γ.find x with
  | none => rw [h'] at h; cases h
  | some en0 => rw [h'] at h; simp at h; exact ⟨en0, rfl, h.symm⟩

mutual
theorem HasTy.subst (hsc : ProgScoped P) (hps : PrimStable prim σ) : ∀ {Δ : Sig} {Γ : Ctx} {e : Expr} {t : Ty}
    {Γ' : Ctx}, HasTy P prim Δ Γ e t Γ' → ∀ {Δ' : Sig}, SigRel P σ Δ Δ' →
    HasTy P prim Δ' (Γ.subst σ) e (t.subst σ) (Γ'.subst σ)
  | _, _, _, _, _, .lit, _, _ => by rw [Lit.ty_subst]; exact .lit
  | _, _, _, _, _, .move hf ha, _, _ => by rw [Ctx.setAvail_subst]; exact .move (Ctx.find_subst' hf) ha
  | _, _, _, _, _, .copy hf ha hp hav hc, _, hr =>
    .copy (Ctx.find_subst' hf) ha (PathTy.subst hsc hps hp hr) hav.subst (Ty.copyable_subst hc)
  | _, _, _, _, _, .proj he hc hp, _, hr =>
    .proj (HasTy.subst hsc hps he hr) (Ty.copyable_subst hc) (PathTy.subst hsc hps hp hr)
  | _, _, _, _, _, .tup hl, _, hr => .tup (ListTy.subst hsc hps hl hr)
  | _, _, _, _, _, @HasTy.list _ _ _ _ es t _ hl hc, _, hr => by
    have h := ListTy.subst hsc hps hl hr
    rw [substL_map_const] at h
    exact .list h (Ty.copyable_subst hc)
  | _, _, _, _, _, @HasTy.con _ _ _ _ s tag es d name ts args _ hd hvar ha hl, _, hr => by
    have h := ListTy.subst hsc hps hl hr
    rw [substL_comp σ ts (scoped_adt hsc hd (List.mem_of_getElem? hvar) ha)] at h
    exact .con hd hvar (by rw [substL_length]; exact ha) h
  | _, _, _, _, _, @HasTy.lam _ _ _ _ ps body ts r Γb hl hb hfin, _, hr => by
    have h := HasTy.subst hsc hps hb (SigRel.fnSig none (ps.map (·, Mode.val)) r)
    rw [paramsCtx_subst] at h
    exact .lam (by rw [substL_length]; exact hl) h (FinFn.subst hfin)
  | _, _, _, _, _, @HasTy.fnref _ _ _ _ f d σ' hf hall hσ', _, hr => by
    have hc := fn_ty_subst (σ := σ) (scoped_fn hsc hf hσ')
    show HasTy P prim _ _ _ (.fn (substL σ (substL σ' d.ptys)) ((d.ret.subst σ').subst σ)) _
    rw [hc.1, hc.2]
    exact .fnref hf hall (by rw [substL_length]; exact hσ')
  | _, _, _, _, _, .callv hf hargs, _, hr => .callv (HasTy.subst hsc hps hf hr) (ArgsTy.subst hsc hps hargs hr)
  | _, _, _, _, _, @HasTy.call _ _ _ _ f d σ' args _ hf hσ' hargs, _, hr => by
    have hc := fn_ty_subst (σ := σ) (scoped_fn hsc hf hσ')
    have h := ArgsTy.subst hsc hps hargs hr
    rw [hc.1] at h; rw [hc.2]
    exact .call hf (by rw [substL_length]; exact hσ') h
  | _, _, _, _, _, @HasTy.mcallP _ _ _ Δ1 _ m x ps en t0 d σ' p0 m0 prest pt0 ptrest args Γ1 Γr Γ2 hf ha hp hav1 hvar hd
      hσ' hpar hpty hsub hval hnval htail hargs, _, hr => by
    obtain ⟨Δ1', htail', hr1⟩ := TailSig.subst htail hr
    have hsf := scoped_fn hsc hd hσ'
    rw [hpty] at hsf
    have hpt0 : pt0.Scoped σ'.length := hsf.1 pt0 (by simp)
    have hrest : ScopedL σ'.length ptrest := ScopedL.of_mem fun t ht => hsf.1 t (by simp [ht])
    obtain ⟨hhead, hvar'⟩ := Ty.head_subst (σ := σ) hvar
    rw [Ty.subst_comp σ d.ret hsf.2]
    have h := ArgsTy.subst hsc hps hargs hr1
    rw [substL_comp σ ptrest hrest] at h
    refine .mcallP (Ctx.find_subst' hf) ha (PathTy.subst hsc hps hp hr) hav1.subst hvar' (by rw [hhead]; exact hd)
      (by rw [substL_length]; exact hσ') hpar hpty (by rw [← Ty.subst_comp σ pt0 hpt0, hsub]) ?_ ?_ htail' h
    · intro hm
      rcases hval hm with ⟨h1, h2⟩ | ⟨h1, h2⟩
      · exact Or.inl ⟨h1, by rw [h2, Ctx.setAvail_subst]⟩
      · exact Or.inr ⟨by rw [h1], Ty.copyable_subst h2⟩
    · intro hm
      obtain ⟨h1, h2, h3⟩ := hnval hm
      exact ⟨by rw [h1], Ty.copyable_subst h2, h3.subst⟩
  | _, _, _, _, _, @HasTy.mcallV _ _ _ Δ1 _ m recv t0 d σ' p0 prest pt0 ptrest args Γ1 Γ2 hnp hrv hvar hd hσ' hpar
      hpty hsub htail hargs, _, hr => by
    obtain ⟨Δ1', htail', hr1⟩ := TailSig.subst htail hr
    have hsf := scoped_fn hsc hd hσ'
    rw [hpty] at hsf
    have hpt0 : pt0.Scoped σ'.length := hsf.1 pt0 (by simp)
    have hrest : ScopedL σ'.length ptrest := ScopedL.of_mem fun t ht => hsf.1 t (by simp [ht])
    obtain ⟨hhead, hvar'⟩ := Ty.head_subst (σ := σ) hvar
    rw [Ty.subst_comp σ d.ret hsf.2]
    have h := ArgsTy.subst hsc hps hargs hr1
    rw [substL_comp σ ptrest hrest] at h
    exact .mcallV hnp (HasTy.subst hsc hps hrv hr) hvar' (by rw [hhead]; exact hd) (by rw [substL_length]; exact hσ')
      hpar hpty (by rw [← Ty.subst_comp σ pt0 hpt0, hsub]) htail' h
  | _, _, _, _, _, @HasTy.mprimP _ _ _ _ m x ps en t0 ts t args Γ1 Γ2 hf ha hp hav1 hvar hd hpr hops hav hc, _, hr => by
    obtain ⟨hhead, hvar'⟩ := Ty.head_subst (σ := σ) hvar
    exact .mprimP (Ctx.find_subst' hf) ha (PathTy.subst hsc hps hp hr) hav1.subst hvar' (by rw [hhead]; exact hd)
      (by rw [hhead]; exact hps _ _ _ hpr) (OpndsTy.subst hsc hps hops hr) hav.subst (Ty.copyable_subst hc)
  | _, _, _, _, _, @HasTy.mprimV _ _ _ _ m recv t0 ts t args Γ1 Γ2 hnp hrv hc0 hvar hd hpr hops hc, _, hr => by
    obtain ⟨hhead, hvar'⟩ := Ty.head_subst (σ := σ) hvar
    exact .mprimV hnp (HasTy.subst hsc hps hrv hr) (Ty.copyable_subst hc0) hvar' (by rw [hhead]; exact hd)
      (by rw [hhead]; exact hps _ _ _ hpr) (OpndsTy.subst hsc hps hops hr) (Ty.copyable_subst hc)
  | _, _, _, _, _, .prim hp hops hc, _, hr =>
    .prim (hps _ _ _ hp) (OpndsTy.subst hsc hps hops hr) (Ty.copyable_subst hc)
  | _, _, _, _, _, .letE he hb ha, _, hr =>
    .letE (HasTy.subst hsc hps he hr) (HasTy.subst hsc hps hb hr) (fun h => Ty.nonlinear_subst (ha h))
  | _, _, _, _, _, @HasTy.assign _ _ _ _ x e en Γ1 hf hm he hl, _, hr => by
    rw [Ctx.setAvail_subst]
    refine .assign (Ctx.find_subst' hf) hm (HasTy.subst hsc hps he hr) ?_
    intro en1 h1 ha1
    obtain ⟨en0, h0, rfl⟩ := find_subst_avail h1
    exact Ty.nonlinear_subst (hl en0 h0 ha1)
  | _, _, _, _, _, .assignPart hf hm ha hp he hav hc, _, hr =>
    .assignPart (Ctx.find_subst' hf) hm ha (PathTy.subst hsc hps hp hr) (HasTy.subst hsc hps he hr) hav.subst
      (Ty.copyable_subst hc)
  | _, _, _, _, _, .seqE h1 hl h2, _, hr =>
    .seqE (HasTy.subst hsc hps h1 hr) (Ty.nonlinear_subst hl) (HasTy.subst hsc hps h2 hr)
  | _, _, _, _, _, .ite hc ha hb, _, hr =>
    .ite (HasTy.subst hsc hps hc hr) (HasTy.subst hsc hps ha hr) (HasTy.subst hsc hps hb hr)
  | _, _, _, _, _, .mtch he harms, _, hr => .mtch (HasTy.subst hsc hps he hr) (ArmsTy.subst hsc hps harms hr)
  | _, Γ, _, _, _, .while hc hb hl, _, hr =>
    .while (HasTy.subst hsc hps hc hr) (HasTy.subst hsc hps hb (hr.withLoop Γ)) (Ty.nonlinear_subst hl)
  | _, _, _, _, _, .ret hex he hrr, _, hr => by
    have h := HasTy.subst hsc hps he hr
    rw [← hr.1] at h
    exact .ret (by rw [hr.2.1]; exact hex) h (RetOk.subst hrr hr)
  | _, _, _, _, _, @HasTy.brk _ _ _ _ Γl _ _ hl hlo, _, hr =>
    .brk (Γl := Γl.subst σ) (by rw [hr.2.2.1, hl]; rfl) (LoopOk.subst hlo)
  | _, _, _, _, _, @HasTy.cont _ _ _ _ Γl _ _ hl hlo, _, hr =>
    .cont (Γl := Γl.subst σ) (by rw [hr.2.2.1, hl]; rfl) (LoopOk.subst hlo)
  | _, _, _, _, _, @HasTy.tryOpt _ _ _ _ e t t' Γ1 hex he hret hrr, _, hr =>
    .tryOpt (t' := t'.subst σ) (by rw [hr.2.1]; exact hex) (HasTy.subst hsc hps he hr) (by rw [hr.1, hret]; rfl)
      (RetOk.subst hrr hr)
  | _, _, _, _, _, @HasTy.tryRes _ _ _ _ e t t' er Γ1 hex he hret hrr, _, hr =>
    .tryRes (t' := t'.subst σ) (by rw [hr.2.1]; exact hex) (HasTy.subst hsc hps he hr) (by rw [hr.1, hret]; rfl)
      (RetOk.subst hrr hr)

theorem ListTy.subst (hsc : ProgScoped P) (hps : PrimStable prim σ) : ∀ {Δ : Sig} {Γ : Ctx} {es : List Expr}
    {ts : List Ty} {Γ' : Ctx}, ListTy P prim Δ Γ es ts Γ' → ∀ {Δ' : Sig}, SigRel P σ Δ Δ' →
    ListTy P prim Δ' (Γ.subst σ) es (substL σ ts) (Γ'.subst σ)
  | _, _, _, _, _, .nil, _, _ => .nil
  | _, _, _, _, _, .cons he htail hl, _, hr => by
    obtain ⟨Δ1', ht', hr1⟩ := TailSig.subst htail hr
    exact .cons (HasTy.subst hsc hps he hr) ht' (ListTy.subst hsc hps hl hr1)

theorem ArgsTy.subst (hsc : ProgScoped P) (hps : PrimStable prim σ) : ∀ {Δ : Sig} {Γ : Ctx} {ms : List Mode}
    {es : List Expr} {ts : List Ty} {Γ' : Ctx}, ArgsTy P prim Δ Γ ms es ts Γ' → ∀ {Δ' : Sig}, SigRel P σ Δ Δ' →
    ArgsTy P prim Δ' (Γ.subst σ) ms es (substL σ ts) (Γ'.subst σ)
  | _, _, _, _, _, _, .nil, _, _ => .nil
  | _, _, _, _, _, _, .val he htail hl, _, hr => by
    obtain ⟨Δ1', ht', hr1⟩ := TailSig.subst htail hr
    exact .val (HasTy.subst hsc hps he hr) ht' (ArgsTy.subst hsc hps hl hr1)
  | _, _, _, _, _, _, .byRef hm hf ha hmut hp hav1 hc hrest hav2, _, hr =>
    .byRef hm (Ctx.find_subst' hf) ha hmut (PathTy.subst hsc hps hp hr) hav1.subst (Ty.copyable_subst hc)
      (ArgsTy.subst hsc hps hrest hr) hav2.subst

theorem OpndsTy.subst (hsc : ProgScoped P) (hps : PrimStable prim σ) : ∀ {Δ : Sig} {Γ : Ctx} {es : List Expr}
    {ts : List Ty} {Γ' : Ctx}, OpndsTy P prim Δ Γ es ts Γ' → ∀ {Δ' : Sig}, SigRel P σ Δ Δ' →
    OpndsTy P prim Δ' (Γ.subst σ) es (substL σ ts) (Γ'.subst σ)
  | _, _, _, _, _, .nil, _, _ => .nil
  | _, _, _, _, _, .place hf ha hp hav1 hrest hav2, _, hr =>
    .place (Ctx.find_subst' hf) ha (PathTy.subst hsc hps hp hr) hav1.subst (OpndsTy.subst hsc hps hrest hr) hav2.subst
  | _, _, _, _, _, .val hnp he hc hrest, _, hr =>
    .val hnp (HasTy.subst hsc hps he hr) (Ty.copyable_subst hc) (OpndsTy.subst hsc hps hrest hr)

theorem PathTy.subst (hsc : ProgScoped P) (hps : PrimStable prim σ) : ∀ {Δ : Sig} {Γ : Ctx} {T : Ty}
    {ps : List PStep} {t : Ty} {Γ' : Ctx}, PathTy P prim Δ Γ T ps t Γ' → ∀ {Δ' : Sig}, SigRel P σ Δ Δ' →
    PathTy P prim Δ' (Γ.subst σ) (T.subst σ) ps (t.subst σ) (Γ'.subst σ)
  | _, _, _, _, _, _, .nil, _, _ => .nil
  | _, _, _, _, _, _, @PathTy.fld _ _ _ _ s args f ps d i ft t Γ' hd hs hi hft ha hp, _, hr => by
    have h := PathTy.subst hsc hps hp hr
    rw [Ty.subst_comp σ ft (scoped_field hsc hd hft ha)] at h
    exact .fld hd hs hi hft (by rw [substL_length]; exact ha) h
  | _, _, _, _, _, _, .tfld hti hp, _, hr => .tfld (substL_getElem? σ hti) (PathTy.subst hsc hps hp hr)
  | _, _, _, _, _, _, .idxList he hp, _, hr => .idxList (HasTy.subst hsc hps he hr) (PathTy.subst hsc hps hp hr)
  | _, _, _, _, _, _, .idxMap he hc hp, _, hr =>
    .idxMap (HasTy.subst hsc hps he hr) (Ty.copyable_subst hc) (PathTy.subst hsc hps hp hr)

theorem ArmsTy.subst (hsc : ProgScoped P) (hps : PrimStable prim σ) : ∀ {Δ : Sig} {Γ : Ctx} {t0 : Ty}
    {arms : List (Pat × Option Expr × Expr)} {t : Ty} {Γ' : Ctx}, ArmsTy P prim Δ Γ t0 arms t Γ' →
    ∀ {Δ' : Sig}, SigRel P σ Δ Δ' → ArmsTy P prim Δ' (Γ.subst σ) (t0.subst σ) arms (t.subst σ) (Γ'.subst σ)
  | _, _, _, _, _, _, .nil, _, _ => .nil
  | _, _, _, _, _, _, @ArmsTy.cons _ _ _ _ _ p g body arms _ bs _ Γb hpat hg hgt hbody hlb hnb hrest, _, hr => by
    refine .cons (bs := bindsSubst σ bs) (Γb := Γb.subst σ) (PatTy.subst hsc hpat)
      (fun h => Ty.copyable_subst (hg h)) ?_ ?_ (by rw [Ctx.subst_length, hlb, bindsSubst_length])
      (Ctx.noLinear_subst hnb) (ArmsTy.subst hsc hps hrest hr)
    · intro ge hge
      have h := HasTy.subst hsc hps (hgt ge hge) hr
      rwa [Ctx.subst_append, bindCtx_bindsSubst] at h
    · have h := HasTy.subst hsc hps hbody hr
      rwa [Ctx.subst_append, Ctx.subst_append, bindCtx_bindsSubst] at h
end

end

/-- **Checking a generic function once suffices**: a program whose functions
are well typed at their own type parameters (each checked once, generically),
with well-scoped declarations and parametric builtin signatures, is well typed
at every instance (`ProgOk`). -/
theorem generic_check_once (P : Prog) (prim : PrimSig) (hA : AdtsOk P) (hS : StdOk P) (hsc : ProgScoped P)
    (hpr : ∀ σ, PrimStable prim σ)
    (h : ∀ f d, P.fns f = some d → d.params.length = d.ptys.length ∧
      ∃ Γ', HasTy P prim (fnSig P d.owner d.params d.ret) (paramsCtx d.params d.ptys) d.body d.ret Γ' ∧
        FinFn P d.owner d.params Γ') :
    ProgOk P prim := by
  refine ⟨hA, hS, fun f d hd => ⟨(h f d hd).1, fun σ _ => ?_⟩⟩
  obtain ⟨-, Γ', hb, hfin⟩ := h f d hd
  refine ⟨Γ'.subst σ, ?_, FinFn.subst hfin⟩
  have := HasTy.subst hsc (hpr σ) hb (SigRel.fnSig (σ := σ) d.owner d.params d.ret)
  rwa [paramsCtx_subst] at this

end Tenon
