// Semantic types, substitution and unification.

use std::collections::HashMap;
use std::fmt;

#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum Ty {
    Con(String, Vec<Ty>), // Int, Str, List[T], user structs/enums, capabilities ...
    Tuple(Vec<Ty>),
    Fn(Vec<Ty>, Box<Ty>),
    Param(String),
    Var(u32),
}

// Opaque types implemented by the runtime: (name, arity, is_capability).
pub const BUILTIN_TYPES: &[(&str, usize, bool)] = &[
    ("Int", 0, false),
    ("Float", 0, false),
    ("Bool", 0, false),
    ("Str", 0, false),
    ("Unit", 0, false),
    ("List", 1, false),
    ("Map", 2, false),
    ("Console", 0, true),
    ("Fs", 0, true),
    ("Clock", 0, true),
    ("Net", 0, true),
    ("Listener", 0, true),
    ("Conn", 0, true),
];

// Builtin handles that own an OS resource: never copied; dropping one closes it.
pub fn is_unique_builtin(name: &str) -> bool {
    name == "Listener" || name == "Conn"
}

pub fn is_capability(name: &str) -> bool {
    BUILTIN_TYPES.iter().any(|(n, _, c)| *n == name && *c)
}

impl Ty {
    pub fn con(n: &str) -> Ty {
        Ty::Con(n.to_string(), vec![])
    }
    pub fn int() -> Ty {
        Ty::con("Int")
    }
    pub fn bool() -> Ty {
        Ty::con("Bool")
    }
    pub fn str() -> Ty {
        Ty::con("Str")
    }
    pub fn unit() -> Ty {
        Ty::con("Unit")
    }
    pub fn float() -> Ty {
        Ty::con("Float")
    }
    pub fn list(t: Ty) -> Ty {
        Ty::Con("List".into(), vec![t])
    }
    pub fn is(&self, n: &str) -> bool {
        matches!(self, Ty::Con(m, _) if m == n)
    }
    pub fn args(&self) -> &[Ty] {
        match self {
            Ty::Con(_, a) => a,
            _ => &[],
        }
    }
    pub fn subst(&self, m: &HashMap<String, Ty>) -> Ty {
        match self {
            Ty::Param(p) => m.get(p).cloned().unwrap_or_else(|| self.clone()),
            Ty::Con(n, a) => Ty::Con(n.clone(), a.iter().map(|t| t.subst(m)).collect()),
            Ty::Tuple(a) => Ty::Tuple(a.iter().map(|t| t.subst(m)).collect()),
            Ty::Fn(a, r) => Ty::Fn(a.iter().map(|t| t.subst(m)).collect(), Box::new(r.subst(m))),
            Ty::Var(_) => self.clone(),
        }
    }
    pub fn any(&self, f: &dyn Fn(&Ty) -> bool) -> bool {
        if f(self) {
            return true;
        }
        match self {
            Ty::Con(_, a) | Ty::Tuple(a) => a.iter().any(|t| t.any(f)),
            Ty::Fn(a, r) => a.iter().any(|t| t.any(f)) || r.any(f),
            _ => false,
        }
    }
}

impl fmt::Display for Ty {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        let list = |f: &mut fmt::Formatter, a: &[Ty]| -> fmt::Result {
            for (i, t) in a.iter().enumerate() {
                if i > 0 {
                    write!(f, ", ")?;
                }
                write!(f, "{}", t)?;
            }
            Ok(())
        };
        match self {
            Ty::Con(n, a) if a.is_empty() => write!(f, "{}", n),
            Ty::Con(n, a) => {
                write!(f, "{}[", n)?;
                list(f, a)?;
                write!(f, "]")
            }
            Ty::Tuple(a) => {
                write!(f, "(")?;
                list(f, a)?;
                write!(f, ")")
            }
            Ty::Fn(a, r) => {
                write!(f, "fn(")?;
                list(f, a)?;
                write!(f, ") -> {}", r)
            }
            Ty::Param(p) => write!(f, "{}", p),
            Ty::Var(_) => write!(f, "_"),
        }
    }
}

#[derive(Default, Clone)]
pub struct Subst {
    pub vars: Vec<Option<Ty>>,
}

impl Subst {
    pub fn fresh(&mut self) -> Ty {
        self.vars.push(None);
        Ty::Var(self.vars.len() as u32 - 1)
    }
    pub fn shallow(&self, t: &Ty) -> Ty {
        let mut t = t.clone();
        while let Ty::Var(v) = t {
            match &self.vars[v as usize] {
                Some(b) => t = b.clone(),
                None => break,
            }
        }
        t
    }
    pub fn resolve(&self, t: &Ty) -> Ty {
        match self.shallow(t) {
            Ty::Con(n, a) => Ty::Con(n, a.iter().map(|t| self.resolve(t)).collect()),
            Ty::Tuple(a) => Ty::Tuple(a.iter().map(|t| self.resolve(t)).collect()),
            Ty::Fn(a, r) => Ty::Fn(a.iter().map(|t| self.resolve(t)).collect(), Box::new(self.resolve(&r))),
            t => t,
        }
    }
    // Replace unresolved variables with Unit (only diverging expressions stay unknown).
    pub fn finish(&self, t: &Ty) -> Ty {
        match self.shallow(t) {
            Ty::Var(_) => Ty::unit(),
            Ty::Con(n, a) => Ty::Con(n, a.iter().map(|t| self.finish(t)).collect()),
            Ty::Tuple(a) => Ty::Tuple(a.iter().map(|t| self.finish(t)).collect()),
            Ty::Fn(a, r) => Ty::Fn(a.iter().map(|t| self.finish(t)).collect(), Box::new(self.finish(&r))),
            t => t,
        }
    }
    fn occurs(&self, v: u32, t: &Ty) -> bool {
        match self.shallow(t) {
            Ty::Var(w) => v == w,
            Ty::Con(_, a) | Ty::Tuple(a) => a.iter().any(|t| self.occurs(v, t)),
            Ty::Fn(a, r) => a.iter().any(|t| self.occurs(v, t)) || self.occurs(v, &r),
            Ty::Param(_) => false,
        }
    }
    pub fn unify(&mut self, a: &Ty, b: &Ty) -> bool {
        let a = self.shallow(a);
        let b = self.shallow(b);
        match (&a, &b) {
            (Ty::Var(x), Ty::Var(y)) if x == y => true,
            (Ty::Var(x), t) | (t, Ty::Var(x)) => {
                if self.occurs(*x, t) {
                    return false;
                }
                self.vars[*x as usize] = Some(t.clone());
                true
            }
            (Ty::Con(n, a1), Ty::Con(m, a2)) => {
                n == m && a1.len() == a2.len() && a1.iter().zip(a2).all(|(x, y)| self.unify(x, y))
            }
            (Ty::Tuple(a1), Ty::Tuple(a2)) => {
                a1.len() == a2.len() && a1.iter().zip(a2).all(|(x, y)| self.unify(x, y))
            }
            (Ty::Fn(a1, r1), Ty::Fn(a2, r2)) => {
                a1.len() == a2.len() && a1.iter().zip(a2).all(|(x, y)| self.unify(x, y)) && self.unify(r1, r2)
            }
            (Ty::Param(p), Ty::Param(q)) => p == q,
            _ => false,
        }
    }
}
