#include <stdio.h>
#include <stdlib.h>
#include "../checked.h"
typedef struct T { struct T *l, *r; } T;
static T *make(int64_t d) { T *t = malloc(sizeof *t); if (d == 0) { t->l = t->r = NULL; } else { t->l = make(ck_sub(d, 1)); t->r = make(ck_sub(d, 1)); } return t; }
static int64_t check(T *t) { return t->l ? ck_add(ck_add(1, check(t->l)), check(t->r)) : 1; }
static void drop(T *t) { if (t->l) { drop(t->l); drop(t->r); } free(t); }
int main(void) {
    int maxd = 18; T *ll = make(maxd);
    for (int d = 4; d <= maxd; d += 2) {
        int64_t iters = 1L << (maxd - d + 4), total = 0;
        for (int64_t i = 0; i < iters; i++) { T *t = make(d); total = ck_add(total, check(t)); drop(t); }
        printf("%lld trees of depth %d check: %lld\n", (long long)iters, d, (long long)total);
    }
    printf("long lived tree of depth %d check: %lld\n", maxd, (long long)check(ll));
    return 0;
}
