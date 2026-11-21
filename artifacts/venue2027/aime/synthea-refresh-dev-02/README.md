# Chart refresh across a second Synthea release

The [registered development repeat](../../../../research/venue2027/aime/protocols/synthea_visit_refresh_dev.md) covered 1,163 encounter histories in the November 2021 CSV. Two histories (58 transitions) were excluded across all arms after five reversed medication intervals. The remaining 58,917 transitions include 1,813 stale automatic deliveries under the single-section hint in 856 subjects. Checking both snapshots eliminated the observed stale deliveries and raised review decisions from 4,448 to 4,724. Full scan and interval sweep delivered every exact chart projection without a review. The two releases share zero encounter-subject keys and the same synthetic generator lineage.

These results establish a software failure mode under a constructed hint stream. The clinical workflow manuscript is retired from the active portfolio because its primary endpoint requires human judgments. These results remain reproducible development evidence.

Run from the repository root with Python 3.11 or newer.

```sh
python -m evaluation.venue2027.aime.synthea_visit_refresh /path/to/csv-2021.zip | diff - artifacts/venue2027/aime/synthea-refresh-dev-02/summary.json
```
