#define main previous_main
#include "../fused/bench.cpp"
#undef main

enum Strategy { Adaptive, Current, Static, General, Record };
constexpr const char* labels[] = {"adaptive","current","static","general","record"};

template<int width>
bool tenths(const char*& p,const char* end,char stop,Word& word) {
    constexpr int length = width + 2;
    if (end-p <= length || p[width] != '.') return false;
    const char* next = p + length;
    if (stop == '\n' && *next == '\r') ++next;
    if (next == end || *next != stop) return false;
    unsigned mantissa = 0;
    for (int i=0;i<length;++i) {
        if (i == width) continue;
        unsigned digit = static_cast<unsigned char>(p[i]) - unsigned('0');
        if (digit > 9) return false;
        mantissa = 10*mantissa + digit;
    }
    word = std::bit_cast<Word>(double(mantissa)/10.);
    p = next+1;
    return true;
}

template<Strategy strategy,bool co2>
bool recognize(const char*& p,const char* end,char stop,int& learned,Word& word) {
    if constexpr (strategy == General) return false;
    if constexpr (strategy == Record && co2) return tenths<3>(p,end,stop,word);
    if (end-p < 4) return false;
    unsigned width = p[1]=='.' ? 1 : p[2]=='.' ? 2 : 3;
    int scale = co2 ? 1 : 3;
    if constexpr (strategy == Adaptive || strategy == Current) {
        scale = strategy == Adaptive ? learned : 0;
        if (!scale) {
            unsigned i = width+2;
            scale = end-p > i && (p[i]==stop || (stop=='\n' && p[i]=='\r')) ? 1 : 3;
        }
    }
    bool ok;
    if (scale==3) ok = attempt(width,p,end,stop,word);
    else if (width==1) ok = tenths<1>(p,end,stop,word);
    else if (width==2) ok = tenths<2>(p,end,stop,word);
    else ok = tenths<3>(p,end,stop,word);
    if constexpr (strategy == Adaptive) {
        if (ok && !learned) learned = scale;
    }
    return ok;
}

struct Column {
    std::vector<double> values;
    std::vector<unsigned char> masks;
};

template<Strategy strategy,bool co2>
auto read_file(const char* path) {
    std::ifstream stream(path,std::ios::binary);
    if (!stream) throw std::runtime_error("open");
    std::string pending;
    if constexpr (co2) {
        if (!std::getline(stream,pending) || pending!="date,co2") throw std::runtime_error("header");
        pending.clear();
    }
    std::array<char,8192> block;
    constexpr size_t count = co2 ? 1 : 7;
    std::array<Column,count> output;
    std::array<int,count> scales{};
    while (stream.read(block.data(),block.size()) || stream.gcount()) {
        pending.append(block.data(),stream.gcount());
        auto last = pending.rfind('\n');
        if (last==std::string::npos) continue;
        const char* p = pending.data();
        const char* end = p+last+1;
        while (p<end) {
            p = skip_field(p,end,co2 ? ',' : ';');
            if constexpr (!co2) p = skip_field(p,end,';');
            for (size_t col=0;col<count;++col) {
                char stop = col+1==count ? '\n' : ';';
                Word word;
                if (!recognize<strategy,co2>(p,end,stop,scales[col],word)) {
                    auto start = p;
                    p = skip_field(p,end,stop);
                    size_t length = p-start-1;
                    if (stop=='\n' && length && start[length-1]=='\r') --length;
                    word = general<Fast>({start,length});
                }
                output[col].values.push_back(std::bit_cast<double>(word));
                output[col].masks.push_back(word==missing);
            }
        }
        pending.erase(0,last+1);
    }
    if (!stream.eof() || !pending.empty()) throw std::runtime_error("incomplete input");
    return output;
}

template<bool co2>
void run(Field mode,const char* path,const char* prefix) {
    const auto readers = std::array{read_file<Adaptive,co2>,read_file<Current,co2>,
        read_file<Static,co2>,read_file<General,co2>,read_file<Record,co2>};
    constexpr int arms = co2 ? 5 : 4;
    if (mode=="check") {
        for (int arm=0;arm<arms;++arm) {
            std::ofstream file(std::string(prefix)+labels[arm],std::ios::binary);
            for (auto& col:readers[arm](path)) {
                file.write(reinterpret_cast<const char*>(col.values.data()),8*col.values.size());
                file.write(reinterpret_cast<const char*>(col.masks.data()),col.masks.size());
            }
            if (!file) throw std::runtime_error("dump");
        }
        return;
    }
    for (int round=0;round<10;++round) for (int pos=0;pos<arms;++pos) {
        int arm = (pos+round)%arms;
        auto start = std::chrono::steady_clock::now();
        for (int pass=0;pass<8;++pass) {
            auto output = readers[arm](path);
            asm volatile("" : : "r"(&output) : "memory");
        }
        auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-start);
        std::cout<<round<<','<<pos<<','<<labels[arm]<<','<<ns.count()<<'\n';
    }
}
int main(int argc,char** argv) {
    if (argc!=5 || std::fegetround()!=FE_TONEAREST) return 2;
    if (Field(argv[2])=="co2") run<true>(argv[1],argv[3],argv[4]);
    else run<false>(argv[1],argv[3],argv[4]);
}
