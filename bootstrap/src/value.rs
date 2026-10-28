// Reference-interpreter values: derived equality, ordering, hashing and
// formatting. The C runtime implements the same rules; differential tests
// keep them in agreement.

use std::collections::HashMap;
use std::hash::{Hash, Hasher};
use std::rc::Rc;

#[derive(Clone, Debug)]
pub enum V {
    Unit,
    Int(i64),
    Float(f64),
    Bool(bool),
    Str(Rc<str>),
    List(Rc<Vec<V>>),
    Map(Rc<MapV>),
    Tuple(Rc<Vec<V>>),
    Struct(u32, Rc<Vec<V>>),   // struct index, fields
    Enum(u32, u32, Rc<Vec<V>>), // enum index, variant, payload
    Fn(Rc<Closure>),
    Cap(Rc<Cap>),
}

#[derive(Debug)]
pub enum Closure {
    Named(usize),
    Variant(u32, u32),
    Lambda(crate::ast::Id, Vec<(String, V)>),
}

#[derive(Debug)]
pub enum Cap {
    Console,
    Fs { root: String, attenuated: bool, writable: bool },
    Clock,
    Net,
    Listener(std::net::TcpListener),
    Conn(std::cell::RefCell<std::io::BufReader<std::net::TcpStream>>),
    Poller(std::cell::RefCell<PollerState>),
}

#[derive(Debug, Default)]
pub struct PollerState {
    pub next: i64,
    pub listeners: std::collections::BTreeMap<i64, std::net::TcpListener>,
    pub conns: std::collections::BTreeMap<i64, std::net::TcpStream>,
}

#[derive(Clone, Debug, Default)]
pub struct MapV {
    pub entries: Vec<Option<(V, V)>>,
    pub index: HashMap<V, usize>,
}

impl MapV {
    pub fn len(&self) -> usize {
        self.index.len()
    }
    pub fn get(&self, k: &V) -> Option<&V> {
        self.index.get(k).map(|i| &self.entries[*i].as_ref().unwrap().1)
    }
    pub fn insert(&mut self, k: V, v: V) {
        match self.index.get(&k) {
            Some(i) => self.entries[*i].as_mut().unwrap().1 = v,
            None => {
                self.index.insert(k.clone(), self.entries.len());
                self.entries.push(Some((k, v)));
            }
        }
    }
    pub fn remove(&mut self, k: &V) -> Option<V> {
        let i = self.index.remove(k)?;
        let (_, v) = self.entries[i].take().unwrap();
        if self.entries.len() > 8 && self.index.len() * 2 < self.entries.len() {
            self.entries.retain(|e| e.is_some());
            for (j, e) in self.entries.iter().enumerate() {
                *self.index.get_mut(&e.as_ref().unwrap().0).unwrap() = j;
            }
        }
        Some(v)
    }
    pub fn iter(&self) -> impl Iterator<Item = &(V, V)> {
        self.entries.iter().flatten()
    }
}

impl PartialEq for V {
    fn eq(&self, o: &V) -> bool {
        use V::*;
        match (self, o) {
            (Unit, Unit) => true,
            (Int(a), Int(b)) => a == b,
            (Float(a), Float(b)) => a == b,
            (Bool(a), Bool(b)) => a == b,
            (Str(a), Str(b)) => a == b,
            // Compare contents, never `Rc` identity (Rc's == short-circuits on the
            // same pointer, which would make NaN or a function equal to itself).
            (List(a), List(b)) | (Tuple(a), Tuple(b)) => a.as_slice() == b.as_slice(),
            (Struct(_, a), Struct(_, b)) => a.as_slice() == b.as_slice(),
            (Enum(_, v, a), Enum(_, w, b)) => v == w && a.as_slice() == b.as_slice(),
            (Map(a), Map(b)) => a.len() == b.len() && a.iter().all(|(k, v)| b.get(k) == Some(v)),
            _ => false,
        }
    }
}
impl Eq for V {}

impl Hash for V {
    fn hash<H: Hasher>(&self, h: &mut H) {
        use V::*;
        match self {
            Unit => 0u8.hash(h),
            Int(i) => i.hash(h),
            Float(f) => (if *f == 0.0 { 0.0f64 } else { *f }).to_bits().hash(h),
            Bool(b) => b.hash(h),
            Str(s) => s.hash(h),
            List(a) | Tuple(a) | Struct(_, a) => a.hash(h),
            Enum(_, v, a) => {
                v.hash(h);
                a.hash(h)
            }
            Map(m) => m.len().hash(h),
            Fn(_) | Cap(_) => {}
        }
    }
}

// Derived ordering: -1, 0, 1. Err means the values are not ordered (maps).
pub fn cmp(a: &V, b: &V) -> Result<i32, &'static str> {
    use V::*;
    let c = |x: bool, y: bool| if x { -1 } else if y { 1 } else { 0 };
    Ok(match (a, b) {
        (Unit, Unit) => 0,
        (Int(x), Int(y)) => c(x < y, x > y),
        (Float(x), Float(y)) => c(x < y, x > y),
        (Bool(x), Bool(y)) => c(!x & y, x & !y),
        (Str(x), Str(y)) => c(x.as_bytes() < y.as_bytes(), x.as_bytes() > y.as_bytes()),
        (List(x), List(y)) | (Tuple(x), Tuple(y)) | (Struct(_, x), Struct(_, y)) => {
            for (p, q) in x.iter().zip(y.iter()) {
                let r = cmp(p, q)?;
                if r != 0 {
                    return Ok(r);
                }
            }
            c(x.len() < y.len(), x.len() > y.len())
        }
        (Enum(_, v, x), Enum(_, w, y)) => {
            if v != w {
                return Ok(c(v < w, v > w));
            }
            for (p, q) in x.iter().zip(y.iter()) {
                let r = cmp(p, q)?;
                if r != 0 {
                    return Ok(r);
                }
            }
            0
        }
        (Map(_), Map(_)) => return Err("maps are not ordered"),
        _ => 0,
    })
}

