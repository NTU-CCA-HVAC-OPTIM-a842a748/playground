#!/usr/bin/env python3

import setuptools


setuptools.setup(
    name='matplotlib-extras',
    version='3.7.2.0a',
    description='Matplotlib API Extras',
    python_requires='>=3.9',
    packages=['matplotlib_extras'],
    package_dir={
        '': 'src'
    },
    install_requires=[
        'matplotlib>=3.7.2'
    ],
    extras_require={
        'dev': []
    }
)
