#include <iostream>

int main() {
    int values[3] = {2, 4, 6};
    int sum = 0;
    for (int i = -1; i < 3; ++i) {
        sum += values[i];
    }
    std::cout << sum << '\n';
    return 0;
}
