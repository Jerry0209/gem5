#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define N 1024 // 必须和 SVE 版本保持一致

// 初始化数组
void init_arrays(int32_t *a, int32_t *b) {
    for (int i = 0; i < N; i++) {
        a[i] = i;
        b[i] = i * 2;
    }
}

int main() {
    int32_t a[N], b[N], c[N];

    init_arrays(a, b);

    printf("Scalar (Standard C) Addition Benchmark\n");
    printf("Array Size: %d\n", N);

    // ==========================================
    // 标量核心循环 (Scalar Loop)
    // ==========================================
    // 这里没有 SVE，没有向量，只有最朴素的"一次做一个"
    system("m5 resetstats");
    for (int i = 0; i < N; i++) {
        c[i] = a[i] + b[i];
    }

    system("m5 dumpstats");

    printf("Computation Complete!\n");

    // ==========================================
    // 验证结果
    // ==========================================
    int errors = 0;
    for (int j = 0; j < N; j++) {
        int32_t expected = a[j] + b[j];
        if (c[j] != expected) {
            errors++;
        }
    }

    if (errors == 0) {
        printf("SUCCESS: All results match!\n");
    } else {
        printf("FAILURE: Found %d errors.\n", errors);
    }

    return 0;
}
