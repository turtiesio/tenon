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
