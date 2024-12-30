"""Setup script for drapto."""

from setuptools import setup, find_packages

setup(
    name="drapto",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "loguru>=0.7.0",
        "pydantic>=2.0.0",
        "tqdm>=4.65.0",
    ],
    entry_points={
        "console_scripts": [
            "drapto=drapto.cli:main",
        ],
    },
)
