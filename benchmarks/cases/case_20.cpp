#include <algorithm>
#include <iostream>
#include <string>

int main() {
    std::string text = "level";
    bool palindrome = std::equal(text.begin(), text.end(), text.rbegin());
    std::cout << std::boolalpha << palindrome << '\n';
    return 0;
}
