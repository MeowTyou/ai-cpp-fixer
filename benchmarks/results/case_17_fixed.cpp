#include <iostream>

int main() {
    int number = 5;
    int factorial = 1;
    for (int i = 2; i <= number; ++i) {
        factorial *= i;
    }
    std::cout << factorial << '\n';
    return 0;
}
