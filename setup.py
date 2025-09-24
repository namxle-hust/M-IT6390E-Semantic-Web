"""
Setup script for Vietnamese DBPedia project.
"""

from setuptools import setup, find_packages
import os
from pathlib import Path

# Read README file
readme_path = Path(__file__).parent / "README.md"
if readme_path.exists():
    with open(readme_path, "r", encoding="utf-8") as f:
        long_description = f.read()
else:
    long_description = "Vietnamese DBPedia - Semantic Web knowledge base for Vietnamese entities"

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
if requirements_path.exists():
    with open(requirements_path, "r", encoding="utf-8") as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
else:
    requirements = []

setup(
    name="vietnamese-dbpedia",
    version="1.0.0",
    author="M-IT6390E Semantic Web Project",
    author_email="student@example.com",
    description="Vietnamese DBPedia - Comprehensive semantic web knowledge base for Vietnamese entities",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/example/vietnamese-dbpedia",
    packages=find_packages(include=['src', 'src.*']),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Researchers", 
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Text Processing :: Linguistic",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        'dev': [
            'pytest>=7.0.0',
            'pytest-cov>=4.0.0',
            'pytest-mock>=3.10.0',
            'black>=23.0.0',
            'isort>=5.12.0',
            'flake8>=6.0.0',
            'mypy>=1.0.0',
        ],
        'docs': [
            'sphinx>=6.0.0',
            'sphinx-rtd-theme>=1.2.0',
        ],
    },
    entry_points={
        'console_scripts': [
            'vietnamese-dbpedia=cli:cli',
        ],
    },
    include_package_data=True,
    package_data={
        '': ['*.yaml', '*.yml', '*.json', '*.ttl', '*.owl', '*.html', '*.css', '*.js'],
    },
    zip_safe=False,
    keywords=[
        'semantic web', 'rdf', 'knowledge base', 'vietnamese', 'dbpedia',
        'sparql', 'graphdb', 'ontology', 'linked data', 'nlp'
    ],
    project_urls={
        'Bug Reports': 'https://github.com/example/vietnamese-dbpedia/issues',
        'Source': 'https://github.com/example/vietnamese-dbpedia',
        'Documentation': 'https://vietnamese-dbpedia.readthedocs.io/',
    },
)