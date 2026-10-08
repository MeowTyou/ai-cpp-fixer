#include <iostream>

int main() {
    int values[5] = {1, 3, 5, 7, 9};
    int target = 9;
    int left = 0;
    int right = 4;
    while (left < right) {
        int middle = left + (right - left) / 2;
        if (values[middle] == target) {
            std::cout << middle << '\n';
            return 0;
        }
        if (values[middle] < target) {
            left = middle + 1;
        } else {
            right = middle - 1;
        }
    }
    std::cout << -1 << '\n';
    return 0;
}
