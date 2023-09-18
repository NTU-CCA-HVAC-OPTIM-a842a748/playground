#!/usr/bin/env python3

import setuptools

setuptools.setup(
    name='energyplus-extras',
    version='0.0.0a',
    description='EnergyPlus Object-Oriented API',
    python_requires='>=3.9',
    packages=['ooep'],
    package_dir={
        '': 'src'
    },    
    install_requires=[
        'packaging', 
        'pandas'
    ],
    extras_require={
        'dev': []
    }
)
