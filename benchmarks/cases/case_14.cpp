#include <algorithm>
#include <iostream>

int main() {
    int values[3] = {-8, -3, -11};
    int maximum = 0;
    for (int value : values) {
        maximum = std::max(maximum, value);
    }
    std::cout << maximum << '\n';
    return 0;
}
