# What two chunks reveal about Unicode normalization tests

## Abstract

Can a data pipeline tell from a chunk boundary whether two separately normalized strings can be concatenated directly? We evaluated ten decision rules on every interior code-point split of the explicit Unicode 15.1 normalization conformance cases. The suite supplies expected whole-string outputs. In NFC, a rule that accepted a join when the first code point on the right had combining class zero failed at 2 of 9,551 splits drawn from source columns. Using all five columns as inputs, as permitted by the suite, exposed 22,112 failures in 45,960 splits. A different shortcut, checking the adjacent pair, failed at 1,636 splits in each composed form and zero in either decomposed form. ICU boundary predicates made zero incorrect decisions to accept but sent many already-correct joins to repair. A bounded context check recovered all safe joins at four code points per side on this file. The suite contains only 17 splits per form from strings longer than eight code points, a substantial limit on interpreting that last result.

## Question and related work

Text ingestion systems may receive one logical string in several chunks. Normalizing each chunk leaves a decision at the join. Reordering may cross the cut, and a starter on the left can compose with a later mark on the right. A caller can always submit the join to a normalizer. We ask how often a decision based on its edges can rule out that work, how often shortcuts return incorrect output, and how sensitive those counts are to the way the conformance file is read.

Unicode Standard Annex #15 already describes concatenation failures in §1.4, the use of stable code points in §9.1, and normalizing the region around a join. Scherer’s technical note gives an adjacent combining-class test for ordered canonical decompositions and discusses incremental FCD checks. These results motivate separate analysis of composed and decomposed forms. [Unicode Normalization Forms, revision 54](https://www.unicode.org/reports/tr15/tr15-54.html) · [Canonical Equivalence in Applications](https://www.unicode.org/notes/tn5/)

