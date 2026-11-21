#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <numeric>
#include <stdexcept>
#include <utility>
#include <vector>

namespace rank_path_cta {
using Curve = std::vector<std::pair<int, int>>;
using Output = std::vector<Curve>;

struct Point {
    int a, b, id;
};

struct Interval {
    int first, last;
};

// A corner's ID is also extremal so it bounds the stable ordering under ties.
struct Group {
    Point worst, best;
    int first, end, count;
    bool leaf;
};

inline bool precedes(Point row, Point focal, int w, int last) {
    const auto diff = std::int64_t(row.a - focal.a) * (last - w)
                    + std::int64_t(row.b - focal.b) * w;
    return diff > 0 || (diff == 0 && row.id < focal.id);
}

inline int as_id(int id) { return id; }
template<class T> int as_id(const T& row) { return row.id; }

class Index {
    static constexpr int fanout = 16;
    const std::vector<Point> points;
    std::vector<int> skyline_order, packed_order;
    std::vector<Group> tree;
    int last, k;

    static void extend(Group& box, Point worst, Point best) {
        box.worst = {std::min(box.worst.a, worst.a), std::min(box.worst.b, worst.b),
                     std::max(box.worst.id, worst.id)};
        box.best = {std::max(box.best.a, best.a), std::max(box.best.b, best.b),
                    std::min(box.best.id, best.id)};
    }

    void pack() {
        packed_order = skyline_order;
        const int n = static_cast<int>(points.size());
        const int leaves = (n + fanout - 1) / fanout;
        const int stripes = static_cast<int>(std::ceil(std::sqrt(leaves)));
        const int width = fanout * ((leaves + stripes - 1) / stripes);
        for (int i = 0; i < n; i += width) {
            std::sort(packed_order.begin() + i, packed_order.begin() + std::min(n, i + width),
                      [&](int a, int b) { return points[a].b > points[b].b; });
        }
        for (int i = 0; i < n; i += fanout) {
            const int end = std::min(i + fanout, n);
            Point first = points[packed_order[i]];
            Group box{first, first, i, end, end - i, true};
            for (int j = i + 1; j < end; ++j) {
                Point p = points[packed_order[j]];
                extend(box, p, p);
            }
            tree.push_back(box);
        }
        for (int start = 0, end = leaves; end - start > 1;) {
            for (int i = start; i < end; i += fanout) {
                int stop = std::min(i + fanout, end);
                Group box{tree[i].worst, tree[i].best, i, stop, 0, false};
                for (int j = i; j < stop; ++j) {
                    extend(box, tree[j].worst, tree[j].best);
                    box.count += tree[j].count;
                }
                tree.push_back(box);
            }
            start = end;
            end = static_cast<int>(tree.size());
        }
    }

    // Algorithm 3 look-ahead. Optimize the linear score difference at the two
    // endpoints to certify a whole group's contribution for every weight.
    void bound(int node, Point focal, Interval cell, int& lower, int& upper) const {
        const Group& g = tree[node];
        if (precedes(g.worst, focal, cell.first, last) &&
            precedes(g.worst, focal, cell.last, last)) {
            lower += g.count;
            upper += g.count;
            return;
        }
        if (!precedes(g.best, focal, cell.first, last) &&
            !precedes(g.best, focal, cell.last, last)) return;
        if (!g.leaf) {
            for (int j = g.first; j < g.end && lower <= k; ++j)
                bound(j, focal, cell, lower, upper);
            return;
        }
        for (int j = g.first; j < g.end && lower <= k; ++j) {
            const Point p = points[packed_order[j]];
            bool left = precedes(p, focal, cell.first, last);
            bool right = precedes(p, focal, cell.last, last);
            lower += left && right;
            upper += left || right;
        }
    }

