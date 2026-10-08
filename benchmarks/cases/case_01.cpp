#include <iostream>

int main() {
    std::vector<int> values = {2, 4, 6};
    int sum = 0;
    for (int value : values) {
        sum += value;
    }
    std::cout << sum << '\n';
    return 0;
}
