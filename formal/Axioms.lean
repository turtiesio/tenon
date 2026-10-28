/-
The axiom audit of ops/gates/formal_check.sh: every guarded theorem
(TenonCore/Theorems.lean) may depend only on Lean's standard axioms
(`propext`, `Classical.choice`, `Quot.sound`). Run: `lake env lean Axioms.lean`.
-/
import TenonCore

#print axioms Tenon.Theorems.within_narrows
#print axioms Tenon.Theorems.readOnly_narrows
#print axioms Tenon.Theorems.attenuation_trans
#print axioms Tenon.Theorems.capability_safety
#print axioms Tenon.Theorems.no_authority_escalation
#print axioms Tenon.Theorems.obligations_conserved
#print axioms Tenon.Theorems.obligations_exactly_once
#print axioms Tenon.Theorems.linear_discharged_exactly_once
#print axioms Tenon.Theorems.step_isolated
#print axioms Tenon.Theorems.run_isolated
#print axioms Tenon.Theorems.no_shared_cell
#print axioms Tenon.Theorems.unchecked_sharing_breaks_isolation
#print axioms Tenon.Theorems.type_soundness
#print axioms Tenon.Theorems.well_typed_never_stuck
#print axioms Tenon.Theorems.typing_subst
#print axioms Tenon.Theorems.generic_check_once
#print axioms Tenon.Theorems.coherent_unique_impl
#print axioms Tenon.Theorems.method_resolution
#print axioms Tenon.Theorems.bounded_call_resolves
#print axioms Tenon.Theorems.dyn_dispatch
#print axioms Tenon.Theorems.sort_unique
#print axioms Tenon.Theorems.sort_sorted_perm
#print axioms Tenon.Theorems.stable_sort_unique
#print axioms Tenon.Theorems.sort_stable_equiv
#print axioms Tenon.Theorems.maps_agree
#print axioms Tenon.Theorems.unlawful_eq_map_provenance
#print axioms Tenon.Theorems.user_impls_capability_safe
-- The hypotheses of type_soundness are satisfiable (TenonCore/TypeExamples.lean)
#print axioms Tenon.Examples.ex_never_stuck
-- Traits and coherence (TenonCore/Traits.lean)
#print axioms Tenon.Traits.impl_unique
#print axioms Tenon.Traits.resolve_impl
#print axioms Tenon.Traits.method_resolution
#print axioms Tenon.Traits.entails_sound
#print axioms Tenon.Traits.superOk_of_impls
#print axioms Tenon.Traits.super_entails
#print axioms Tenon.Traits.bounded_call_resolves
#print axioms Tenon.Traits.bounded_call_resolves_typed
#print axioms Tenon.Traits.dyn_dispatch
#print axioms Tenon.Traits.coherent_of_heads
-- The item-3 specification (TenonCore/TypeGaps.lean)
#print axioms Tenon.TypeGaps.eqLawful_of_ord
#print axioms Tenon.TypeGaps.isort_perm
#print axioms Tenon.TypeGaps.isort_sorted
#print axioms Tenon.TypeGaps.isort_idem
#print axioms Tenon.TypeGaps.sort_unique
#print axioms Tenon.TypeGaps.isort_congr
#print axioms Tenon.TypeGaps.isortM_perm
#print axioms Tenon.TypeGaps.mget_mset_self
#print axioms Tenon.TypeGaps.mget_mset_other
#print axioms Tenon.TypeGaps.mbuild_unique
#print axioms Tenon.TypeGaps.mbuild_prov
#print axioms Tenon.TypeGaps.mget_prov
#print axioms Tenon.TypeGaps.mbuild_length
#print axioms Tenon.TypeGaps.oget_oset_self
#print axioms Tenon.TypeGaps.oget_oset_other
#print axioms Tenon.TypeGaps.obuild_sorted_unique
#print axioms Tenon.TypeGaps.obuild_prov
#print axioms Tenon.TypeGaps.obuild_length
#print axioms Tenon.TypeGaps.omap_agrees
#print axioms Tenon.TypeGaps.hmap_agrees
#print axioms Tenon.TypeGaps.hbuild_unique
#print axioms Tenon.TypeGaps.hbuild_prov
#print axioms Tenon.TypeGaps.user_sort_perm
#print axioms Tenon.TypeGaps.user_impl_no_effects
#print axioms Tenon.TypeGaps.user_impls_capability_safe
#print axioms Tenon.TypeGaps.user_impls_obligations_conserved
#print axioms Tenon.TypeGaps.ord_bound_gives_eq
#print axioms Tenon.TypeGaps.hash_bound_gives_eq
#print axioms Tenon.Theorems.type_soundness_full
#print axioms Tenon.Theorems.check_sound
#print axioms Tenon.Theorems.checked_program_never_stuck
#print axioms Tenon.Theorems.overlap_check_sound
#print axioms Tenon.Theorems.orphan_rule_coherent
