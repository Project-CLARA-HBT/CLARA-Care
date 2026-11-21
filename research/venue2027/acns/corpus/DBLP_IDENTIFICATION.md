# DBLP identification for the attestation review

On 21 November 2026, the five registered Boolean queries yielded 78 distinct DBLP keys in the 20 November daily snapshot. The 1 November persistent release yielded 69. All 69 earlier keys occurred in the later result. Use the later 78 keys as screening candidates. Adding the two totals would double count every earlier match.

| Query | 1 November | 20 November |
|---|---:|---:|
| S1 Attestation | 2 | 2 |
| S2 Provenance | 63 | 71 |
| S3 Receipts | 0 | 0 |
| S4 Benchmark observability | 0 | 0 |
| S5 Supply-chain verification | 6 | 7 |

Some titles match two queries. The search inspected 3,992,890 titled records from publication years 2019–2026 in the first snapshot and 4,032,053 in the second. Each hit retains its DBLP key, matched queries and bibliographic metadata. [Persistent snapshot results](dblp_20261101_identification.json) · [Daily snapshot results](dblp_20261120_identification.json)

DBLP's XML distribution has a title field and omits author keywords and abstracts. The runner reads the verbatim quoted terms and Boolean groups from the registered protocol, folds case, collapses whitespace and requires whole phrases in the title. It applies no stemming. S3 and S4 zeroes are specific to this field and syntax. Indexing and the December cutoff can change the candidate set. Other registered indexes, cross-source deduplication, snowballing and independent screening remain open. The results carry no inclusion or agreement labels.

## Reproduction

For the persistent release, check the compressed file against the publisher's MD5, then run the command below using its dated DTD. Compare the resulting JSON with the first result linked above. Both JSON files include SHA-256 digests of the compressed distribution, DTD and selection protocol. The daily download changes over time. Its recorded digest identifies the particular copy used. [November release](https://doi.org/10.4230/dblp.xml.2026-11-01) · [Release DTD](https://doi.org/10.4230/dblp.xml.dtd.2023-06-28) · [DBLP daily distribution](https://dblp.org/xml/)

```sh
python3 -m evaluation.venue2027.acns.dblp_identification dblp-2026-11-01.xml.gz dblp-2023-06-28.dtd
```
