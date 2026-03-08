#include <arm_sve.h>
#include <stdio.h>

int main() {
    // 使用 SVE 内置函数获取当前向量长度 (以位为单位)
    uint64_t vl = svcntb() * 8;

    printf("================================\n");
    printf("Hello from gem5 SVE world!\n");
    printf("SVE Vector Length: %lu bits\n", vl);
    printf("================================\n");

    return 0;
}
