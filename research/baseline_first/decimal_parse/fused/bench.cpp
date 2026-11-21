// The build command extracts the previous experiment's unmodified reference parsers.
#include "reference.hpp"

static const char* skip_field(const char* p, const char* end, char delimiter) {
    while (p != end && *p != delimiter) ++p;
    if (p == end) throw std::runtime_error("incomplete row");
    return p + 1;
}

template <int integer_digits>
bool fixed(const char*& p, const char* end, char delimiter, Word& result) {
    constexpr int length = integer_digits + 4;
    if (end - p <= length || p[integer_digits] != '.') return false;
    const char* next = p + length;
    if (delimiter == '\n' && *next == '\r') ++next;
    if (next == end || *next != delimiter) return false;
    unsigned mant = 0;
    for (int j = 0; j < length; ++j) {
        if (j == integer_digits) continue;
        const unsigned digit = static_cast<unsigned char>(p[j]) - unsigned('0');
        if (digit > 9) return false;
        mant = 10 * mant + digit;
    }
    result = std::bit_cast<Word>(static_cast<double>(mant) / 1000.);
    p = next + 1;
    return true;
}

inline bool attempt(unsigned width, const char*& p, const char* end, char stop, Word& value) {
    switch (width) {
        case 1: return fixed<1>(p, end, stop, value);
        case 2: return fixed<2>(p, end, stop, value);
        case 3: return fixed<3>(p, end, stop, value);
        default: return false;
    }
}

template <bool hint>
__attribute__((noinline)) void fused(Field input, std::vector<Word>& output) {
    std::array<unsigned, 7> previous{};
    const char* cur = input.data();
    const char* end = cur + input.size();
    size_t index = 0;
    while (cur < end) {
        cur = skip_field(cur, end, ';');
        cur = skip_field(cur, end, ';');
        if (index + 7 > output.size()) throw std::runtime_error("row count");
        for (int col = 0; col < 7; ++col) {
            char delimiter = col == 6 ? '\n' : ';';
            Word& value = output[index++];
            if constexpr (hint) {
                if (attempt(previous[col], cur, end, delimiter, value)) continue;
            }
            if (end - cur >= 4) {
                const auto width = cur[1] == '.' ? 1u : cur[2] == '.' ? 2u : 3u;
                if (attempt(width, cur, end, delimiter, value)) {
                    if constexpr (hint) previous[col] = width;
                    continue;
                }
            }
            const char* start = cur;
            cur = skip_field(cur, end, delimiter);
            size_t n = cur - start - 1;
            if (col == 6 && n && start[n-1] == '\r') --n;
            value = general<Fast>({start, n});
        }
    }
    if (index != output.size()) throw std::runtime_error("row count");
}

int main(int argc, char** argv) {
    if (argc != 3 || std::fegetround() != FE_TONEAREST) return 2;
    std::ifstream file(argv[1], std::ios::binary);
    std::string input{std::istreambuf_iterator<char>(file), {}};
    std::vector<Word> output(7 * std::count(input.begin(), input.end(), '\n'));
    if (output.empty()) return 2;
    const auto arms = std::array{parse<Fast>, parse<Standard>, parse<Scalar>, parse<Paired>,
                                 fused<false>, fused<true>};
    const char* labels[] = {"fast_float", "std", "scalar", "paired", "fused", "hint"};
    for (size_t a = 0; a < arms.size(); ++a) {
        arms[a](input, output);
        std::ofstream out(std::string(argv[2]) + "." + labels[a], std::ios::binary);
        out.write(reinterpret_cast<const char*>(output.data()), output.size() * sizeof(Word));
        if (!out) throw std::runtime_error("save failed");
    }
    for (size_t round = 0; round < 10; ++round) {
        for (size_t position = 0; position < arms.size(); ++position) {
            size_t a = (round + position) % arms.size();
            auto start = std::chrono::steady_clock::now();
            for (int pass = 0; pass < 32; ++pass) {
                arms[a](input, output);
                asm volatile("" : : "r"(output.data()) : "memory");
            }
            auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(
                std::chrono::steady_clock::now() - start).count();
            std::cout << round << ',' << position << ',' << labels[a] << ",32," << elapsed << '\n';
        }
    }
}
