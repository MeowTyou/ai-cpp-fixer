#include <algorithm>
#include <iostream>
#include <iterator>
#include <vector>

int main() {
    std::vector<int> values = {4, 7, 9};
    std::vector<int>::iterator position = std::find(values.begin(), values.end(), 9);
    std::cout << std::distance(values.begin(), position) << '\n';
    return 0;
}
