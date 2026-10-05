#include <iostream>

// 评测类型：编译错误。
// 程序用途：计算 1、2、3、4 的和，并输出结果。
// 已知正确输出：10 后跟一个换行符。
// 故意保留的错误：输出语句末尾缺少分号。
// 修复要求：恢复正常编译，保留求和计算和输出。
int main() {
    int numbers[4] = {1, 2, 3, 4};
    int sum = 0;

    for (int i = 0; i < 4; ++i) {
        sum += numbers[i];
    }

    std::cout << sum << '\n';
    return 0;
}
