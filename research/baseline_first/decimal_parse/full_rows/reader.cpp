#define main previous_main
#include "../fused/bench.cpp"
#undef main

struct Columns {
    std::array<std::vector<double>, 7> values;
    std::array<std::vector<unsigned char>, 7> masks;
};

template<bool split>
void rows(Field input, Columns& out) {
    auto cur = input.data();
    const auto end = cur + input.size();
    while (cur < end) {
        cur = skip_field(cur, end, ';');
        cur = skip_field(cur, end, ';');
        for (int col = 0; col < 7; ++col) {
            const char delimiter = col == 6 ? '\n' : ';';
            const char* limit = split ? skip_field(cur, end, delimiter) : end;
            Word word;
            const unsigned width = limit-cur >= 4 ? (cur[1]=='.' ? 1 : cur[2]=='.' ? 2 : 3) : 0;
            if (!attempt(width, cur, limit, delimiter, word)) {
                const char* start = cur;
                cur = split ? limit : skip_field(cur, end, delimiter);
                size_t n = cur-start-1;
                if (col == 6 && n && start[n-1]=='\r') --n;
                word = general<Fast>({start, n});
            }
            out.values[col].push_back(std::bit_cast<double>(word));
            out.masks[col].push_back(word == missing);
        }
    }
}

template<bool split>
Columns read_day(const char* path) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream) throw std::runtime_error("open");
    std::array<char,8192> block;
    std::string pending;
    Columns output;
    while(stream.read(block.data(),block.size()) || stream.gcount()) {
        pending.append(block.data(), stream.gcount());
        const auto last = pending.rfind('\n');
        if (last == std::string::npos) continue;
        rows<split>({pending.data(),last+1},output);
        pending.erase(0,last+1);
    }
    if (!stream.eof() || !pending.empty()) throw std::runtime_error("incomplete input");
    return output;
}

int main(int argc,char** argv) {
    if(argc!=3 || std::fegetround()!=FE_TONEAREST) return 2;
    auto readers = std::array{read_day<false>,read_day<true>};
    for(int arm=0;arm<2;++arm) {
        auto out = readers[arm](argv[1]);
        std::ofstream dump(std::string(argv[2])+std::to_string(arm),std::ios::binary);
        for(int col=0;col<7;++col) {
            dump.write(reinterpret_cast<const char*>(out.values[col].data()),out.values[col].size()*8);
            dump.write(reinterpret_cast<const char*>(out.masks[col].data()),out.masks[col].size());
        }
        if(!dump) throw std::runtime_error("dump");
    }
    for(int r=0;r<8;++r) for(int pos=0;pos<2;++pos) {
        int arm=(r+pos)%2;
        auto start=std::chrono::steady_clock::now();
        for(int pass=0;pass<16;++pass) {
            auto out=readers[arm](argv[1]);
            asm volatile("" : : "r"(&out) : "memory");
        }
        auto ns=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-start).count();
        std::cout<<r<<','<<pos<<','<<(arm?"split":"direct")<<','<<ns<<'\n';
    }
}