    // First integer weight with the right-end ordering. End orders must differ.
    int crossing(Point row, Point focal, bool moves_ahead) const {
        const auto origin = std::int64_t(row.a - focal.a) * last;
        const int slope = (row.b - focal.b) - (row.a - focal.a);
        const int threshold = row.id < focal.id ? 0 : 1;
        if (moves_ahead)
            return static_cast<int>((threshold - origin + slope - 1) / slope);
        return static_cast<int>((origin - threshold) / -slope + 1);
    }

public:
    Index(std::vector<Point> data, int limit, int max_weight)
        : points(std::move(data)), skyline_order(points.size()), last(max_weight), k(limit) {
        if (k < 1 || last < 1 || last > 65535)
            throw std::invalid_argument("invalid cutoff or weight range");
        std::iota(skyline_order.begin(), skyline_order.end(), 0);
        std::sort(skyline_order.begin(), skyline_order.end(), [&](int i, int j) {
            if (points[i].a != points[j].a) return points[i].a > points[j].a;
            return i < j;
        });
        if (!points.empty()) pack();
    }

    Curve path(int id) const {
        const Point focal = points.at(id);
        std::vector<bool> removed(points.size()), seen(points.size());
        removed[id] = true;
        std::vector<Interval> pending{{0, last}};
        Curve finished;
        while (!pending.empty()) {
            // Recompute the current 2D skyline, retaining the processed pivots.
            std::vector<int> skyline, cuts;
            std::pair<int, int> best_b{-1, 0};
            for (int j : skyline_order) {
                if (removed[j]) continue;
                const Point p = points[j];
                const auto key = std::make_pair(p.b, -p.id);
                if (key <= best_b) continue;
                best_b = key;
                skyline.push_back(j);
                if (seen[j]) continue;
                seen[j] = true;
                bool left = precedes(p, focal, 0, last);
                bool right = precedes(p, focal, last, last);
                if (left != right) cuts.push_back(crossing(p, focal, right));
            }
            std::sort(cuts.begin(), cuts.end());
            cuts.erase(std::unique(cuts.begin(), cuts.end()), cuts.end());
            std::vector<Interval> unresolved;
            auto classify = [&](Interval cell) {
                int lower = 1, upper = 1;
                bound(static_cast<int>(tree.size()) - 1, focal, cell, lower, upper);
                if (lower > k || lower == upper)
                    finished.emplace_back(cell.first, std::min(lower, k + 1));
                else
                    unresolved.push_back(cell);
            };
            for (Interval cell : pending) {
                auto cut = std::upper_bound(cuts.begin(), cuts.end(), cell.first);
                for (; cut != cuts.end() && *cut <= cell.last; ++cut) {
                    classify({cell.first, *cut - 1});
                    cell.first = *cut;
                }
                classify(cell);
            }
            pending = std::move(unresolved);
            if (pending.empty()) break;

            // The union of non-pivots over all live cells can be tested at
            // the two outermost endpoints since pairwise scores are affine.
            bool advanced = false;
            for (int j : skyline) {
                Point p = points[j];
                if (precedes(p, focal, pending.front().first, last) ||
                    precedes(p, focal, pending.back().last, last)) {
                    removed[j] = true;
                    advanced = true;
                }
            }
            if (!advanced) throw std::logic_error("unresolved cell without a non-pivot");
        }
        std::sort(finished.begin(), finished.end());
        Curve curve;
        for (auto change : finished)
            if (curve.empty() || curve.back().second != change.second) curve.push_back(change);
        return curve;
    }
};

// rows are in ascending stable document-ID order with .a, .b in [0,65535].
// Positives may be integer row indices or rows with .id equal to that index.
template<class Rows, class Positives>
Output evaluate(const Rows& rows, const Positives& positives, int k = 10, int last = 65535) {
    std::vector<Point> data;
    data.reserve(rows.size());
    for (const auto& row : rows)
        data.push_back({row.a, row.b, static_cast<int>(data.size())});
    Index index(std::move(data), k, last);
    Output result;
    result.reserve(positives.size());
    for (const auto& p : positives) result.push_back(index.path(as_id(p)));
    return result;
}
}  // namespace rank_path_cta
