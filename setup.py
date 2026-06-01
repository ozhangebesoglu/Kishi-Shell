from setuptools import setup, Extension
from Cython.Build import cythonize
import os

# Wheel'lar manylinux/macOS/Windows için cibuildwheel ile üretiliyor.
# -march=native YASAK — derlendiği makineye özel binary üretir, taşınabilir
# wheel olmaz. -O3 yeterli optimizasyon (Cython zaten %95 hız kazancını verir).
extensions = [
    Extension(
        "kishi.krep_core",
        ["kishi/krep_core.pyx"],
        extra_compile_args=["-O3"] if os.name != "nt" else ["/O2"],
    )
]

setup(
    ext_modules=cythonize(extensions, compiler_directives={"language_level": "3"}),
)
