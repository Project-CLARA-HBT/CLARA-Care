# Can a proceedings catalogue trust DBLP modification dates?

**Decision, 21 November 2026. Drop the method paper.** A catalogue frozen on 1 November missed 132 proceedings and served two stale titles on 20 November. A date-change filter reproduced the later snapshot, but a simple inclusive date watermark reached the same answer with the same number of catalogue writes. It compared only two more retained payloads. These results close the investigation that replaced the ACNS manual-review proposal. [Machine-readable results](results.json)

## Population and outcome

We scanned both complete public XML files and selected every top-level `proceedings` record across all years. The user-visible operation is lookup by DBLP key. Its response contains the ordered title and year fields, including nested title text and decoded entities. Absent fields are empty lists. The identity rule is literal key equality. A renamed key would count as a disappearance and an appearance. The experiment requires no inferred work identity, clinical records, human ratings or security scenarios.

The earlier catalogue had 65,785 keys. All survived, and the later catalogue had 65,917. On retained keys, 87 modification dates changed and only two displayed payloads changed. Both title edits removed the repeated year immediately after “Proceedings of the” in the 2024 and 2025 ICAIE volumes. Both carried a 6 November modification date. An inventory of keys alone would miss both edits. The source documents establish what DBLP displayed at each endpoint. They do not establish which title the publisher considered correct or what was displayed between those dates. [Projected changes by DBLP key](projection_delta.json)

## Refresh comparison

Every incremental arm starts with the same old view, scans the same new inventory, inserts all new keys and deletes all vanished keys. Each eligible retained row gets an exact payload comparison before any write. The candidate uses the per-key date from both snapshots. The watermark uses only the later date and the date of the earlier release. A missing later date triggers comparison in both arms. The frozen control keeps the old catalogue. The full rebuild starts empty.

| Refresh | Retained payload comparisons | Catalogue row writes | Missing keys | Extra keys | Wrong payloads on shared keys |
|---|---:|---:|---:|---:|---:|
| Frozen | 0 | 0 | 132 | 0 | 2 |
| Reconcile keys only | 0 | 132 | 0 | 0 | 2 |
| Compare when later date ≥ 1 Nov | 89 | 134 | 0 | 0 | 0 |
| Compare when date differs (candidate) | 87 | 134 | 0 | 0 | 0 |
| Compare every retained payload | 65,785 | 134 | 0 | 0 | 0 |
| Rebuild from empty | 0 | 65,917 | 0 | 0 | 0 |

A write is one catalogue insert, update or delete. The 134 writes comprise 132 inserts and two title updates, the minimum for this keyed representation. Date comparisons, storing previous dates, XML parsing and I/O are outside the payload-comparison and write counts. All refresh inputs were fully parsed. A difference of two in-memory comparisons supplies no evidence of lower end-to-end runtime. Exact keyed differencing gives the same write count and remains correct even if a title changes under an unchanged date.

The independent oracle reads the later gzip and local DTD directly with Expat callbacks and constructs a fresh key-to-fields mapping. The refresh code reads lxml projections, and the oracle has its own selection and field assembly code. The scorer checks the actual missing, extra and unequal values along with a deterministic catalogue digest. A regression fixture exercises deletion, a backdated insertion and an edit hidden by an unchanged date. Fixture rows do not enter the observed counts. [Oracle](oracle.py) · [Scorer](compare.py) · [Regression cases](test_refresh.py)

## Prior work and venue decision

- Labio and Garcia-Molina formulated snapshot differencing for warehouse sources without change feeds in 1996. Exact keyed differencing is the relevant established baseline. We implement a direct keyed comparison and make no performance comparison with their compression or window algorithms. [VLDB paper](https://www.vldb.org/conf/1996/P063.PDF)
- Ley documented DBLP's XML data model. Ackermann and Reitz subsequently used historical DBLP curation to evaluate author-profile disambiguation. Their labels concerned author identity. This experiment measures reproduction of a later title/year lookup, for which the later dump supplies a direct reference. [Ley, PVLDB 2009](https://doi.org/10.14778/1687553.1687577) · [Ackermann and Reitz, 2018](https://arxiv.org/abs/1806.06017)
- Di Scala and colleagues tracked publication-metadata modifications across monthly Crossref archives. Their JCDL paper supplies direct precedent for longitudinal bibliographic change tracking and a more extensive history than this pair. [JCDL 2025 paper](https://doi.org/10.1109/JCDL67857.2025.00023)

Digital-library practitioners maintaining local replicas are the natural audience. JCDL covers this topic and has already published longitudinal metadata work. ACNS would require a security contribution. The narrow measurement here supports a reproducibility artifact. The one 19-day transition, two clustered title edits, absence of deletions, and strong baseline tie leave insufficient evidence for a standalone submission to either venue. Record-level percentages would conceal that both edits came from one conference series. [JCDL scope](https://www.jcdl.org/)

## Reproduce

Run from this directory with Python 3 and lxml. The recorded environment used Python 3.12.3, lxml 6.1.3, libxml2 2.14.6 and Expat 2.6.1. Keep each XML file and its own DTD in the same directory. The persistent November release and dated DTD can be downloaded again. The later file came from the rolling daily distribution. Its checksum identifies the required copy. [1 November release](https://doi.org/10.4230/dblp.xml.2026-11-01) · [Release DTD](https://doi.org/10.4230/dblp.xml.dtd.2023-06-28) · [Daily distribution](https://dblp.org/xml/)

```sh
set -eu
old=/tmp/clara-dblp-20261101
new=/tmp/clara-dblp-20261120
work=$(mktemp -d)
here=$PWD
(cd "$old" && sha256sum -c "$here/nov01.sha256")
(cd "$new" && sha256sum -c "$here/nov20.sha256")
python extract.py "$old/dblp-2026-11-01.xml.gz" > "$work/old.json"
python extract.py "$new/dblp.xml.gz" > "$work/new.json"
python oracle.py "$new/dblp.xml.gz" > "$work/oracle.json"
python compare.py "$work/old.json" "$work/new.json" "$work/oracle.json" "$work/results.json" "$work/delta.json"
cmp results.json "$work/results.json"
cmp projection_delta.json "$work/delta.json"
python -m pytest -q test_refresh.py
```

With only the persistent release, run the old extraction and then `python replay.py "$work/old.json"`. This reconstructs the exact later input **projection** using the committed public delta, checks both projection digests, and compares all six outcomes with the archived results and independent oracle receipt. Re-executing Expat against the original later XML requires the hash-matched daily file.
