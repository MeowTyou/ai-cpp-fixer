#include <algorithm>
#include <iostream>
#include <vector>

int main() {
    std::vector<int> values = {-2, 5, -2, 0};
    std::sort(values.begin(), values.end());
    std::cout << values.front() << ' ' << values.back() << '\n';
    return 0;
}
