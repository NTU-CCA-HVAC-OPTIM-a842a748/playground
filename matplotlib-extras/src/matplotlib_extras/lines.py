import typing

import matplotlib.lines

from . import artist


class Line2D(matplotlib.lines.Line2D, artist.FlexArtist):
    def __init__(self, xdata=[], ydata=[], **kwargs):
        return super().__init__(xdata, ydata, **kwargs)

    def extend_data(self, *datas, orig=True):
        """
        Extend the x and y data.

        Parameters
        ----------
        *args : (2, N) array or two 1D arrays

        Examples
        --------
        TODO
        """

        # TODO NOTE datas: tuple of 1d arrays: (<xdata>, <ydata>, ...)
        def _impl(datas, orig):
            self.set_data(*(
                [*old_data, *data]
                for old_data, data in
                zip(self.get_data(orig=orig), datas)
            ))

        if len(datas) == 1:
            return _impl(*datas, orig=orig)
        return _impl(datas, orig=orig)

    def append_data(self, *datas, orig=True):
        # TODO NOTE datas: tuple: (<xdata>, <ydata>, ...)
        def _impl(datas, orig):
            return self.extend_data(tuple([d] for d in datas), orig=orig)

        if len(datas) == 1:
            return _impl(*datas, orig=orig)
        return _impl(datas, orig=orig)

class SimpleLine2D(Line2D):
    @classmethod
    def _f_xdata(cls, ydata, start=0, step=1):
        return range(start, start + len(ydata), step)

    def set_data_1d(self, ydata):
        self.set_data(
            self.__class__._f_xdata(ydata),
            ydata
        )

    def extend_data_1d(self, ydata, orig=True):
        return self.set_data_1d(
            [*self.get_ydata(orig=orig), *ydata]
        )

    def append_data_1d(self, ydata, orig=True):
        return self.extend_data_1d([ydata], orig=orig)

class StepFunction2D(Line2D):
    def __init__(
        self,
        *data_srcs: typing.Callable,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.on_step(
            'append_data',
            *data_srcs
        )

__all__ = [
    Line2D,
    SimpleLine2D,
    StepFunction2D
]
