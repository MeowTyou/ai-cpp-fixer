#include <iostream>

int main() {
    int value = 42;
    int* pointer = &value;
    std::cout << *pointer << '\n';
    return 0;
}
