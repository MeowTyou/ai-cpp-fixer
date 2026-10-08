#include <iostream>

int main() {
    int numbers[4] = {1, 2, 3, 4};
    int sum = 0;

    for (int i = 0; i < 4; ++i) {
        sum += numbers[i];
    }

    std::cout << sum << '\n'
    return 0;
}
