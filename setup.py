"""Akshar — अक्षर — Setup"""
from setuptools import find_packages, setup

from engine import __version__

setup(
    name="akshar",
    version=__version__,
    description="Universal Real-Time Linguistic Overlay — system-wide transliteration IME for Linux",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Bharat",
    license="MIT",
    url="https://github.com/akshar-ime/akshar",
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.8",
    # Language maps live OUTSIDE the package; the engine finds them via $AKSHAR_LANG_DIR
    # or /usr/local/share/akshar/languages (installed here).
    data_files=[
        ("share/akshar/languages", [f"languages/{f}" for f in __import__("os").listdir("languages") if f.endswith(".json")]),
        ("share/akshar/languages/lexicon", [f"languages/lexicon/{f}" for f in __import__("os").listdir("languages/lexicon") if f.endswith(".json")]),
    ],
    extras_require={"offline": ["argostranslate"], "test": ["pytest"]},
    entry_points={"console_scripts": ["akshar-cli=engine.cli:main"]},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Topic :: Text Processing :: Linguistic",
    ],
)
