#include "fast_float/fast_float.h"
#include <algorithm>
#include <array>
#include <bit>
#include <cfenv>
#include <charconv>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>
#include <emmintrin.h>

using Word = std::uint64_t;
using Field = std::string_view;
constexpr Word missing = 0x7ff8000000000001ULL, invalid = missing + 1;
enum Arm { Fast, Standard, Scalar, Paired, Scan };
constexpr const char* names[] = {"fast_float", "std", "scalar", "paired", "scan"};

template <Arm arm>
Word general(Field s) {
    if (s.empty() || s == "?") return missing;
    double v;
    const char *p = s.data(), *end = p + s.size();
    if constexpr (arm == Standard) {
        const auto r = std::from_chars(p, end, v);
        if (r.ec != std::errc() || r.ptr != end) return invalid;
    } else {
        const auto r = fast_float::from_chars(p, end, v);
        if (r.ec != std::errc() || r.ptr != end) return invalid;
    }
    return std::bit_cast<Word>(v);
}

inline int mantissa(Field s) {
    const int n = static_cast<int>(s.size());
    if (n < 5 || n > 7 || s[n - 4] != '.') return -1;
    int x = 0;
    for (int i = 0; i < n; ++i) {
        if (i == n - 4) continue;
        unsigned digit = static_cast<unsigned char>(s[i]) - '0';
        if (digit > 9) return -1;
        x = 10 * x + static_cast<int>(digit);
    }
    return x;
}

inline Word scalar(Field s, int x) {
    return x < 0 ? general<Fast>(s) : std::bit_cast<Word>(static_cast<double>(x) / 1000.);
}

template <Arm arm>
void convert(const std::array<Field, 7>& fields, Word* out) {
    size_t i = 0;
    if constexpr (arm == Paired) {
        for (; i + 1 < fields.size(); i += 2) {
            int a = mantissa(fields[i]), b = mantissa(fields[i + 1]);
            if (a >= 0 && b >= 0) {
                auto pair = _mm_div_pd(_mm_set_pd(b, a), _mm_set1_pd(1000.));
                _mm_storeu_si128(reinterpret_cast<__m128i*>(out + i), _mm_castpd_si128(pair));
            } else {
                out[i] = scalar(fields[i], a);
                out[i + 1] = scalar(fields[i + 1], b);
            }
        }
    }
    for (; i < fields.size(); ++i) {
        if constexpr (arm == Scalar || arm == Paired) out[i] = scalar(fields[i], mantissa(fields[i]));
        else if constexpr (arm == Scan) out[i] = fields[i].size();
        else out[i] = general<arm>(fields[i]);
    }
}

template <Arm arm>
__attribute__((noinline)) void parse(Field input, std::vector<Word>& output) {
    const char *cur = input.data(), *end = cur + input.size();
    size_t count = 0;
    while (cur != end) {
        std::array<Field, 7> fields;
        for (int col = 0; col < 9; ++col) {
            const char* start = cur;
            const char stop = col == 8 ? '\n' : ';';
            while (cur != end && *cur != stop) ++cur;
            if (cur == end) throw std::runtime_error("incomplete row");
            if (col >= 2) {
                size_t len = cur - start;
                if (col == 8 && len && cur[-1] == '\r') --len;
                fields[col - 2] = {start, len};
            }
            ++cur;
        }
        if (count + 7 > output.size()) throw std::runtime_error("row count");
        convert<arm>(fields, output.data() + count);
        count += 7;
    }
    if (count != output.size()) throw std::runtime_error("row count");
}

int main(int argc, char** argv) {
    if (argc != 3 || std::fegetround() != FE_TONEAREST) return 2;
    std::ifstream file(argv[1], std::ios::binary);
    std::string input{std::istreambuf_iterator<char>(file), {}};
    size_t rows = std::count(input.begin(), input.end(), '\n');
    if (rows == 0) return 2;
    std::vector<Word> output(7 * rows);
    const auto arms = std::array{parse<Fast>, parse<Standard>, parse<Scalar>, parse<Paired>, parse<Scan>};
    for (size_t i = 0; i < arms.size(); ++i) {
        arms[i](input, output);
        if (i != Scan) {
            std::ofstream out(std::string(argv[2]) + "." + names[i], std::ios::binary);
            out.write(reinterpret_cast<const char*>(output.data()), output.size() * sizeof(Word));
            if (!out) return 2;
        }
    }
    const int passes = 32;
    for (size_t round = 0; round < 10; ++round) {
        for (size_t pos = 0; pos < arms.size(); ++pos) {
            auto arm = (round + pos) % arms.size();
            auto start = std::chrono::steady_clock::now();
            for (int pass = 0; pass < passes; ++pass) {
                arms[arm](input, output);
                asm volatile("" : : "r"(output.data()) : "memory");
            }
            auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(
                std::chrono::steady_clock::now() - start).count();
            std::cout << round << ',' << pos << ',' << names[arm] << ',' << passes << ',' << elapsed << '\n';
        }
    }
}
