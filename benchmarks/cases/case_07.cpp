#include <cstring>
#include <iostream>

int main() {
    char text[4];
    std::strcpy(text, "hello");
    std::cout << text << '\n';
    return 0;
}
