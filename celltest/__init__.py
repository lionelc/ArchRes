"""celltest: the measurement half of the reference-guided gap method, independent of the case.

gapgraph (the sibling package) never runs an engine; it reads measured files. celltest produces those files and the
evidence that decides a fix's verdict. Standard library only (Python >= 3.9), so it runs inside a case's container.

Modules:
  registry     seeds derived from a registration's sha256; code-freeze manifests; binaries pinned by sha256; run metadata
  orders       block-order designs (ABBA, rotation, explicit cycles) and the checks that make them counterbalanced
  spec         cells, arms (connections) and designs; building each arm's command line and environment
  execute      process and in-process executors: warm-ups, timed blocks, output verification, whole-panel runs
  write        one result model, read from and written to the files gapgraph.digest and gapgraph.rebuild read
  capture      deterministic counters: callgrind (instructions, top functions, markers), strace -c, /usr/bin/time
  noise        A/A diagnostics: single-block bands, matched-estimator nulls, outlier blocks, order effects
  sufficiency  the sufficiency rule for a fix's effect (deterministic mechanism, sign, beyond a matched null), with looks

Case code that stays in the case: input generators, the panel data (cells), digest hooks and prompt parameters."""
