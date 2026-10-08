#include <iostream>

int main() {
    int* value = new int(42);
    delete value;

    std::cout << *value << '\n';
    return 0;
}
