#include "sprintz_xff.h"
#include <iostream>
#include <iterator>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 2) return 1;
    std::vector<char> bytes(std::istreambuf_iterator<char>(std::cin), {});
    if (bytes.empty() || bytes.size() > 240000) return 2;
    std::vector<uint16_t> input(bytes.size() / 2 + 128), output(120128);
    memcpy(input.data(), bytes.data(), bytes.size());
    int64_t words;
    if (std::string(argv[1]) == "encode" && bytes.size() == 120000) {
        words = compress_rowmajor_xff_rle_16b(input.data(), 60000,
            reinterpret_cast<int16_t*>(output.data()), 12, true);
    } else if (std::string(argv[1]) == "decode") {
        words = decompress_rowmajor_xff_rle_16b(
            reinterpret_cast<int16_t*>(input.data()), output.data());
        if (words != 60000) return 3;
    } else return 4;
    if (words <= 0 || words > 120000) return 5;
    std::cout.write(reinterpret_cast<char*>(output.data()), 2 * words + (std::string(argv[1]) == "encode"));
}
