#define main previous_main
#include "../bench.cpp"
#undef main

__attribute__((noinline)) void prescan(Field input, std::vector<Word>& output) {
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
            const char* after = skip_field(cur, end, delimiter);
            if (after - cur >= 5) {
                unsigned width = cur[1] == '.' ? 1u : cur[2] == '.' ? 2u : 3u;
                if (attempt(width, cur, after, delimiter, value)) continue;
            }
            const char* start = cur;
            cur = after;
            size_t n = cur - start - 1;
            if (col == 6 && n && start[n-1] == '\r') --n;
            value = general<Fast>({start, n});
        }
    }
    if (index != output.size()) throw std::runtime_error("row count");
}

__attribute__((noinline)) void cursor(Field input, std::vector<Word>& output) {
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
            double number;
            auto parsed = fast_float::from_chars(cur, end, number);
            const char* next = parsed.ptr;
            if (delimiter == '\n' && next != end && *next == '\r') ++next;
            if (parsed.ec == std::errc{} && next != end && *next == delimiter) {
                value = std::bit_cast<Word>(number);
                cur = next + 1;
                continue;
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
    const auto arms = std::array{prescan, fused<false>, cursor};
    const char* labels[] = {"prescan", "direct", "cursor"};
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
