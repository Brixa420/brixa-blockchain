# Setup configuration for PyPI package
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="wrath-scaling-layer",
    version="1.0.0",
    author="Laura Wolf (Brixa420)",
    author_email="brixa420@example.com",
    description="Drop-in infinite TPS scaling layer for any blockchain",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Brixa420/brixa-blockchain",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "aiohttp>=3.8.0",
        "websockets>=10.0.0",
    ],
    extras_require={
        "ethereum": ["web3>=6.0.0", "eth-account>=0.9.0"],
        "bitcoin": ["python-bitcoinrpc>=0.0.1"],
        "solana": ["solana>=0.30.0"],
    },
    package_data={
        "wrath_scaling": ["py.typed"],
    },
)