// Float.to_fixed and `{x:.N}`: exact decimal rounding of the binary value
// (as C's "%.*f"); decimals clamped to 0..100. C: tn_float_fixed_into.
pub fn float_fixed(x: f64, d: i64) -> String {
    if x.is_nan() {
        return "nan".into();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf" } else { "-inf" }.into();
    }
    format!("{:.*}", d.clamp(0, 100) as usize, x)
}

// Shortest round-trip digits, laid out as the C runtime does (tn_fmt_float).
pub fn fmt_float(x: f64) -> String {
    if x.is_nan() {
        return "nan".into();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf".into() } else { "-inf".into() };
    }
    let neg = x.is_sign_negative();
    let s = format!("{:e}", x.abs());
    let (mant, exp) = s.split_once('e').unwrap();
    let exp: i32 = exp.parse().unwrap();
    let digits: String = mant.chars().filter(|c| *c != '.').collect();
    let mut out = String::new();
    if neg {
        out.push('-');
    }
    out.push_str(&layout_float(&digits, exp));
    out
}

pub fn layout_float(digits: &str, exp: i32) -> String {
    let d = digits.as_bytes();
    let mut out = String::new();
    if (-5..16).contains(&exp) {
        if exp >= 0 {
            let e = exp as usize;
            for i in 0..=e {
                out.push(if i < d.len() { d[i] as char } else { '0' });
            }
            out.push('.');
            if d.len() > e + 1 {
                out.push_str(&digits[e + 1..]);
            } else {
                out.push('0');
            }
        } else {
            out.push_str("0.");
            for _ in 0..(-exp - 1) {
                out.push('0');
            }
            out.push_str(digits);
        }
    } else {
        out.push(d[0] as char);
        if d.len() > 1 {
            out.push('.');
            out.push_str(&digits[1..]);
        }
        out.push_str(&format!("e{}", exp));
    }
    out
}

pub fn quote(s: &str, out: &mut String) {
    out.push('"');
    for ch in s.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\t' => out.push_str("\\t"),
            '\r' => out.push_str("\\r"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{{{:x}}}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
}

pub struct Names<'a> {
    // field names; a None field is private to another module and not shown
    pub structs: &'a [(String, Vec<Option<String>>)],
    pub enums: &'a [(String, Vec<String>)],
}

pub fn show(v: &V, top: bool, n: &Names, out: &mut String) {
    use V::*;
    let seq = |items: &[V], out: &mut String| {
        for (i, x) in items.iter().enumerate() {
            if i > 0 {
                out.push_str(", ");
            }
            show(x, false, n, out);
        }
    };
    match v {
        Unit => out.push_str("()"),
        Int(i) => out.push_str(&i.to_string()),
        Float(f) => out.push_str(&fmt_float(*f)),
        Bool(b) => out.push_str(if *b { "true" } else { "false" }),
        Str(s) => {
            if top {
                out.push_str(s)
            } else {
                quote(s, out)
            }
        }
        List(xs) => {
            out.push('[');
            seq(xs, out);
            out.push(']');
        }
        Tuple(xs) => {
            out.push('(');
            seq(xs, out);
            out.push(')');
        }
        Map(m) => {
            if m.len() == 0 {
                out.push_str("[:]");
                return;
            }
            out.push('[');
            for (i, (k, v)) in m.iter().enumerate() {
                if i > 0 {
                    out.push_str(", ");
                }
                show(k, false, n, out);
                out.push_str(": ");
                show(v, false, n, out);
            }
            out.push(']');
        }
        Struct(si, fs) => {
            let (name, fields) = &n.structs[*si as usize];
            out.push_str(name);
            if fs.is_empty() {
                out.push_str(" {}");
                return;
            }
            out.push_str(" { ");
            let mut first = true;
            for (f, x) in fields.iter().zip(fs.iter()) {
                if !first {
                    out.push_str(", ");
                }
                first = false;
                match f {
                    Some(f) => {
                        out.push_str(f);
                        out.push_str(": ");
                        show(x, false, n, out);
                    }
                    None => {
                        out.push_str("..");
                        break;
                    }
                }
            }
            out.push_str(" }");
        }
        Enum(ei, vi, xs) => {
            out.push_str(&n.enums[*ei as usize].1[*vi as usize]);
            if !xs.is_empty() {
                out.push('(');
                seq(xs, out);
                out.push(')');
            }
        }
        Fn(_) => out.push_str("<fn>"),
        Cap(c) => out.push_str(match **c {
            self::Cap::Console => "<Console>",
            self::Cap::Fs { .. } => "<Fs>",
            self::Cap::Clock => "<Clock>",
            self::Cap::Net => "<Net>",
            self::Cap::Listener(_) => "<Listener>",
            self::Cap::Conn(_) => "<Conn>",
            self::Cap::Poller(_) => "<Poller>",
        }),
    }
}
