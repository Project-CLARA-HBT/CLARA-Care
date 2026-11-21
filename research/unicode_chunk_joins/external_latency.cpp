// Supplemental hot-buffer timing for the exact natural-text cuts exported by external.py.
#include <unicode/unorm2.h>
#include <unicode/utf16.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

using Text = std::u16string;
struct Cut {
    Text left, right, raw, expected;
    bool accepted;
};

Text decode(const std::string& hex) {
    Text text;
    for (size_t i = 0; i < hex.size(); i += 4) {
        int lo = std::stoi(hex.substr(i, 2), nullptr, 16);
        int hi = std::stoi(hex.substr(i + 2, 2), nullptr, 16);
        text.push_back(static_cast<char16_t>((hi << 8) | lo));
    }
    return text;
}

void check(UErrorCode err) {
    if (U_FAILURE(err)) throw std::runtime_error(u_errorName(err));
}

bool boundary(const UNormalizer2* norm, UChar32 a, UChar32 b) {
    return unorm2_hasBoundaryAfter(norm, a) || unorm2_hasBoundaryBefore(norm, b);
}

bool accept(const UNormalizer2* norm, bool composed, const Text& left, std::u16string_view right) {
    int i = left.size(), j = 0;
    UChar32 a, b;
    U16_PREV(left, 0, i, a);
    U16_NEXT(right, j, static_cast<int>(right.size()), b);
    if (!composed) {
        auto c = u_getCombiningClass(b);
        return c == 0 || u_getCombiningClass(a) <= c;
    }
    if (boundary(norm, a, b)) return true;
    for (int n = 1; i > 0; ++n) {
        int prev = i;
        UChar32 cp;
        U16_PREV(left, 0, prev, cp);
        if (boundary(norm, cp, a)) break;
        if (n == 4) return false;
        a = cp;
        i = prev;
    }
    for (int n = 1; j < static_cast<int>(right.size()); ++n) {
        int next = j;
        UChar32 cp;
        U16_NEXT(right, next, static_cast<int>(right.size()), cp);
        if (boundary(norm, b, cp)) break;
        if (n == 4) return false;
        b = cp;
        j = next;
    }
    char16_t sample[16];
    auto mid = std::copy(left.begin() + i, left.end(), sample);
    auto end = std::copy_n(right.begin(), j, mid);
    UErrorCode err = U_ZERO_ERROR;
    bool normalized = unorm2_isNormalized(norm, sample, end - sample, &err);
    check(err);
    return normalized;
}

enum Method { Append, Guarded, Stream, NormalizeThenGuard };

int run(Method m, const UNormalizer2* norm, bool composed, const Cut& cut,
        Text& dest, Text& scratch) {
    UErrorCode err = U_ZERO_ERROR;
    auto pos = std::copy(cut.left.begin(), cut.left.end(), dest.begin());
    if (m == Stream) {
        int n = unorm2_normalizeSecondAndAppend(norm, dest.data(), cut.left.size(), dest.size(),
                                               cut.raw.data(), cut.raw.size(), &err);
        check(err);
        return n;
    }
    std::u16string_view right(cut.right);
    if (m == NormalizeThenGuard) {
        int n = unorm2_normalize(norm, cut.raw.data(), cut.raw.size(),
                                 scratch.data(), scratch.size(), &err);
        check(err);
        right = std::u16string_view(scratch.data(), n);
    }
    if (m != Append && accept(norm, composed, cut.left, right)) {
        return std::copy(right.begin(), right.end(), pos) - dest.begin();
    }
    int n = unorm2_append(norm, dest.data(), cut.left.size(), dest.size(),
                          right.data(), right.size(), &err);
    check(err);
    return n;
}

int main() {
    std::map<std::array<std::string, 3>, std::vector<Cut>> groups;
    for (std::string line; std::getline(std::cin, line);) {
        std::istringstream in(line);
        std::string lang, rendering, length, form, left, right, raw, expected;
        bool accepted;
        if (!(in >> lang >> rendering >> length >> form >> accepted >> left >> right >> raw >> expected))
            throw std::runtime_error("bad input row");
        groups[{lang, rendering, form}].push_back(
            {decode(left), decode(right), decode(raw), decode(expected), accepted});
    }
    if (groups.size() != 16) throw std::runtime_error("incomplete natural-text input");
    const char* names[] = {"append", "guarded", "stream", "normalize_then_guard"};
    std::cout << "corpus,rendering,form,round,method,ns_per_cut\n";
    uint64_t checksum = 0;
    for (const auto& [key, cuts] : groups) {
        UErrorCode err = U_ZERO_ERROR;
        bool composed = key[2].back() == 'C';
        auto norm = unorm2_getInstance(nullptr, key[2].starts_with("NFK") ? "nfkc" : "nfc",
                                       composed ? UNORM2_COMPOSE : UNORM2_DECOMPOSE, &err);
        check(err);
        size_t capacity = 0;
        for (const auto& cut : cuts)
            capacity = std::max(capacity, cut.left.size() + cut.right.size() + cut.raw.size()
                                          + cut.expected.size() + 1);
        Text dest(capacity, 0), scratch(capacity, 0);
        for (const auto& cut : cuts) {
            if (accept(norm, composed, cut.left, cut.right) != cut.accepted)
                throw std::runtime_error("guard disagrees with Python enumeration");
            for (auto m : {Append, Guarded, Stream, NormalizeThenGuard}) {
                int n = run(m, norm, composed, cut, dest, scratch);
                if (dest.compare(0, n, cut.expected) != 0) throw std::runtime_error("wrong output");
            }
        }
        for (int round = 0; round < 8; ++round) {
            for (int idx = 0; idx < 4; ++idx) {
                Method m = static_cast<Method>((round + idx) % 4);
                auto start = std::chrono::steady_clock::now();
                for (int repeat = 0; repeat < 16; ++repeat)
                    for (const auto& cut : cuts) {
                        int n = run(m, norm, composed, cut, dest, scratch);
                        checksum += n + dest[n - 1];
                    }
                auto elapsed = std::chrono::steady_clock::now() - start;
                double ns = std::chrono::duration<double, std::nano>(elapsed).count();
                std::cout << key[0] << ',' << key[1] << ',' << key[2] << ',' << round << ','
                          << names[m] << ',' << ns / (16 * cuts.size()) << '\n';
            }
        }
    }
    std::cerr << "checksum " << checksum << '\n';
}
