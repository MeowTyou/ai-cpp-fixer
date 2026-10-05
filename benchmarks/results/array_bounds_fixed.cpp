#include <iostream>

// 评测类型：数组越界。
// 程序用途：计算数组中 4 个元素的和，并输出结果。
// 已知正确输出：10 后跟一个换行符。
// 故意保留的错误：循环多执行一次，访问不存在的 numbers[4]。
// 修复要求：消除越界，保留全部 4 个元素的求和计算和输出。
int main() {
    int numbers[4] = {1, 2, 3, 4};
    int sum = 0;

    for (int i = 0; i < 4; ++i) {
        sum += numbers[i];
    }

    std::cout << sum << '\n';
    return 0;
}
