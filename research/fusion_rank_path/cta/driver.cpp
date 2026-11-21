#include "lp_cta.hpp"
#include <iostream>

int main() {
    int n, m, k, last;
    while (std::cin >> n >> m >> k >> last) {
        if (n < 1 || m < 0 || m > n) return 1;
        struct Row {int a, b;};
        std::vector<Row> rows(n);
        for (auto& row : rows) if (!(std::cin >> row.a >> row.b)) return 1;
        std::vector<int> positives(m);
        for (auto& id : positives) if (!(std::cin >> id)) return 1;
        for (const auto& curve : rank_path_cta::evaluate(rows, positives, k, last)) {
            for (auto [w, r] : curve) std::cout << w << ':' << r << ' ';
            std::cout << '\n';
        }
    }
}
