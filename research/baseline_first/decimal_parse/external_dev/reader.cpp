#define main previous_main
#include "../fused/bench.cpp"
#undef main

struct Column {
    std::vector<double> values;
    std::vector<unsigned char> missing_mask;
};

bool tenths(const char*& p, const char* end, Word& word) {
    if (end-p < 6 || p[3] != '.' || p[5] != '\n') return false;
    unsigned mantissa = 0;
    for (int i : {0,1,2,4}) {
        unsigned digit = static_cast<unsigned char>(p[i]) - unsigned('0');
        if (digit > 9) return false;
        mantissa = 10 * mantissa + digit;
    }
    word = std::bit_cast<Word>(double(mantissa) / 10.);
    p += 6;
    return true;
}

template<bool split, bool adapted>
Column read_file(const char* path) {
    std::ifstream stream(path, std::ios::binary);
    std::string pending;
    if (!std::getline(stream,pending) || pending != "date,co2")
        throw std::runtime_error("header");
    pending.clear();
    std::array<char,8192> block;
    Column out;
    while (stream.read(block.data(),block.size()) || stream.gcount()) {
        pending.append(block.data(),stream.gcount());
        auto last = pending.rfind('\n');
        if (last == std::string::npos) continue;
        const char* cur = pending.data();
        const char* end = cur + last + 1;
        while (cur < end) {
            cur = skip_field(cur,end,',');
            const char* limit = split ? skip_field(cur,end,'\n') : end;
            Word word;
            bool recognized;
            if constexpr (adapted) recognized = tenths(cur,limit,word);
            else {
                unsigned width = limit-cur >= 4 ? (cur[1]=='.' ? 1 : cur[2]=='.' ? 2 : 3) : 0;
                recognized = attempt(width,cur,limit,'\n',word);
            }
            if (!recognized) {
                const char* start = cur;
                cur = split ? limit : skip_field(cur,end,'\n');
                word = general<Fast>({start,size_t(cur-start-1)});
            }
            out.values.push_back(std::bit_cast<double>(word));
            out.missing_mask.push_back(word == missing);
        }
        pending.erase(0,last+1);
    }
    if (!stream.eof() || !pending.empty()) throw std::runtime_error("incomplete input");
    return out;
}

int main(int argc,char** argv) {
    if (argc != 4 || std::fegetround()!=FE_TONEAREST) return 2;
    auto readers = std::array{read_file<false,false>,read_file<true,false>,
                              read_file<false,true>,read_file<true,true>};
    if (Field(argv[1]) == "check") {
        for (int i=0;i<4;++i) {
            auto out = readers[i](argv[2]);
            std::ofstream dump(std::string(argv[3])+std::to_string(i),std::ios::binary);
            dump.write(reinterpret_cast<const char*>(out.values.data()),out.values.size()*8);
            dump.write(reinterpret_cast<const char*>(out.missing_mask.data()),out.missing_mask.size());
            if (!dump) return 3;
        }
        return 0;
    }
    std::cout << "round,guard_position,arm_position,guard,arm,ns_per_64\n";
    for (int round=0;round<16;++round) for (int g=0;g<2;++g) for (int a=0;a<2;++a) {
        int guard = (g+round)%2;
        int arm = (a+round)%2;
        auto start = std::chrono::steady_clock::now();
        for (int i=0;i<64;++i) {
            auto out = readers[2*guard+arm](argv[2]);
            asm volatile("" : : "r"(&out) : "memory");
        }
        auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now()-start).count();
        std::cout << round << ',' << g << ',' << a << ',' << (guard?"tenths":"milliscale")
                  << ',' << (arm?"split":"direct") << ',' << ns << '\n';
    }
}
