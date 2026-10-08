#include <iostream>

int main() {
    int* values = new int[3]{2, 4, 6};
    int sum = 0;
    for (int i = 0; i < 3; ++i) {
        sum += values[i];
    }
    std::cout << sum << '\n';
    delete[] values;
    return 0;
}
