"""
AI-OS Vault Index (Phase 8) — the profiling-driven hot-path optimization.

Profiling showed vault search was the one genuinely CPU-bound path: the naive
version re-read and re-tokenized *every* note on *every* query (O(all notes),
~1.1 s over 1500 notes). This replaces that with an in-memory **inverted index**
built once and updated incrementally, so a query only scores the notes that
actually contain its terms (O(matching notes), sub-millisecond).

An optional native accelerator (`aios_native`, C++/pybind11 — see native/) speeds
the tokenizer inner loop when compiled; everything falls back to pure Python.
"""

import os
import re
import glob
import logging
from collections import Counter, defaultdict
from typing import Dict, List, Any, Optional, Set

logger = logging.getLogger(__name__)

_WORD = re.compile(r"[a-z0-9]+")
_STOP = set("the a an and or of to in is are for on with as at by be this that it from".split())

# Optional C++ accelerator for tokenization (compiled from native/aios_native.cpp).
try:  # pragma: no cover - depends on a compiled extension being present
    import aios_native as _native
    _HAVE_NATIVE = True
except Exception:
    _native = None
    _HAVE_NATIVE = False


def tokenize(text: str) -> List[str]:
    """Tokenize + stopword-filter. Uses the native accelerator if available."""
    if _HAVE_NATIVE:
        return _native.tokenize(text)          # C++ fast path
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 1]


class VaultIndex:
    """In-memory inverted index over a vault's markdown notes."""

    def __init__(self) -> None:
        self.doc_tf: Dict[str, Counter] = {}              # path -> term frequencies
        self.postings: Dict[str, Set[str]] = defaultdict(set)  # term -> {paths}
        self.doc_tags: Dict[str, Set[str]] = {}           # path -> {tags}
        self.built = False

    # -- maintenance --------------------------------------------------------
    def add(self, path: str, content: str, tags: Optional[List[str]] = None) -> None:
        self.remove(path)  # keep postings consistent on update
        terms = tokenize(content)
        tf = Counter(terms)
        self.doc_tf[path] = tf
        for term in tf:
            self.postings[term].add(path)
        self.doc_tags[path] = {t.lower() for t in (tags or [])}

    def remove(self, path: str) -> None:
        old = self.doc_tf.pop(path, None)
        if old:
            for term in old:
                s = self.postings.get(term)
                if s:
                    s.discard(path)
                    if not s:
                        del self.postings[term]
        self.doc_tags.pop(path, None)

    def build(self, root: str) -> "VaultIndex":
        self.doc_tf.clear(); self.postings.clear(); self.doc_tags.clear()
        for full in glob.glob(os.path.join(root, "**", "*.md"), recursive=True):
            rel = os.path.relpath(full, root).replace("\\", "/")
            try:
                with open(full, encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            tags = re.findall(r"(?:^|\s)#([a-zA-Z0-9_/-]+)", text)
            self.add(rel, text, tags)
        self.built = True
        return self

    # -- query --------------------------------------------------------------
    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        q_terms = set(tokenize(query))
        if not q_terms:
            return []
        # Candidate docs = union of postings for the query terms (NOT all docs).
        candidates: Set[str] = set()
        for t in q_terms:
            candidates |= self.postings.get(t, set())
        # Also allow title/path matches even without a body hit.
        for path in self.doc_tf:
            if any(t in path.lower() for t in q_terms):
                candidates.add(path)

        results = []
        for path in candidates:
            tf = self.doc_tf.get(path, {})
            score = sum(tf.get(t, 0) for t in q_terms)
            score += 3 * len(q_terms & self.doc_tags.get(path, set()))
            score += 5 * sum(1 for t in q_terms if t in path.lower())
            if score:
                results.append({"path": path, "score": score,
                                "tags": sorted(self.doc_tags.get(path, set()))})
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:k]

    def stats(self) -> Dict[str, Any]:
        return {"documents": len(self.doc_tf), "terms": len(self.postings),
                "native_tokenizer": _HAVE_NATIVE}
