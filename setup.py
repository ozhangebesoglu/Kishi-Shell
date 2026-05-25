from setuptools import setup, Extension
from Cython.Build import cythonize
import os

extensions = [
    Extension(
        "kishi.krep_core",
        ["kishi/krep_core.pyx"],
        extra_compile_args=["-O3", "-march=native"] if os.name != "nt" else ["/O2"],
    )
]

setup(
    ext_modules=cythonize(extensions, compiler_directives={"language_level": "3"}),
)
