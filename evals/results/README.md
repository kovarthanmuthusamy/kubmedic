# Benchmark results

Live benchmark runs (`python -m evals.harness`) write one JSON file per
run here: `<UTC timestamp>-<model>.json`, with per-scenario outcomes,
agent time-to-fix, token counts and cost, plus the summary the README's
headline table is filled from.

There are deliberately **no result files yet**: the benchmark has not
been run on a cluster. The README table stays `TBD` until a results
file exists — numbers are never written from memory or expectation.
