- DOE Commercial Prototype Building Models
	https://www.energycodes.gov/prototype-building-models
- DOE Commercial Reference Building Energy Models
	https://www.energy.gov/eere/buildings/commercial-reference-buildings
- OpenAI Gym environment for building simulation and control using reinforcement learning
	https://github.com/ugr-sail/sinergym
- https://www.energy.gov/eere/buildings/articles/spawn-energyplus-spawn
- https://github.com/mechyai/rl_bca
- https://github.com/mechyai/RL-EmsPy
- https://bigladdersoftware.com/epx/docs/9-6/input-output-reference/api-usage.html

## TODOs
- `EventListener` for `ooep.ems.Environment`
-
```
import collections

class OrderedSetDict(collections.OrderedDict):
    def add(self, v):
        self[v] = v

    def remove(self, v):
        return self.pop(v)

# TODO NOTE data format {<callable>: <callable>} {<key>: <callable>}
class CallableSet(OrderedSetDict):
    def __call__(self, *args, **kwargs):
        return {
            f: f.__call__(*args, **kwargs)
                for _, f in self.items()
        }
```
- Feature: read model without `exec`
-
```
import typing

class BaseDataAggregator:
    def __init__(self, source: typing.Callable[[], typing.Any]):
        self._data = []
        self._source = source

    @property
    def data(self):
        return self._data

    def __call__(self, *args, **kwargs):
        self._data.append(self._source(*args, **kwargs))
        return self._data


# TODO .. support for env components!!!
class DataAggregator(BaseDataAggregator):
    pass

import itertools

class BaseCountAggregator(BaseDataAggregator):
    def __init___(self, start=0, step=1):
        self._cnt = itertools.count(start, step)
        return super().__init__(
            source=lambda: next(self._cnt)
        )

```