#include <cstring>
#include <iostream>

int main() {
    char* text = new char[6];
    std::strcpy(text, "hello");
    std::cout << text << '\n';
    delete[] text;
    return 0;
}