import sys
import typing


class OptionalImportError(ImportError):
    @classmethod
    def suggest(cls, package_names: typing.Collection[str]):
        return cls(
            'Missing optional dependency(ies)/module(s): '
            f'''{str.join(', ', package_names)}. '''
            f'''Install them through {sys.executable} to use this feature.'''
        )

__all__ = [
    OptionalImportError
]
