// Fixed-point offline relevance-rank paths. Build with C++17.
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <numeric>
#include <random>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

constexpr int W = 65535, K = 10;
struct Row { int a, b, id; };
struct Query { std::string source, qid; std::vector<Row> rows; std::vector<Row> positives; };
using Change = std::pair<int,int>;
using Curve = std::vector<Change>;
using Output = std::vector<Curve>;
enum Mode { Sweep, BandSweep, Early, Clip, BandClip };

bool ahead(int v, int other, int id, int other_id) {
    return v > other || (v == other && id < other_id);
}

// In descending stable x order, at most nine earlier rows may dominate y.
std::vector<Row> band(const std::vector<Row>& rows) {
    auto sorted = rows;
    std::sort(sorted.begin(), sorted.end(), [](Row a, Row b){return ahead(a.a,b.a,a.id,b.id);});
    std::array<std::pair<int,int>,K> top;
    top.fill({-1,0});
    std::vector<Row> kept;
    for (Row r:sorted) {
        std::pair<int,int> key{r.b,-r.id};
        if (key <= top.back()) continue;
        kept.push_back(r);
        auto slot=std::lower_bound(top.begin(),top.end(),key,std::greater<>());
        std::move_backward(slot,top.end()-1,top.end());
        *slot=key;
    }
    return kept;
}

int kth(std::vector<int>& values, size_t i) {
    auto at=values.begin()+i;
    std::nth_element(values.begin(),at,values.end());
    return *at;
}

Curve path(const std::vector<Row>& rows, Row p, bool early, bool clip) {
    int fixed=0;
    std::vector<int> rises, falls;
    Curve changes{{0,K+1}};
    for (Row r:rows) {
        if (r.id==p.id) continue;
        bool left=ahead(r.a,p.a,r.id,p.id), right=ahead(r.b,p.b,r.id,p.id);
        if (left==right) {
            if (left && ++fixed>=K && early) return changes;
            continue;
        }
        int64_t origin=int64_t(r.a-p.a)*W;
        int slope=(r.b-p.b)-(r.a-p.a), threshold=(r.id<p.id)?0:1;
        if (right) rises.push_back((threshold-origin+slope-1)/slope);
        else falls.push_back((origin-threshold)/(-slope)+1);
    }
    if (fixed>=K) return changes;
    int lo=0, hi=W+1, room=K-fixed;
    if (clip) {
        if (int(falls.size())>=room) lo=kth(falls,falls.size()-room);
        if (int(rises.size())>=room) hi=kth(rises,room-1);
        if (lo>=hi) return changes;
    }
    int rank=1+fixed;
    std::vector<Change> events;
    for (int w:rises) {
        rank+=w<=lo;
        if (lo<w && w<hi) events.emplace_back(w,1);
    }
    for (int w:falls) {
        rank+=w>lo;
        if (lo<w && w<hi) events.emplace_back(w,-1);
    }
    auto record=[&](int w,int r){
        r=std::min(r,K+1);
        if (w==0) changes.front().second=r;
        else if (changes.back().second!=r) changes.emplace_back(w,r);
    };
    record(lo,rank);
    std::sort(events.begin(),events.end());
    size_t i=0;
    while (i<events.size()) {
        int at=events[i].first;
        do {rank+=events[i++].second;} while(i<events.size() && events[i].first==at);
        record(at,rank);
    }
    if (hi<=W) record(hi,K+1);
    return changes;
}

Output evaluate(const Query& q, Mode mode) {
    bool use_band=mode==BandSweep || mode==BandClip;
    auto filtered=use_band ? band(q.rows) : std::vector<Row>{};
    const auto& rivals=use_band ? filtered : q.rows;
    Output result;
    for (Row p:q.positives) {
        if (use_band && std::none_of(rivals.begin(),rivals.end(),[&](Row r){return r.id==p.id;}))
            result.push_back({{0,K+1}});
        else result.push_back(path(rivals,p,mode!=Sweep && mode!=BandSweep,mode==Clip || mode==BandClip));
    }
    return result;
}

int main(int argc,char** argv) {
    if (argc!=4) throw std::runtime_error("usage: path inputs.txt changes.tsv timings.csv");
    std::ifstream in(argv[1]); std::ofstream curves(argv[2]), times(argv[3]);
    if (!in || !curves || !times) throw std::runtime_error("file open failed");
    std::vector<Query> queries;
    int n;
    std::string source,id;
    while(in>>source>>id>>n) {
        Query q{source,id,{},{}};
        for(int i=0;i<n;++i) {
            int a,b,rel;
            if (!(in>>a>>b>>rel) || a<0 || a>W || b<0 || b>W || (rel!=0 && rel!=1))
                throw std::runtime_error("bad row");
            q.rows.push_back({a,b,i});
            if(rel) q.positives.push_back(q.rows.back());
        }
        queries.push_back(std::move(q));
    }
    std::vector<Output> expected;
    for (const auto& q:queries) {
        expected.push_back(evaluate(q,Sweep));
        for(size_t i=0;i<q.positives.size();++i) {
            curves<<q.source<<'\t'<<q.qid<<'\t'<<q.positives[i].id;
            for(auto [at,r]:expected.back()[i]) curves<<'\t'<<at<<':'<<r;
            curves<<'\n';
        }
    }
    times<<"source,round,position,method,ns\n";
    std::mt19937 rng(97123);
    for(size_t first=0;first<queries.size();) {
        size_t end=first+1;
        while(end<queries.size() && queries[end].source==queries[first].source) ++end;
        std::array<Mode,5> order={Sweep,BandSweep,Early,Clip,BandClip};
        for(int round=0;round<=12;++round) {
            std::shuffle(order.begin(),order.end(),rng);
            for(size_t pos=0;pos<order.size();++pos) {
                std::vector<Output> out;
                auto start=std::chrono::steady_clock::now();
                for(size_t j=first;j<end;++j) out.push_back(evaluate(queries[j],order[pos]));
                auto elapsed=std::chrono::steady_clock::now()-start;
                if (!std::equal(out.begin(),out.end(),expected.begin()+first))
                    throw std::runtime_error("path mismatch");
                if(round) times<<queries[first].source<<','<<round<<','<<pos<<','<<order[pos]<<','
                    <<std::chrono::duration_cast<std::chrono::nanoseconds>(elapsed).count()<<'\n';
            }
        }
        first=end;
    }
}
