# aios_native — C++ accelerators (Phase 8)

The optional native hot-path engine. Profiling ([the Phase 8 story](../ROADMAP.md))
showed vault **search** was the only genuinely CPU-bound path. The big win was an
algorithmic one — an inverted index (~60×, pure Python). This module is the
*further* optional micro-optimization: a compiled C++ tokenizer for the inner loop.

## Build

From the repo root, on a machine with a C++ compiler:

```bash
pip install pybind11
pip install ./native
```

- Linux: `sudo apt install build-essential`
- macOS: `xcode-select --install`
- Windows: install "Microsoft C++ Build Tools"

## How it's used

`ai_os/core/knowledge/index.py` does `import aios_native` at load time. If the
compiled module is present, `tokenize()` uses the C++ path; otherwise it uses the
identical pure-Python implementation. Nothing else changes — it's transparent.

Check which is active:

```bash
curl http://localhost:8080/api/v1/knowledge/status   # → "native_tokenizer": true|false
```

## Honest note

This module is **written and build-configured but not compiled/benchmarked in the
project's dev environment** (no C++ toolchain there). It builds where a compiler
exists. The **index is where the real speedup came from** — the C++ tokenizer is a
marginal extra on top, included because a native engine was explicitly requested.
For this workload, once the index exists, Python is already fast enough; C++ helps
most on very large vaults / bulk re-indexing.
