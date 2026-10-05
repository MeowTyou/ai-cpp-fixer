#include <iostream>

// 评测类型：重复释放。
// 程序用途：创建并输出整数 42，然后释放它占用的内存。
// 已知正确输出：42 后跟一个换行符。
// 故意保留的错误：同一块内存被 delete 两次。
// 修复要求：消除重复释放，同时保留输出且没有内存泄漏。
int main() {
    int* value = new int(42);
    std::cout << *value << '\n';

    delete value;

    return 0;
}
