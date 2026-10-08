#include <cstring>
#include <iostream>

int main() {
    char* text = new char[6];
    std::strcpy(text, "hello");
    delete[] text;
    std::cout << text << '\n';
    return 0;
}
