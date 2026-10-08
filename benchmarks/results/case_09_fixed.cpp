#include <iostream>
#include <vector>

int main() {
    std::vector<int> values = {2, 4, 6};
    int* start = values.data();
    values.reserve(32);
    std::cout << values[1] << '\n';
    return 0;
}
