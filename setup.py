from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="kishi-shell",
    version="1.8.8",
    author="Ozhan Gebesoglu",
    author_email="ozhan.gebesoglu@gmail.com",
    description="A powerful, highly modular, Python-based modern shell.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ozhangebesoglu/Kishi-Shell",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: POSIX :: Linux",
        "Environment :: Console",
    ],
    python_requires=">=3.8",
    install_requires=[
        "prompt_toolkit>=3.0.0",
        "psutil>=5.0.0"
    ],
    entry_points={
        "console_scripts": [
            "kishi=kishi.main:main",
        ],
    },
)
