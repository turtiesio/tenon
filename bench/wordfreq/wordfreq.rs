use std::collections::HashMap;
use std::io::Read;
fn main() {
    let mut s = String::new();
    std::io::stdin().read_to_string(&mut s).unwrap();
    let s = s.to_lowercase();
    let mut counts: HashMap<&str, i64> = HashMap::new();
    for w in s.split_ascii_whitespace() { *counts.entry(w).or_insert(0) += 1; }
    let mut v: Vec<(&str, i64)> = counts.into_iter().collect();
    v.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(b.0)));
    for (w, n) in v.iter().take(10) { println!("{} {}", n, w); }
}
