#include <iostream>
#include <numeric>
#include <vector>

int main() {
    std::vector<int> values;
    int sum = std::accumulate(values.begin(), values.end(), 0);
    std::cout << sum << '\n';
    return 0;
}
