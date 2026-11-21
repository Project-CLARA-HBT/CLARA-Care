#include "path.hpp"
#include <iostream>
#include <string>

int main(int argc, char** argv) {
    int k = argc == 2 ? std::stoi(argv[1]) : 10;
    std::string source, query;
    int n;
    while (std::cin >> source >> query >> n) {
        std::vector<int> left(n), right(n), positives;
        for (int i = 0; i < n; ++i) {
            int positive;
            if (!(std::cin >> left[i] >> right[i] >> positive)) return 1;
            if (positive) positives.push_back(i);
        }
        auto curves = directrank::rank_paths(left, right, positives, k);
        for (size_t i = 0; i < positives.size(); ++i) {
            std::cout << source << '\t' << query << '\t' << positives[i];
            for (auto [weight, rank] : curves[i])
                std::cout << '\t' << weight << ':' << rank;
            std::cout << '\n';
        }
    }
}
