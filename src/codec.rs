// Strict decoder for the derived codec (interpreter side). The C side is
// generated in emit_c.rs (`*_dec` functions) and follows the same algorithm,
// so both report the same failure offset.
//
// A value is accepted only in its canonical form: scalars must re-encode to
// exactly the consumed text, separators are exactly ", " and ": ", struct
// fields appear in declaration order, and map keys are distinct.

use crate::check::Checked;
use crate::types::Ty;
use crate::value::*;
use std::rc::Rc;

struct Dec<'a> {
    s: &'a [u8],
    pos: usize,
    err: Option<usize>,
    c: &'a Checked,
    names: &'a Names<'a>,
}

pub fn decode(c: &Checked, names: &Names, t: &Ty, text: &str) -> Result<V, String> {
    let mut d = Dec { s: text.as_bytes(), pos: 0, err: None, c, names };
    match d.value(t) {
        Some(v) if d.pos == d.s.len() => Ok(v),
        Some(_) => Err(format!("cannot decode {} at byte {}", t, d.pos)),
        None => Err(format!("cannot decode {} at byte {}", t, d.err.unwrap_or(d.pos))),
    }
}

impl<'a> Dec<'a> {
    fn fail<T>(&mut self, at: usize) -> Option<T> {
        if self.err.is_none() {
            self.err = Some(at);
        }
        None
    }
    fn lit(&mut self, l: &str) -> bool {
        if self.s[self.pos..].starts_with(l.as_bytes()) {
            self.pos += l.len();
            true
        } else {
            false
        }
    }
    fn expect(&mut self, l: &str) -> Option<()> {
        if self.lit(l) { Some(()) } else { self.fail(self.pos) }
    }
    fn run(&mut self, ok: impl Fn(u8) -> bool) -> &'a str {
        let st = self.pos;
        while self.pos < self.s.len() && ok(self.s[self.pos]) {
            self.pos += 1;
        }
        std::str::from_utf8(&self.s[st..self.pos]).unwrap_or("")
    }
    fn canonical(&mut self, v: V, text: &str, start: usize) -> Option<V> {
        let mut out = String::new();
        show(&v, false, self.names, &mut out);
        if out == text { Some(v) } else { self.fail(start) }
    }

    fn value(&mut self, t: &Ty) -> Option<V> {
        let start = self.pos;
        match t {
            Ty::Con(n, a) => match n.as_str() {
                "Int" => {
                    let text = self.run(|c| c == b'-' || c.is_ascii_digit());
                    match crate::interp::parse_int(text) {
                        Some(i) => self.canonical(V::Int(i), text, start),
                        None => self.fail(start),
                    }
                }
                "Float" => {
                    let text = self.run(|c| c == b'-' || c == b'+' || c == b'.' || c.is_ascii_alphanumeric());
                    match crate::interp::parse_float(text) {
                        Some(f) => self.canonical(V::Float(f), text, start),
                        None => self.fail(start),
                    }
                }
                "Bool" => {
                    if self.lit("true") {
                        Some(V::Bool(true))
                    } else if self.lit("false") {
                        Some(V::Bool(false))
                    } else {
                        self.fail(start)
                    }
                }
                "Unit" => self.expect("()").map(|_| V::Unit),
                "Str" => self.string(),
                "List" => {
                    self.expect("[")?;
                    let mut xs = Vec::new();
                    if !self.lit("]") {
                        loop {
                            xs.push(self.value(&a[0])?);
                            if self.lit(", ") {
                                continue;
                            }
                            self.expect("]")?;
                            break;
                        }
                    }
                    Some(V::List(Rc::new(xs)))
                }
                "Map" => {
                    let mut m = MapV::default();
                    if self.lit("[:]") {
                        return Some(V::Map(Rc::new(m)));
                    }
                    self.expect("[")?;
                    loop {
                        let ks = self.pos;
                        let k = self.value(&a[0])?;
                        if m.get(&k).is_some() {
                            return self.fail(ks);
                        }
                        self.expect(": ")?;
                        let v = self.value(&a[1])?;
                        m.insert(k, v);
                        if self.lit(", ") {
                            continue;
                        }
                        self.expect("]")?;
                        break;
                    }
                    Some(V::Map(Rc::new(m)))
                }
                _ => self.user(t, n),
            },
            Ty::Tuple(ts) => {
                self.expect("(")?;
                let mut xs = Vec::new();
                for (i, t) in ts.iter().enumerate() {
                    if i > 0 {
                        self.expect(", ")?;
                    }
                    xs.push(self.value(t)?);
                }
                self.expect(")")?;
                Some(V::Tuple(Rc::new(xs)))
            }
            _ => self.fail(start),
        }
    }

    fn user(&mut self, t: &Ty, n: &str) -> Option<V> {
        let disp = crate::interp::display(n);
        if let Some(fs) = self.c.struct_fields(t) {
            let si = self.c.struct_idx(n).unwrap() as u32;
            self.expect(disp)?;
            if fs.is_empty() {
                self.expect(" {}")?;
                return Some(V::Struct(si, Rc::new(vec![])));
            }
            self.expect(" { ")?;
            let mut vals = Vec::new();
            for (i, (f, ft)) in fs.iter().enumerate() {
                if i > 0 {
                    self.expect(", ")?;
                }
                self.expect(f)?;
                self.expect(": ")?;
                vals.push(self.value(ft)?);
            }
            self.expect(" }")?;
            return Some(V::Struct(si, Rc::new(vals)));
        }
        let vs = self.c.enum_variants(t)?;
        let ei = self.c.enum_idx(n).unwrap() as u32;
        let start = self.pos;
        let name = self.run(|c| c.is_ascii_alphanumeric() || c == b'_');
        let Some(vi) = vs.iter().position(|(v, _)| v == name) else { return self.fail(start) };
        let mut payload = Vec::new();
        if !vs[vi].1.is_empty() {
            self.expect("(")?;
            for (i, ft) in vs[vi].1.iter().enumerate() {
                if i > 0 {
                    self.expect(", ")?;
                }
                payload.push(self.value(ft)?);
            }
            self.expect(")")?;
        }
        Some(V::Enum(ei, vi as u32, Rc::new(payload)))
    }

    fn string(&mut self) -> Option<V> {
        let start = self.pos;
        self.expect("\"")?;
        let mut out: Vec<u8> = Vec::new();
        loop {
            let Some(&c) = self.s.get(self.pos) else { return self.fail(self.pos) };
            self.pos += 1;
            match c {
                b'"' => break,
                b'\\' => {
                    let Some(&e) = self.s.get(self.pos) else { return self.fail(self.pos) };
                    self.pos += 1;
                    match e {
                        b'"' => out.push(b'"'),
                        b'\\' => out.push(b'\\'),
                        b'n' => out.push(b'\n'),
                        b't' => out.push(b'\t'),
                        b'r' => out.push(b'\r'),
                        b'u' => {
                            self.expect("{")?;
                            let h = self.run(|c| c.is_ascii_hexdigit());
                            let Ok(v) = u8::from_str_radix(h, 16) else { return self.fail(start) };
                            self.expect("}")?;
                            out.push(v);
                        }
                        _ => return self.fail(start),
                    }
                }
                _ => out.push(c),
            }
        }
        let text = std::str::from_utf8(&self.s[start..self.pos]).unwrap_or("");
        let Ok(st) = String::from_utf8(out) else { return self.fail(start) };
        self.canonical(V::Str(st.into()), text, start)
    }
}
