#include <arm_sve.h> // 必须包含这个头文件才能使用 SVE 指令
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define N 1024 // 数组大小

// 初始化数组
void init_arrays(int32_t *a, int32_t *b) {
    for (int i = 0; i < N; i++) {
        a[i] = i;      // 0, 1, 2, ...
        b[i] = i * 2;  // 0, 2, 4, ...
    }
}

int main() {
    int32_t a[N], b[N], c[N];

    init_arrays(a, b);

    // 获取当前硬件的向量长度 (以 32位整数 为单位)
    // 例如：如果向量长 128-bit，那么 svcntw() 返回 4 (因为 4 * 32 = 128)
    uint64_t num_elements = svcntw();

    printf("SVE Vector Addition Benchmark\n");
    printf("Array Size: %d\n", N);
    printf("Hardware Vector Length: %lu bits (%lu integers per vector)\n",
           num_elements * 32, num_elements);

    // ==========================================
    // SVE 核心循环 (Core Loop)
    // ==========================================
    system("m5 resetstats");
    int i = 0;

    // svwhilelt_b32: 创建一个"预测断言"(Predicate)。
    // 它会判断 i < N 是否成立。如果剩下不到一整组向量，它会自动处理剩下的尾巴。
    svbool_t pg = svwhilelt_b32(i, N);

    while (svptest_any(svptrue_b32(), pg)) {
        // 1. 加载 (Load)
        svint32_t va = svld1_s32(pg, &a[i]);
        svint32_t vb = svld1_s32(pg, &b[i]);

        // 2. 加法 (Add)
        svint32_t vc = svadd_s32_z(pg, va, vb);

        // 3. 存储 (Store)
        svst1_s32(pg, &c[i], vc);

        // 4. 更新索引
        i += svcntw(); // 一次跳过一个向量的长度
        pg = svwhilelt_b32(i, N); // 更新断言，准备下一轮
    }

    system("m5 dumpstats");

    printf("Computation Complete!\n");

    // ==========================================
    // 验证结果 (Verify)
    // ==========================================
    int errors = 0;
    for (int j = 0; j < N; j++) {
        int32_t expected = a[j] + b[j];
        if (c[j] != expected) {
            errors++;
            printf("Error at %d: Expected %d, Got %d\n", j, expected, c[j]);
            if (errors > 10) break; // 错误太多就停下
        }
    }

    if (errors == 0) {
        printf("SUCCESS: All results match!\n");
        // 打印前几个结果看看
        printf("Results: %d, %d, %d, %d, %d\n", c[0], c[1], c[2], c[3], c[4]);
    } else {
        printf("FAILURE: Found %d errors.\n", errors);
    }

    return 0;
}
