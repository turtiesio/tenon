// Match exhaustiveness and reachability (usefulness algorithm, Maranget 2007).

use crate::ast::{Arm, Id, PatKind, Pattern};
use crate::check::Checked;
use crate::diag::{Diag, Span};
use crate::types::Ty;
use std::collections::HashMap;

#[derive(Clone, Debug)]
enum P {
    Wild,
    Ctor(usize, Vec<P>), // constructor index within the type
    Lit(String),         // Int/Str literal: an infinite domain
}

struct Cx<'a> {
    c: &'a Checked,
}

impl<'a> Cx<'a> {
    // Constructors of a type: Some(field types per ctor) if finite.
    fn ctors(&self, t: &Ty) -> Option<Vec<Vec<Ty>>> {
        match t {
            Ty::Con(n, _) if n == "Bool" => Some(vec![vec![], vec![]]),
            Ty::Tuple(ts) => Some(vec![ts.clone()]),
            Ty::Con(..) => self.c.enum_variants(t).map(|vs| vs.into_iter().map(|(_, f)| f).collect()),
            _ => None,
        }
    }
}

fn lower(p: &Pattern, res: &HashMap<Id, (usize, usize)>) -> Vec<P> {
    match &p.kind {
        PatKind::Wild | PatKind::Bind(_) => vec![P::Wild],
        PatKind::Int(i) => vec![P::Lit(i.to_string())],
        PatKind::Str(s) => vec![P::Lit(format!("{:?}", s))],
        PatKind::Bool(b) => vec![P::Ctor(if *b { 1 } else { 0 }, vec![])],
        PatKind::Tuple(ps) => product(ps, res).into_iter().map(|a| P::Ctor(0, a)).collect(),
        PatKind::Variant(_, _, ps) => {
            let (_, vi) = res[&p.id];
            product(ps, res).into_iter().map(|a| P::Ctor(vi, a)).collect()
        }
        PatKind::Or(alts) => alts.iter().flat_map(|a| lower(a, res)).collect(),
    }
}

// Expand or-patterns nested in sub-patterns into alternatives.
fn product(ps: &[Pattern], res: &HashMap<Id, (usize, usize)>) -> Vec<Vec<P>> {
    let mut acc: Vec<Vec<P>> = vec![vec![]];
    for p in ps {
        let alts = lower(p, res);
        let mut next = Vec::new();
        for a in &acc {
            for alt in &alts {
                let mut v = a.clone();
                v.push(alt.clone());
                next.push(v);
            }
        }
        acc = next;
    }
    acc
}

fn specialize(rows: &[Vec<P>], c: usize, arity: usize) -> Vec<Vec<P>> {
    let mut out = Vec::new();
    for r in rows {
        match &r[0] {
            P::Ctor(d, args) if *d == c => {
                let mut v = args.clone();
                v.extend_from_slice(&r[1..]);
                out.push(v);
            }
            P::Wild => {
                let mut v = vec![P::Wild; arity];
                v.extend_from_slice(&r[1..]);
                out.push(v);
            }
            _ => {}
        }
    }
    out
}

fn useful(cx: &Cx, rows: &[Vec<P>], v: &[P], tys: &[Ty]) -> bool {
    if v.is_empty() {
        return rows.is_empty();
    }
    let rest_tys = &tys[1..];
    match &v[0] {
        P::Ctor(c, args) => {
            let fts = cx.ctors(&tys[0]).map(|cs| cs[*c].clone()).unwrap_or_default();
            let rows2 = specialize(rows, *c, args.len());
            let mut v2 = args.clone();
            v2.extend_from_slice(&v[1..]);
            let mut t2 = fts;
            t2.extend_from_slice(rest_tys);
            useful(cx, &rows2, &v2, &t2)
        }
        P::Lit(l) => {
            let rows2: Vec<Vec<P>> = rows
                .iter()
                .filter(|r| matches!(&r[0], P::Wild) || matches!(&r[0], P::Lit(m) if m == l))
                .map(|r| r[1..].to_vec())
                .collect();
            useful(cx, &rows2, &v[1..], rest_tys)
        }
        P::Wild => {
            let used: Vec<usize> = rows
                .iter()
                .filter_map(|r| if let P::Ctor(c, _) = &r[0] { Some(*c) } else { None })
                .collect();
            if let Some(cs) = cx.ctors(&tys[0]) {
                if !cs.is_empty() && (0..cs.len()).all(|c| used.contains(&c)) {
                    return (0..cs.len()).any(|c| {
                        let rows2 = specialize(rows, c, cs[c].len());
                        let mut v2 = vec![P::Wild; cs[c].len()];
                        v2.extend_from_slice(&v[1..]);
                        let mut t2 = cs[c].clone();
                        t2.extend_from_slice(rest_tys);
                        useful(cx, &rows2, &v2, &t2)
                    });
                }
            }
            let rows2: Vec<Vec<P>> =
                rows.iter().filter(|r| matches!(r[0], P::Wild)).map(|r| r[1..].to_vec()).collect();
            useful(cx, &rows2, &v[1..], rest_tys)
        }
    }
}

pub fn check(
    c: &Checked,
    res: &HashMap<Id, (usize, usize)>,
    _resolve: &dyn Fn(&Ty) -> Ty,
    span: Span,
    st: &Ty,
    arms: &[Arm],
) -> Result<(), Diag> {
    let cx = Cx { c };
    let tys = vec![st.clone()];
    let mut rows: Vec<Vec<P>> = Vec::new();
    for a in arms {
        let alts = lower(&a.pat, res);
        let reachable = alts.iter().any(|p| useful(&cx, &rows, &[p.clone()], &tys));
        if !reachable {
            return Err(Diag::new(a.pat.span, "unreachable pattern: earlier arms already cover it"));
        }
        if a.guard.is_none() {
            for p in alts {
                rows.push(vec![p]);
            }
        }
    }
    if useful(&cx, &rows, &[P::Wild], &tys) {
        let mut missing = String::new();
        if let Some(vs) = c.enum_variants(st) {
            for (i, (n, fs)) in vs.iter().enumerate() {
                let probe = P::Ctor(i, vec![P::Wild; fs.len()]);
                if useful(&cx, &rows, &[probe], &tys) {
                    let args = if fs.is_empty() { String::new() } else { format!("({})", vec!["_"; fs.len()].join(", ")) };
                    missing = format!(": '{}{}' is not covered", n, args);
                    break;
                }
            }
        }
        return Err(Diag::new(span, &format!("match is not exhaustive{}; add the missing arm or '_ =>'", missing)));
    }
    Ok(())
}
