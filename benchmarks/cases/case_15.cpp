#include <iostream>

int main() {
    int values[5] = {1, 2, 2, 3, 2};
    int count = 0;
    for (int& value : values) {
        if (value = 2) {
            ++count;
        }
    }
    std::cout << count << '\n';
    return 0;
}
