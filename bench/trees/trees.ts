type Tree = null | [Tree, Tree];
function make(d: number): [Tree, Tree] { return d === 0 ? [null, null] : [make(d - 1), make(d - 1)]; }
function check(t: [Tree, Tree]): number { return t[0] === null ? 1 : 1 + check(t[0]) + check(t[1] as [Tree, Tree]); }
const maxd = 18;
const ll = make(maxd);
const out: string[] = [];
for (let d = 4; d <= maxd; d += 2) {
  const iters = 2 ** (maxd - d + 4);
  let total = 0;
  for (let i = 0; i < iters; i++) total += check(make(d));
  out.push(`${iters} trees of depth ${d} check: ${total}`);
}
out.push(`long lived tree of depth ${maxd} check: ${check(ll)}`);
console.log(out.join("\n"));
