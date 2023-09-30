import matplotlib.lines

from . import artist

class Line2D(matplotlib.lines.Line2D, artist.FlexArtist):
    def __init__(self, xdata=[], ydata=[], **kwargs):
        return super().__init__(xdata, ydata, **kwargs)

    def extend_data(self, *datas, orig=True):
        self.set_data(*(
            [*old_data, *data]
            for old_data, data in
            zip(self.get_data(orig=orig), datas)
        ))

    def append_data(self, *datas, orig=True):
        return self.extend_data(*([d] for d in datas), orig=orig)

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

__all__ = [
    Line2D, SimpleLine2D
]
