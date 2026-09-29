#include <iostream>

int main() {
    // 预期输出：sum=10，用于检查 AI 的逻辑说明和修复结果。
    int numbers[4] = {1, 2, 3, 4};
    int sum = 0;

    for (int i = 0; i <= 4; ++i) {
        sum += numbers[i];
    }

    std::cout << "sum=" << sum << '\n';
    return 0;
}
