#pragma once

#include <algorithm>
#include <cstdint>
#include <numeric>
#include <stdexcept>
#include <utility>
#include <vector>

namespace directrank {

using Curves = std::vector<std::vector<std::pair<int, int>>>;
constexpr int last_weight = 65535;

// Accessors expose score columns and positive indices from the caller's native
// layout. Row indices follow stable document-ID order; positives are distinct.
template<class Left, class Right, class PositiveId>
Curves rank_paths(int size, Left left, Right right, int positive_count,
                  PositiveId positive_id, int k = 10) {
    if (k <= 0 || size < 0 || positive_count < 0 || positive_count > size)
        throw std::invalid_argument("invalid rank path dimensions");
    const int count = std::min(k, size);
    Curves curves(positive_count, {{0, k + 1}});
    if (!positive_count) return curves;
    std::vector<int> positive_index(size, -1);
    for (int i = 0; i < positive_count; ++i) {
        int id = positive_id(i);
        if (id < 0 || id >= size || positive_index[id] != -1)
            throw std::invalid_argument("invalid positive document");
        positive_index[id] = i;
    }

    std::vector<int> order(size);
    std::iota(order.begin(), order.end(), 0);
    int weight = 0;
    auto score = [&](int id) {
        return std::int64_t(last_weight - weight) * left(id) + std::int64_t(weight) * right(id);
    };
    auto ahead = [&](int u, int v) {
        auto a = score(u), b = score(v);
        return a > b || (a == b && u < v);
    };
    // Assumes challenger follows incumbent at the current weight. Stable ID
    // determines whether a zero margin (tie) is sufficient to change order.
    auto crossing = [&](int incumbent, int challenger) {
        const int right_gap = int(right(challenger)) - int(right(incumbent));
        if (right_gap < 0 || (right_gap == 0 && challenger > incumbent))
            return last_weight + 1;
        const int initial_deficit = int(left(incumbent)) - int(left(challenger));
        const int slope = right_gap + initial_deficit;
        const auto numerator = std::int64_t(initial_deficit) * last_weight
                             + int(challenger > incumbent);
        return int((numerator + slope - 1) / slope);
    };

    std::partial_sort(order.begin(), order.begin() + count, order.end(), ahead);
    auto publish = [&](int id, int rank) {
        int index = positive_index[id];
        if (index < 0) return;
        auto &curve = curves[index];
        if (weight == 0) curve.front().second = rank;
        else if (curve.back().second != rank) curve.emplace_back(weight, rank);
    };
    for (int i = 0; i < count; ++i) publish(order[i], i + 1);

    std::vector<int> previous(count);
    while (weight < last_weight) {
        int internal = last_weight + 1;
        for (int i = 1; i < count; ++i)
            internal = std::min(internal, crossing(order[i-1], order[i]));

        const int boundary = order[count-1];
        int entry = last_weight + 1;
        int entry_position = -1;
        int simultaneous_entries = 0;
        for (int i = count; i < size; ++i) {
            int candidate = crossing(boundary, order[i]);
            if (candidate < entry) {
                entry = candidate;
                entry_position = i;
                simultaneous_entries = 1;
            } else if (candidate == entry) {
                ++simultaneous_entries;
            }
        }
        int next = std::min(internal, entry);
        if (next > last_weight) break;
        if (next <= weight) throw std::logic_error("stale DirectRank event");
        weight = next;
        std::copy_n(order.begin(), count, previous.begin());

        if (entry < internal && simultaneous_entries == 1) {
            // A single entrant displaces the old boundary. On a finite grid it
            // may leap several positions between consecutive integer weights.
            std::swap(order[entry_position], order[count-1]);
            auto position = std::lower_bound(order.begin(), order.begin()+count-1,
                                             order[count-1], ahead);
            std::rotate(position, order.begin()+count-1, order.begin()+count);
        } else if (internal < entry) {
            std::sort(order.begin(), order.begin()+count, ahead);
            // If the old boundary rose, an outsider below it may outrank the
            // new bottom even though it did not overtake the old one.
            if (order[count-1] != boundary)
                std::partial_sort(order.begin(), order.begin()+count, order.end(), ahead);
        } else {
            // Multiple outsiders, or simultaneous internal and external events.
            std::partial_sort(order.begin(), order.begin()+count, order.end(), ahead);
        }
        for (int i = 0; i < count; ++i) publish(order[i], i + 1);
        for (int id : previous) {
            if (positive_index[id] >= 0 &&
                std::find(order.begin(), order.begin()+count, id) == order.begin()+count)
                publish(id, k + 1);
        }
    }
    return curves;
}

template<class ScoreColumn>
Curves rank_paths(const ScoreColumn& left, const ScoreColumn& right,
                  const std::vector<int>& positives, int k = 10) {
    if (left.size() != right.size()) throw std::invalid_argument("different score column sizes");
    return rank_paths(int(left.size()), [&](int i) { return left[i]; },
                      [&](int i) { return right[i]; }, int(positives.size()),
                      [&](int i) { return positives[i]; }, k);
}

} // namespace directrank
