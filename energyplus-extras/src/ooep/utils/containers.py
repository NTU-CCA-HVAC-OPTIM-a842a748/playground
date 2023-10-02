import collections

class OrderedSetDict(collections.OrderedDict):
    def add(self, v):
        self[v] = v

    def remove(self, v):
        return self.pop(v)

# TODO
# TODO NOTE data format {<callable>: <callable>} {<key>: <callable>}
class CallableSet(OrderedSetDict):
    def __call__(self, *args, **kwargs):
        return collections.OrderedDict({
            key: f.__call__(*args, **kwargs)
                for key, f in self.items()
        })

# TODO
class DefaultSet(set):
    def __init__(self, default_factory):
        self._default_factory = default_factory

    def add(self, *args, **kwargs):
        return super().add(self._default_factory(*args, **kwargs))


__all__ = [
    OrderedSetDict,
    CallableSet,
    DefaultSet
]
