#include <iomanip>
#include <iostream>

int main() {
    int values[3] = {2, 3, 5};
    int sum = 0;
    for (int value : values) {
        sum += value;
    }
    double average = sum / 3.0;
    std::cout << std::fixed << std::setprecision(2) << average << '\n';
    return 0;
}
