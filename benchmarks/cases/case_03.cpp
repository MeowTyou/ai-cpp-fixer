#include <iostream>
#include <vector>

int main() {
    std::vector<int> values = {3, 1, 4};
    values.push(2);
    std::cout << values.size() << '\n';
    return 0;
}