ICU exposes context-independent boundaries on either side of a code point and an operation for appending a second normalized string. Van Lohuizen describes a practical Go example in which a substring match must respect normalization boundaries. Our contribution is an empirical comparison of join decisions and of two ways to enumerate the labeled inputs. The underlying boundary operations are established software techniques. [ICU 74.2 Normalizer2 interface](https://github.com/unicode-org/icu/blob/release-74-2/icu4c/source/common/unicode/unorm2.h) · [Text normalization in Go](https://go.dev/blog/normalization)

## Materials and methods

We treated the public Unicode 15.1 conformance file as development data. Its 19,074 explicit rows contain the source string and four normalized versions. Its header specifies, for example, that NFC maps each of the first three columns to the second, and each of the final two to the fourth. We applied the corresponding published equivalences for all four forms. Within a form, deduplication yielded 36,482 distinct inputs, of which 17,694 have an interior split. Identical inputs had consistent labels. We evaluated all 45,960 interior split positions per form. The source-only sensitivity includes an input whenever it appears in the first column of any row. Implicit single-code-point identity cases have no interior cut. [NormalizationTest-15.1.0.txt](https://www.unicode.org/Public/15.1.0/ucd/NormalizationTest.txt)

For a cut, let L and R be the two independently normalized halves, produced by ICU 74.2. Direct acceptance returns their concatenation. Repair normalizes that concatenation in the same form. Exact code-point equality to the published target scores each decision. We verified both whole-input normalization and every repair against the target. This separates the file-based correctness label from ICU's decision about where repair might be needed.

The controls always accept, always repair, or ask ICU whether the full join is already normalized. The starter rule accepts when the first code point of R has canonical combining class zero. The pair rule asks ICU whether the last code point of L followed by the first of R is normalized. The right-boundary rule uses ICU's boundary-before predicate on R. The either-boundary rule also accepts when the last character of L has a boundary after it.

Three additional rules begin with the either-boundary test. If it fails, they search outward for a certified boundary or a string end on each side, allowing a window of at most one, two, or four code points per side. They accept when both endpoints are certified and ICU finds the enclosed text normalized. Certified endpoints permit independent normalization inside and outside the window. Outside text comes from the normalized halves, and contiguous substrings preserve normalization. Failure to find both endpoints sends the join to repair. The budget limits the text submitted to the window normalization check. Testing its endpoints may also inspect a neighboring code point.

We counted incorrect direct joins and unnecessary repairs. All policies see exactly the same splits. Positions within a row and the four forms share inputs, so we report paired census counts without independent-sample confidence intervals. The pre-run design and executable definitions are available in the [experiment specification](design.md) and [comparison program](compare.py).

## Results

**NFC decisions on the same 45,960 splits.** Of these, 15,510 would produce the expected output by direct concatenation. An incorrect direct join returns the wrong string. An unnecessary repair returns the right string after an avoidable normalization call.

| Rule | Direct joins | Incorrect direct joins | Unnecessary repairs |
|---|---:|---:|---:|
| Always repair | 0 | 0 | 15,510 |
| Always direct | 45,960 | 30,450 | 0 |
| Combining class zero | 28,206 | 22,112 | 9,416 |
| Normalized adjacent pair | 17,146 | 1,636 | 0 |
| ICU boundary before right | 5,834 | 0 | 9,676 |
| ICU boundary on either side | 5,980 | 0 | 9,530 |
| Certified window, one per side | 6,025 | 0 | 9,485 |
| Certified window, two per side | 7,724 | 0 | 7,786 |
| Certified window, four per side | 15,510 | 0 | 0 |
| Whole-join check | 15,510 | 0 | 0 |

**Input selection changes the apparent defect rate.** On source-column inputs, the combining-class rule returned 2 incorrect results among 2,027 accepted NFC joins (0.10%). On all eligible inputs it returned 22,112 among 28,206 (78.4%). A post hoc count found that 21,954 of the 22,110 additional failures involved strings appearing exclusively in derived columns and consisting entirely of Hangul Jamo (U+1100–U+11FF). Decomposing a Hangul syllable exposes internal cuts where the right Jamo can compose with the left despite its zero combining class. A separate two-code-point example involves Bengali vowel signs. Joining U+09C7 and U+09BE directly misses the expected U+09CB. The test expansion changes which boundaries are exposed and the relative weight assigned to script-specific patterns. [Grouped counts](results/counts.csv) · [Counterexamples](results/audit.json)

**The adjacent pair behaves differently across forms.** The counts below use all inputs. “Safe” counts joins equal to the file target before repair. The final column counts such safe joins that the either-boundary rule sent to repair.

| Form | Safe joins | Incorrect direct joins under the pair rule | Safe joins missed by the pair rule | Safe joins missed by either-boundary |
|---|---:|---:|---:|---:|
| NFC | 15,510 | 1,636 | 0 | 9,530 |
| NFKC | 15,519 | 1,636 | 0 | 9,539 |
| NFD | 39,962 | 0 | 0 | 6,753 |
| NFKD | 39,962 | 0 | 0 | 6,762 |

For NFC, split the sequence U+0044 U+031B U+0307 immediately after the D. The D and the following horn are a normalized pair. The later dot above still composes with D, giving U+1E0A U+031B. The pair test misses that interaction. In the decomposed forms the halves are already decomposed and internally ordered, so ordering across their adjacent ends is the remaining condition. This accounts for the pair rule's different behavior. [Observed examples](results/audit.json)

**A wider window recovered more joins but often checked the entire string.** In NFC the four-per-side rule accepted 9,530 correct joins beyond the either-boundary rule. In 23,816 cases its normalization check covered the full joined text. Only 530 of those checks accepted, leaving 23,286 cases that incurred a full check followed by repair. On source-column inputs alone the same rule accepted all 3,565 safe NFC joins, including 337 accepted after a whole-window check. All 17 splits of inputs longer than eight were already certified by an immediate boundary in every form. This suite therefore supplies little evidence about the budget on long, context-dependent inputs.

## Interpretation and limitations

A source-column test alone substantially understates the failures of the starter shortcut on this development suite. Reporting failures per accepted join as well as total attempted joins matters because conservative rules can obtain perfect output by sending everything to repair. The adjacent-pair counterexample gives a small regression case for composition across a mark.

The four-code-point result describes this version's explicit examples. Arbitrarily long runs of combining marks can separate a cut from a certified endpoint. A fixed window then falls back to repair even when the text happens to be normalized. The corpus is a standards conformance fixture, with deliberate coverage of decompositions and ordering cases. Its code-point cuts provide neither a production chunk-size distribution nor text-frequency weights. The experiment also assumes valid decoded Unicode, two chunks, a single ICU version and a complete expected output. Runtime and memory costs depend on library internals, encoding and caller buffering. The observed count of avoided calls cannot establish a speedup over ICU's native normalized append.

For this developer-facing use case, the most informative evidence is the change in exposed failures when every already-labeled representation is used, together with the observed cost of conservative boundary decisions. The generality of the measured rates and the performance of bounded inspection on application streams remain open. [Reproduction instructions](README.md) · [Machine-readable results](results/counts.csv)
