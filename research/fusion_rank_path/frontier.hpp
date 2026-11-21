// Included after the scalar reference implementations for the AVX2 study.
#include <immintrin.h>

struct Endpoints {
    std::vector<int> left, right;
    explicit Endpoints(const std::vector<Row>& rows) {
        const size_t padded = (rows.size() + 7) / 8 * 8;
        left.assign(padded, -1);
        right.assign(padded, -1);
        for (Row r : rows) {
            left[r.id] = r.a;
            right[r.id] = r.b;
        }
    }
};

// Keep the k smallest keys. Negate falling crossing weights to keep the latest.
struct Smallest {
    std::array<int,K> keys;
    int size = 0;

    bool insert(int value) {
        if (size == K && value >= keys.back()) return false;
        auto end = keys.begin() + size;
        auto slot = std::lower_bound(keys.begin(), end, value);
        if (size == K) --end;
        else ++size;
        std::move_backward(slot, end, end + 1);
        *slot = value;
        return true;
    }
};

Curve emit_path(int fixed, const std::vector<int>& up, const std::vector<int>& down) {
    std::vector<Change> changes;
    changes.reserve(up.size() + down.size());
    for (int w : up) changes.emplace_back(w, 1);
    for (int w : down) changes.emplace_back(w, -1);
    std::sort(changes.begin(), changes.end());
    int rank = fixed + 1 + static_cast<int>(down.size());
    Curve result{{0, std::min(rank, K + 1)}};
    for (size_t i = 0; i < changes.size();) {
        int weight = changes[i].first;
        do {
            rank += changes[i++].second;
        } while (i < changes.size() && changes[i].first == weight);
        int clipped = std::min(rank, K + 1);
        if (result.back().second != clipped) result.emplace_back(weight, clipped);
    }
    return result;
}

template<bool bounded, bool check_prefix>
Curve vector_path(const Endpoints& cols, Row p) {
    const __m256i left = _mm256_set1_epi32(p.a), right = _mm256_set1_epi32(p.b);
    const __m256i offsets = _mm256_setr_epi32(0, 1, 2, 3, 4, 5, 6, 7);
    int fixed = 0;
    Smallest earliest, latest;
    std::vector<int> up, down;
    for (size_t base = 0; base < cols.left.size(); base += 8) {
        auto ids = _mm256_add_epi32(_mm256_set1_epi32(static_cast<int>(base)), offsets);
        auto tie = _mm256_cmpgt_epi32(_mm256_set1_epi32(p.id), ids);
        auto a = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(cols.left.data() + base));
        auto b = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(cols.right.data() + base));
        auto better_a = _mm256_cmpgt_epi32(a, _mm256_add_epi32(left, tie));
        auto better_b = _mm256_cmpgt_epi32(b, _mm256_add_epi32(right, tie));
        int lmask = _mm256_movemask_ps(_mm256_castsi256_ps(better_a));
        int rmask = _mm256_movemask_ps(_mm256_castsi256_ps(better_b));
        int both = lmask & rmask;
        fixed += __builtin_popcount(static_cast<unsigned>(both));
        if (fixed >= K) return {{0, K + 1}};
        int moving = lmask ^ rmask;
        bool changed = both != 0;
        while (moving) {
            int lane = __builtin_ctz(static_cast<unsigned>(moving));
            moving &= moving - 1;
            int id = static_cast<int>(base) + lane;
            int delta = cols.left[id] - p.a;
            int slope = (cols.right[id] - p.b) - delta;
            int threshold = id < p.id ? 0 : 1;
            int64_t origin = int64_t(delta) * W;
            if (rmask & (1 << lane)) {
                int crossing = static_cast<int>((threshold - origin + slope - 1) / slope);
                if constexpr (bounded) changed |= earliest.insert(crossing);
                else up.push_back(crossing);
            } else {
                int crossing = static_cast<int>((origin - threshold) / -slope + 1);
                if constexpr (bounded) changed |= latest.insert(-crossing);
                else down.push_back(crossing);
            }
        }
        if constexpr (check_prefix) {
            int room = K - fixed;
            if (changed && earliest.size >= room && latest.size >= room &&
                earliest.keys[room - 1] <= -latest.keys[room - 1])
                return {{0, K + 1}};
        }
    }
    if constexpr (bounded) {
        up.assign(earliest.keys.begin(), earliest.keys.begin() + earliest.size);
        for (int i = 0; i < latest.size; ++i) down.push_back(-latest.keys[i]);
    }
    return emit_path(fixed, up, down);
}

Output vector_evaluate(const Query& query, int mode) {
    Endpoints columns(query.rows);
    Output result;
    for (Row p : query.positives) {
        if (mode == 5) result.push_back(vector_path<false, false>(columns, p));
        else if (mode == 6) result.push_back(vector_path<true, false>(columns, p));
        else result.push_back(vector_path<true, true>(columns, p));
    }
    return result;
}
