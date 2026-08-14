// ============================================================================
//  aios_native — AI-OS native accelerators (Phase 8, C++/pybind11)
//
//  A compiled fast path for the one CPU-bound hot loop profiling found: vault
//  tokenization. `ai_os/core/knowledge/index.py` auto-detects this module and
//  uses it if present, else falls back to the pure-Python tokenizer. Output is
//  byte-for-byte identical to the Python version (same stopwords, same rules).
//
//  Build:  pip install pybind11 && pip install ./native
// ============================================================================
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <string>
#include <vector>
#include <unordered_set>
#include <cctype>

namespace py = pybind11;

// Must match _STOP in index.py exactly.
static const std::unordered_set<std::string> STOP = {
    "the","a","an","and","or","of","to","in","is","are","for","on","with",
    "as","at","by","be","this","that","it","from"
};

// Tokenize == Python: findall([a-z0-9]+) over text.lower(), drop len<=1 + stopwords.
static std::vector<std::string> tokenize(const std::string& text) {
    std::vector<std::string> out;
    std::string cur;
    cur.reserve(32);
    auto flush = [&]() {
        if (cur.size() > 1 && STOP.find(cur) == STOP.end())
            out.push_back(cur);
        cur.clear();
    };
    for (unsigned char c : text) {
        if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')) {
            cur.push_back(static_cast<char>(std::tolower(c)));
        } else {
            flush();
        }
    }
    flush();
    return out;
}

PYBIND11_MODULE(aios_native, m) {
    m.doc() = "AI-OS native accelerators (Phase 8)";
    m.def("tokenize", &tokenize,
          "Fast tokenizer; output identical to the Python fallback.");
}
