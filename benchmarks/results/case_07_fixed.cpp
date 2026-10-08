#include <cstring>
#include <iostream>

int main() {
    char text[6];
    std::strcpy(text, "hello");
    std::cout << text << '\n';
    return 0;
}
