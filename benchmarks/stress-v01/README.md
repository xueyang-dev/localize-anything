# v0.1 Runtime Stress Benchmark

This benchmark exercises the deterministic v0.1 runtime path with synthetic
locale data. It does not measure translation quality and does not use private
source material.

Default gate:

```bash
python benchmarks/stress-v01/run.py
```

The default profile generates 10,000 JSON locale segments and requires the
measured runtime stages to complete within 15 seconds and 512 MiB of traced
Python heap.

Larger exploratory run:

```bash
python benchmarks/stress-v01/run.py --segments 50000 --max-total-seconds 60 --report benchmarks/private/stress-v01-50000.json
```

The report includes stage timing, throughput, QA status, batch count, package
size, incremental diff summary, and work-packet retrieval before and after the
translation memory is populated. Reports under `benchmarks/private/` are
ignored by Git.
