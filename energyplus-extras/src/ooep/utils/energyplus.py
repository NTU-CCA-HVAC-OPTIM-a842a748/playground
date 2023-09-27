from __future__ import annotations

import os
import shutil
import importlib
import typing
import pathlib

from . import monkey


class Importer:
    def __init__(
        self,
        exec_name: str = 'energyplus',
        package_name: str = 'pyenergyplus'
    ):
        self.exec_name = exec_name
        self.package_name = package_name

    @property
    def base_path(self):
        exec_path = shutil.which(self.exec_name)
        if exec_path is None:
            raise FileNotFoundError(
                f'`{self.exec_name}` binary required '
                f'to locate `{self.package_name}` but not found: '
                'make sure it is installed and in the search path'
            )
        return os.path.dirname(
            os.path.realpath(exec_path)
        )

    def __import__(self, **importlib_options):
        with monkey.temporary_search_path(self.base_path):
            return importlib.__import__(self.package_name, **importlib_options)

    def import_module(self, name: str):
        return importlib.import_module(name, package=self.package_name)

    def import_modules(self, *names: str):
        return [
            self.import_module(name)
                for name in names
        ]

    def import_package(
        self,
        submodules: typing.Collection[str],
        **importlib_options
    ):
        pkg = self.__import__(**importlib_options)
        _ = self.import_modules(*submodules)
        return pkg

importer = Importer()

class Dataset:
    def __init__(self, base_path: str | bytes | os.PathLike):
        self.base_path = pathlib.Path(base_path)

    @property
    def models(self):
        return self.base_path / 'ExampleFiles'

    @property
    def weathers(self):
        return self.base_path / 'WeatherData'
    
    @property
    def datas(self):
        return self.base_path / 'DataSets'

dataset = Dataset(base_path=importer.base_path)

__all__ = [
    Importer, importer,
    Dataset, dataset
]
