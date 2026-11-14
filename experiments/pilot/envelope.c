/* Envelope (C2) of the WASI copy path, measured directly on the host: the least wall time to move N bytes
   (a) from a file into a user buffer with read(), and (b) from a user buffer into a new file with write(),
   minimized over buffer sizes and repetitions. Any fd_read/fd_write implementation does at least this. */
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
int main(int argc, char **argv) {
    const char *in = argv[1], *out = argv[2]; int reps = atoi(argv[3]);
    size_t sizes[] = {65536, 1 << 20, 4 << 20, 16 << 20};
    double best_r = 1e9, best_w = 1e9; size_t bs_r = 0, bs_w = 0; off_t n = 0;
    for (int k = 0; k < 4; k++) {
        size_t bs = sizes[k]; char *buf = aligned_alloc(4096, bs); memset(buf, 7, bs);
        for (int r = 0; r < reps; r++) {
            int fd = open(in, O_RDONLY); double t0 = now(); ssize_t got; n = 0;
            while ((got = read(fd, buf, bs)) > 0) n += got;
            double t = now() - t0; close(fd); if (t < best_r) { best_r = t; bs_r = bs; }
            int fo = open(out, O_WRONLY | O_CREAT | O_TRUNC, 0644); t0 = now(); off_t left = n;
            while (left > 0) { ssize_t w = write(fo, buf, left < (off_t)bs ? (size_t)left : bs); left -= w; }
            t = now() - t0; close(fo); unlink(out); if (t < best_w) { best_w = t; bs_w = bs; }
        }
        free(buf);
    }
    printf("{\"bytes\": %lld, \"read_min_s\": %.6f, \"read_best_buffer\": %zu, \"write_min_s\": %.6f, \"write_best_buffer\": %zu}\n",
           (long long)n, best_r, bs_r, best_w, bs_w);
    return 0;
}
