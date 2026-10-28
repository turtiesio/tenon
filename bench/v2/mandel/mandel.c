/* Serial C reference for mandel.tn (same algorithm and output). */
#include <stdio.h>

#define WIDTH 1600
#define HEIGHT 1200
#define MAX_ITER 1000

int main(void) {
    long long sum = 0, inside = 0, h = 0;
    for (int y = 0; y < HEIGHT; y++) {
        double ci = (double)y / HEIGHT * 2.4 - 1.2;
        long long rs = 0, ri = 0, rh = 0;
        for (int x = 0; x < WIDTH; x++) {
            double cr = (double)x / WIDTH * 3.2 - 2.2, zr = 0.0, zi = 0.0;
            int i = 0;
            while (i < MAX_ITER && zr * zr + zi * zi <= 4.0) {
                double t = zr * zr - zi * zi + cr;
                zi = 2.0 * zr * zi + ci;
                zr = t;
                i++;
            }
            rs += i;
            if (i == MAX_ITER) ri++;
            rh = (rh * 31 + i) % 1000000007;
        }
        sum += rs;
        inside += ri;
        h = (h * 7 + rh) % 1000000007;
    }
    printf("mandelbrot %dx%d, %d iterations: %lld in total, %lld inside, checksum %lld\n", WIDTH, HEIGHT, MAX_ITER, sum, inside, h);
    return 0;
}
