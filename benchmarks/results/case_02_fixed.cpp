#include <iostream>

int main() {
    int values[4] = {1, 2, 3, 4};
    int sum = 0;
    for (int index = 0; index < 4; ++index) {
        sum += values[index];
    }
    std::cout << sum << '\n';
    return 0;
}
