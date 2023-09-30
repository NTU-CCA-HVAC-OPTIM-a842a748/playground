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
        return {
            key: f.__call__(*args, **kwargs)
                for key, f in self.items()
        }

__all__ = [
    OrderedSetDict
]
