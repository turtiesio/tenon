enum Tree { Leaf, Node(Box<Tree>, Box<Tree>) }
fn make(d: i32) -> Tree { if d == 0 { Tree::Node(Box::new(Tree::Leaf), Box::new(Tree::Leaf)) } else { Tree::Node(Box::new(make(d - 1)), Box::new(make(d - 1))) } }
fn check(t: &Tree) -> i64 { match t { Tree::Leaf => 0, Tree::Node(l, r) => 1 + check(l) + check(r) } }
fn main() {
    let maxd = 18;
    let ll = make(maxd);
    let mut d = 4;
    while d <= maxd {
        let iters: i64 = 1 << (maxd - d + 4);
        let mut total = 0;
        for _ in 0..iters { total += check(&make(d)); }
        println!("{} trees of depth {} check: {}", iters, d, total);
        d += 2;
    }
    println!("long lived tree of depth {} check: {}", maxd, check(&ll));
}
