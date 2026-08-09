# Full-stack benchmark protocol

The PostgreSQL runner executes inside an API container and calls the API-owned
GST/GLHS gateway. GLHS intentionally exposes no arbitrary public GST endpoint,
so the manifest distinguishes this service-layer measurement from HTTP
transport latency.

Run only against an isolated PostgreSQL → GST → GLHS → THSS → API deployment
with fixed data and concurrency. Capture P50/P95/P99, throughput, DB I/O,
write/storage amplification, reconstruction, snapshot compilation,
invalidation/rebuild, revocation propagation, CPU, and peak RSS. Full archive
runs also record hardware, workers, wall-clock, cases/s, peak RSS, and phase
timing.

```bash
python3 -m evaluation.fullstack_benchmark.run_postgresql \
  --output /secure/fullstack-run
python3 -m evaluation.fullstack_benchmark.validate_metrics --metrics /secure/fullstack_metrics.csv --manifest /secure/fullstack_manifest.json
```
