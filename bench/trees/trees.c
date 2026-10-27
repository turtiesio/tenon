#include <stdio.h>
#include <stdlib.h>
typedef struct T { struct T *l, *r; } T;
static T *make(int d) { T *t = malloc(sizeof *t); if (d == 0) { t->l = t->r = NULL; } else { t->l = make(d - 1); t->r = make(d - 1); } return t; }
static long check(T *t) { return t->l ? 1 + check(t->l) + check(t->r) : 1; }
static void drop(T *t) { if (t->l) { drop(t->l); drop(t->r); } free(t); }
int main(void) {
    int maxd = 18; T *ll = make(maxd);
    for (int d = 4; d <= maxd; d += 2) {
        long iters = 1L << (maxd - d + 4), total = 0;
        for (long i = 0; i < iters; i++) { T *t = make(d); total += check(t); drop(t); }
        printf("%ld trees of depth %d check: %ld\n", iters, d, total);
    }
    printf("long lived tree of depth %d check: %ld\n", maxd, check(ll));
    return 0;
}
