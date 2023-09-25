import builtins
import contextlib

@contextlib.contextmanager
def temporary_attr(o, name: str):
    a = builtins.getattr(o, name)
    try: yield
    finally: builtins.setattr(o, name, a)

import sys

@contextlib.contextmanager
def temporary_search_path(*paths):
    with temporary_attr(sys, 'path'):
        builtins.setattr(sys, 'path', [str(p) for p in paths])
        try: yield
        finally: pass

__all__ = [
    temporary_attr,
    temporary_search_path
]
