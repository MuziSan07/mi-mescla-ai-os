"""
Build the aios_native C++ accelerator (Phase 8).

    pip install pybind11
    pip install ./native          # from the repo root

Needs a C++ compiler (build-essential / MSVC Build Tools / Xcode CLT). Optional:
the app runs fine without it (pure-Python fallback in index.py).
"""

from setuptools import setup

try:
    from pybind11.setup_helpers import Pybind11Extension, build_ext
except ImportError:  # give a clear message instead of a cryptic failure
    raise SystemExit("Install pybind11 first:  pip install pybind11")

ext_modules = [
    Pybind11Extension(
        "aios_native",
        ["aios_native.cpp"],
        cxx_std=17,
    )
]

setup(
    name="aios_native",
    version="0.1.0",
    description="AI-OS native accelerators (fast tokenizer)",
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
    zip_safe=False,
)
