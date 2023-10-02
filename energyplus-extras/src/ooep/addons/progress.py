from . import OptionalImportError

try: import tqdm.auto
except ImportError as e:
    raise OptionalImportError(['tqdm']) from e

from .. import ems


class BaseProgressBar(tqdm.auto.tqdm):
    def update_to(self, n):
        self.n = n
        self.refresh()

class ProgressBar(BaseProgressBar):
    def __init__(self, env: ems.Environment, **tqdm_kwargs):
        self._env = env

        (
        self._env.event_listener
            .subscribe(
                dict(event_name='progress'),
                self.update_to
            )
            .subscribe(
                dict(event_name='message'),
                lambda s: self.set_postfix_str(s.decode())
            )
        )

        super().__init__(total=100, **tqdm_kwargs)

__all__ = [
    BaseProgressBar,
    ProgressBar
]
