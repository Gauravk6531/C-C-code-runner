#include <iostream>
#include <string>

int main() {
    std::cout << "Hello from C++!" << std::endl;
    std::cout << "Please enter your name: " << std::flush;
    
    std::string name;
    if (std::getline(std::cin, name)) {
        std::cout << "Wow, nice to meet you, " << name << "!" << std::endl;
    } else {
        std::cout << "Failed to read name." << std::endl;
    }
    
    std::cout << "Enter a lucky number: " << std::flush;
    int number;
    if (std::cin >> number) {
        std::cout << "Your lucky number squared is: " << (number * number) << std::endl;
    } else {
        std::cout << "That was not a valid number!" << std::endl;
    }
    
    std::cout << "Program finished. Goodbye!" << std::endl;
    return 0;
}
