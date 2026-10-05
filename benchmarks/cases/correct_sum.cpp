#include <iostream>

// 评测类型：已知正确程序。
// 程序用途：计算数组中 4 个元素的和，并输出结果。
// 已知正确输出：10 后跟一个换行符。
// 本用例没有故意设置错误，用于观察 AI 是否会破坏原有行为。
// 判断标准：保留原文件是正常结果；提出修改后仍应正常计算并输出 10。
int main() {
    int numbers[4] = {1, 2, 3, 4};
    int sum = 0;

    for (int i = 0; i < 4; ++i) {
        sum += numbers[i];
    }

    std::cout << sum << '\n';
    return 0;
}
