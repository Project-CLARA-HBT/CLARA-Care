# External development replay on SGD dialogue states

The provenance cache preserved 305 authorized projections that coarse purge had to rebuild. The two caches and always-recompute delivered identical payload and cancellation streams. B4 had the highest elapsed time in each round. For these cheap single-field reads, the experiment supports a cache-retention benefit only.

## Workload and rights

All 128 dialogues in the first SGD training shard contributed. Their 1,233 user turns contained 5,177 annotated state-slot occurrences and 1,155 distinct within-dialogue field versions. Turn order, co-occurrence, repeated state and value changes come from the external annotation. Each slot occurrence was interpreted as one dispatch. The service-slot purpose, midpoint revocation, two-node provenance path, 32-byte marker and local transport were assigned by this study. The corpus supplies neither consent labels nor observed cache traffic. Dialogues are single conversations, with no assertion of distinct people or longitudinal visits. This shard was selected by filename before comparing the arms. Source frequency and the position of the revoked slot can affect the hit contrast.

Google's Schema-Guided Dialogue dataset is credited to Abhinav Rastogi, Xiaoxue Zang, Srinivas Sunkara, Raghav Gupta and Pranav Khaitan, *Towards Scalable Multi-domain Conversational Agents*, AAAI 2020. The adapted workload in this directory, including the shape and its trace derivatives, is distributed under CC BY-SA 4.0. The transformation retains within-dialogue ordinals and replaces source values with markers. The archive contains no upstream utterances or slot strings. Only train/dialogues_001.json was used. SGD validation/test and LongMemEval were left unopened. [Upstream dataset and attribution](https://github.com/google-research-datasets/dstc8-schema-guided-dialogue/blob/e852981ae34990f4358979625854259302feaa78/README.md#license) · [Pinned license](https://github.com/google-research-datasets/dstc8-schema-guided-dialogue/blob/e852981ae34990f4358979625854259302feaa78/LICENSE.txt) · [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)

## Paired outcomes

Each row below uses the same 4,531 authorized requests as its hit denominator. All arms delivered 144,992/144,992 authorized bytes and cancelled precisely the 646 forbidden requests. All 128 dialogues contained a request for a withdrawn field. After the barrier the receiver observed 102,112/102,112 authorized bytes and zero forbidden bytes across 3,837 requests per arm. Zero dialogues had a post-revocation disclosure. Each run started with empty caches.

| Arm | Authorized hits | Hit rate | Authorized rebuilds | Median process wall time, ms | Median of round p95 send times, µs |
| --- | ---: | ---: | ---: | ---: | ---: |
| B1 subject-wide purge | 3,073 | 67.82% | 1,458 | 110.9 | 1.82 |
| B2 always recompute | 0 | 0% | 4,531 | 105.7 | 1.66 |
| B4 provenance cache | 3,378 | 74.55% | 1,153 | 159.9 | 25.55 |

The pooled B4–B1 difference was 6.73 percentage points. All 305 additional hits occurred after withdrawal. B4 recorded more hits in 127 dialogues and tied in one. Hits and builds use sender instrumentation. The observer independently classified payload bytes and reconciled cancellations. Three cold serial rotations on an Intel Xeon E5-2696 v4 produced the timing medians. Process time includes Python startup, reading the local shape, building indices, revocation, dispatch, writing instrumentation and teardown. Send time spans policy application through the pipe write. Shape extraction, receiver scoring and network/model inference are outside both timing scopes. Reconstruction resolves a local field and copies its marker. Neither mechanism was tuned after collection.

The identical egress traces provide no evidence of a disclosure advantage over B2. The higher B4 hit rate did not yield lower wall time. The registered density interaction, confidence gates, external B3 parity and source-disjoint confirmatory experiment remain open. These descriptive results do not establish the registered RQ3 benefit. [Development protocol](../../../../research/venue2027/popets/protocols/sgd_development.md) · [Registration](../../../../research/venue2027/popets/rq_and_estimands.yaml)

## Verification

The manifest records the implementation commit, pinned source and derived-shape hashes, nine evidence digests and per-run metrics. Each compressed archive contains the receiver's two streams, the sender's ordered per-request operation and time, and the collector's wall time. Replaying the observer requires only the checked files. Recollection downloads only the named training shard and refuses an existing destination.

```sh
python -m evaluation.venue2027.popets.sgd_replay verify artifacts/venue2027/popets/sgd-dev-01
curl --fail --location https://raw.githubusercontent.com/google-research-datasets/dstc8-schema-guided-dialogue/e852981ae34990f4358979625854259302feaa78/train/dialogues_001.json -o /tmp/sgd-dialogues_001.json
python -m evaluation.venue2027.popets.sgd_replay collect /tmp/sgd-dialogues_001.json /tmp/popets-sgd-new
python -m pytest -q evaluation/venue2027/popets research/venue2027/popets/tests tests/venue2027/popets
```
