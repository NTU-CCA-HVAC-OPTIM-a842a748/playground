import abc
import typing
import functools

import matplotlib
import matplotlib.artist

from . import utils

class Artist(matplotlib.artist.Artist, abc.ABC):
    @functools.cached_property
    def _step_callbacks(self):
        class _Callbacks(utils.containers.OrderedSetDict):
            @classmethod
            def _entry_encode(cls, func, *args, **kwargs):
                return tuple(
                    (func, args, tuple(kwargs.items()))
                )

            def __init__(self, *args, func_resolver=None, **kwargs):
                self._func_resolver = func_resolver
                super().__init__(*args, **kwargs)

            def add(self, func, *args, **kwargs):
                return super().add(
                    self.__class__._entry_encode(func, *args, **kwargs)
                )

            def remove(self, func, *args, **kwargs):
                return super().remove(
                    self.__class__._entry_encode(func, *args, **kwargs)
                )

            def __call__(self):
                def _func_handler(f):
                    nonlocal self
                    if callable(f): return f
                    if self._func_resolver is not None:
                        return self._func_resolver(f)
                    raise TypeError

                return {
                    key: _func_handler(f).__call__(
                        *(f_args() for f_args in args_factory),
                        **{name: f_kwargs() for name, f_kwargs in kwargs_factory}
                    ) for key, (f, args_factory, kwargs_factory) in self.items()
                }

        return _Callbacks(
            # NOTE instance method needs to be unbounded hence the `.__func__`
            func_resolver=lambda name: getattr(self, name).__func__
        )

    # TODO NOTE format: <instance_method_name>, <args_factory>
    # TODO NOTE example: .on_step('set_data', lambda: [1, 2, 3])
    # TODO NOTE example: .on_step(lambda self, a: self.set_data(a), lambda: [1, 2, 3])
    def on_step(
        self,
        callback: typing.Callable | str,
        *args_factory, **kwargs_factory
    ):
        self._step_callbacks.add(
            callback,
            lambda: self,
            *args_factory, **kwargs_factory
        )
        return self

    def step(self):
        self._step_callbacks()

class FlexArtist(Artist):
    def autofit(self, enable=True):
        self._autofit = enable
        return self

    def step(self, *args, **kwargs):
        res = super().step(*args, **kwargs)
        if getattr(self, '_autofit', False):
            self.axes.relim()
            self.axes.autoscale_view()
        return res

__all__ = [
    Artist,
    FlexArtist
]
