from pathlib import Path

from setuptools import find_packages, setup

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setup(
    name="gitingest",
    version="0.1.3",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=[
        "click>=8.0.0",
        "tiktoken",
        "typing_extensions; python_version < '3.10'",
    ],
    entry_points={
        "console_scripts": [
            "gitingest=gitingest.cli:main",
        ],
    },
    python_requires=">=3.7",
    author="Romain Courtois",
    author_email="romain@coderamp.io",
    description="CLI tool to analyze and create text dumps of codebases for LLMs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cyclotruc/gitingest",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
)
