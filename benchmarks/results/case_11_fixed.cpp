#include <iostream>

void release(int* value) {
    delete value;
}

int main() {
    int* value = new int(42);
    std::cout << *value << '\n';
    release(value);

    return 0;
}
