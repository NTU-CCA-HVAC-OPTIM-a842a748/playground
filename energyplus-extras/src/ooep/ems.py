from __future__ import annotations

import abc
import typing
import collections
import io
import csv
import datetime

import packaging
import pandas as pd

from . import utils


class BaseEnvironment:
    _target_ep_api_version = packaging.version.Version('0.2')

    @classmethod
    def _ep_api_version(cls, ep_api: 'pyenergyplus.api.EnergyPlusAPI'):
        return packaging.version.Version(ep_api.api_version())

    def __init__(self, ep_api: 'pyenergyplus.api.EnergyPlusAPI' = None):
        if not self._ep_api_version(ep_api) >= self._target_ep_api_version:
            raise Exception(
                f'pyenergyplus version incompatible: '
                f'{self.__class__} requires {self._target_ep_api_version}; '
                f'got {self._ep_api_version(ep_api)}'
            )
        self._ep_api = ep_api

    def __enter__(self):
        # TODO
        if getattr(self, '_ep_state', None) is None:
            self._ep_state = self._ep_api.state_manager.new_state()
        else: self._ep_api.state_manager.reset_state(self._ep_state)
        return self

    def __exit__(self, *_exc_args):
        if getattr(self, '_ep_state', None) is None:
            return
        self._ep_api.state_manager.delete_state(self._ep_state)
        del self._ep_state

    def _console_output(self, enabled: bool):
        self._ep_api.runtime.set_console_output_status(
            self._ep_state,
            print_output=enabled
        )

    def _exec(self, *args):
        return self._ep_api.runtime.run_energyplus(
            self._ep_state,
            command_line_args=args
        )

    def _stop(self):
        self._ep_api.runtime.stop_simulation(self._ep_state)

    def __call__(self, *args):
        return self._exec(*args)

    def stop(self):
        return self._stop()

    @property
    def _available_data(self):
        def _ep_csv_reader(f, default_title=None):
            title = default_title
            for row in csv.reader(f):
                if len(row) == 1:
                    title = row.pop()
                yield title, row

        # TODO NOTE headsup! upcoming version will include `get_api_data`:
        # csv may no longer be needed
        with io.StringIO(
            self._ep_api.exchange
                .list_available_api_data_csv(self._ep_state)
                .decode()
        ) as f:
            d = collections.defaultdict(lambda: [])
            for title, row in _ep_csv_reader(f):
                if not row:
                    continue
                d[title].append(row)

            colnames = {
                '**ACTUATORS**': ['type', 'component_type', 'control_type', 'actuator_key'],
                '**INTERNAL_VARIABLES**': ['type', 'variable_type', 'variable_key'],
                '**PLUGIN_GLOBAL_VARIABLES**': ['type', 'var_name'],
                '**TRENDS**': ['type', 'trend_var_name'],
                '**METERS**': ['type', 'meter_name'],
                '**VARIABLES**': ['type', 'variable_name', 'variable_key']
            }

            return {
                title: pd.DataFrame(
                    d.get(title, []),
                    columns=colnames[title]
                ) for title in colnames
            }

    @property
    def _data_ready(self):
        return self._ep_api.exchange.api_data_fully_ready(self._ep_state)

    class Specs(typing.NamedTuple):
        # datas
        actuators: pd.DataFrame
        internal_variables: pd.DataFrame
        # plugin_variables: pd.DataFrame
        # plugin_trends: pd.DataFrame
        meters: pd.DataFrame
        variables: pd.DataFrame
        # events
        events: pd.DataFrame

    @property
    def specs(self) -> Specs:
        return self.Specs(
            # datas
            actuators=self._available_data['**ACTUATORS**'][
                [*self.Actuator.Specs._fields]
            ],
            internal_variables=self._available_data['**INTERNAL_VARIABLES**'][
                [*self.InternalVariable.Specs._fields]
            ],
            #plugin_variables=...,
            #plugin_trends=...,
            meters=self._available_data['**METERS**'][
                [*self.Meter.Specs._fields]
            ],
            variables=self._available_data['**VARIABLES**'][
                [*self.Variable.Specs._fields]
            ],
            # events
            events=pd.DataFrame(self.Event._get_ep_available_specs())
        )

    class Component(abc.ABC):
        class NotReadyError(Exception):
            pass

        class Specs(typing.NamedTuple):
            ...

        def __init__(
            self,
            specs: Specs | typing.Mapping,
            environment: 'Environment'
        ):
            self._specs = self.Specs(**specs)
            self._env = environment

        @property
        def specs(self):
            return self._specs

    def _component(
        self,
        specs: typing.Mapping | Component.Specs | pd.DataFrame,
        constructor: typing.Callable[[Component.Specs], Component]
    ):
        if isinstance(specs, pd.DataFrame):
            return pd.DataFrame.apply(specs, constructor, axis='columns')
        return constructor(specs)

    class Actuator(Component):
        class Specs(typing.NamedTuple):
            component_type: str
            control_type: str
            actuator_key: str

        @property
        def _ep_handle(self):
            if not self._env._data_ready:
                raise self.NotReadyError()
            return self._env._ep_api.exchange.get_actuator_handle(
                self._env._ep_state,
                component_type=self._specs.component_type,
                control_type=self._specs.control_type,
                actuator_key=self._specs.actuator_key
            )

        @property
        def value(self):
            return self._env._ep_api.exchange.get_actuator_value(
                self._env._ep_state,
                actuator_handle=self._ep_handle
            )

        @value.setter
        def value(self, n: float):
            self._env._ep_api.exchange.set_actuator_value(
                self._env._ep_state,
                actuator_handle=self._ep_handle,
                actuator_value=n
            )

        def reset(self):
            self._env._ep_api.exchange.reset_actuator(
                self._env._ep_state,
                actuator_handle=self._ep_handle
            )

    def actuator(
        self,
        specs: typing.Mapping | Actuator.Specs | pd.DataFrame
    ) -> Actuator:
        return self._component(
            specs,
            lambda d: self.Actuator(d, environment=self)
        )

    class InternalVariable(Component):
        class Specs(typing.NamedTuple):
            variable_type: str
            variable_key: str

        @property
        def _ep_handle(self):
            if not self._env._data_ready:
                raise self.NotReadyError()
            return self._env._ep_api.exchange.get_internal_variable_handle(
                self._env._ep_state,
                variable_name=self._specs.variable_name,
                variable_key=self._specs.variable_key
            )

        @property
        def value(self):
            return self._env._ep_api.exchange.get_internal_variable_value(
                self._env._ep_state,
                variable_handle=self._ep_handle
            )

    def internal_variable(
        self,
        specs: typing.Mapping | InternalVariable.Specs | pd.DataFrame
    ) -> InternalVariable:
        return self._component(
            specs,
            lambda d: self.InternalVariable(d, environment=self)
        )

    class Meter(Component):
        class Specs(typing.NamedTuple):
            meter_name: str

        @property
        def _ep_handle(self):
            if not self._env._data_ready:
                raise self.NotReadyError()
            return self._env._ep_api.exchange.get_meter_handle(
                self._env._ep_state,
                meter_name=self._specs.meter_name
            )

        @property
        def value(self):
            return self._env._ep_api.exchange.get_meter_value(
                self._env._ep_state,
                meter_handle=self._ep_handle
            )

    def meter(
        self,
        specs: typing.Mapping | Meter.Specs | pd.DataFrame
    ) -> Meter:
        return self._component(
            specs,
            lambda d: self.Meter(d, environment=self)
        )

    class Variable(Component):
        class Specs(typing.NamedTuple):
            variable_name: str
            variable_key: str

        def __init__(
            self,
            specs: Specs,
            environment: 'Environment'
        ):
            super().__init__(specs, environment)
            self._make_avilable()

        def _make_avilable(self):
            self._env._ep_api.exchange.request_variable(
                self._env._ep_state,
                variable_name=self._specs.variable_name,
                variable_key=self._specs.variable_key
            )

        @property
        def _ep_handle(self):
            if not self._env._data_ready:
                raise self.NotReadyError()
            return self._env._ep_api.exchange.get_variable_handle(
                self._env._ep_state,
                variable_name=self._specs.variable_name,
                variable_key=self._specs.variable_key
            )

        @property
        def value(self):
            return self._env._ep_api.exchange.get_variable_value(
                self._env._ep_state,
                variable_handle=self._ep_handle
            )

    def variable(
        self,
        specs: typing.Mapping | Variable.Specs | pd.DataFrame
    ) -> Variable:
        return self._component(
            specs,
            lambda d: self.Variable(d, environment=self)
        )

    class Event(Component):
        class Specs(typing.NamedTuple):
            event_name: str

        @classmethod
        def _get_ep_callback_setters(cls):
            # TODO NOTE of states: each state only has a single callback; states don't share callbacks!
            #   that's why we don't need to pass the state (or its wrapper `Environment`) to clients
            def _state_callback_setter(state, base_setter):
                return lambda callback: base_setter(
                    state,
                    lambda _: callback()
                )

            def _data_callback_setter(state, base_setter):
                return lambda callback: base_setter(
                    state, callback
                )

            runtime: 'pyenergyplus.api.runtime'
            return {
                # state callbacks
                cls.Specs('after_component_input'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.callback_after_component_get_input
                    ),
                cls.Specs('after_new_environment_warmup_complete'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.callback_after_new_environment_warmup_complete
                    ),
                cls.Specs('after_predictor_after_hvac_managers'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.callback_after_predictor_after_hvac_managers
                    ),
                cls.Specs('after_predictor_before_hvac_managers'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.callback_after_predictor_before_hvac_managers
                    ),
                cls.Specs('begin_new_environment'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.callback_begin_new_environment
                    ),
                cls.Specs('begin_system_timestep_before_predictor'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.callback_begin_system_timestep_before_predictor
                    ),
                cls.Specs('begin_zone_timestep_after_init_heat_balance'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.callback_begin_zone_timestep_after_init_heat_balance
                    ),
                cls.Specs('begin_zone_timestep_before_init_heat_balance'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.callback_begin_zone_timestep_before_init_heat_balance
                    ),
                cls.Specs('begin_zone_timestep_before_set_current_weather'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.callback_begin_zone_timestep_before_set_current_weather
                    ),
                cls.Specs('end_system_sizing'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.callback_end_system_sizing
                    ),
                cls.Specs('end_system_timestep_after_hvac_reporting'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.callback_end_system_timestep_after_hvac_reporting
                    ),
                cls.Specs('end_system_timestep_before_hvac_reporting'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.callback_end_system_timestep_before_hvac_reporting
                    ),
                cls.Specs('end_zone_sizing'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.callback_end_zone_sizing
                    ),
                cls.Specs('end_zone_timestep_after_zone_reporting'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.callback_end_zone_timestep_after_zone_reporting
                    ),
                cls.Specs('end_zone_timestep_before_zone_reporting'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.callback_end_zone_timestep_before_zone_reporting
                    ),
                cls.Specs('inside_system_iteration_loop'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.callback_inside_system_iteration_loop
                    ),
                cls.Specs('register_external_hvac_manager'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.callback_register_external_hvac_manager
                    ),
                cls.Specs('unitary_system_sizing'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.callback_unitary_system_sizing
                    ),
                # data callbacks
                cls.Specs('message'):
                    lambda state, runtime: _data_callback_setter(
                        state, runtime.callback_message
                    ),
                cls.Specs('progress'):
                    lambda state, runtime: _data_callback_setter(
                        state, runtime.callback_progress
                    )
            }

        @classmethod
        def _get_ep_available_specs(cls):
            return cls._get_ep_callback_setters().keys()

        @property
        def callback(self):
            raise NotImplementedError('function not available: callbacks are write-only')

        @callback.setter
        def callback(self, f):
            self._get_ep_callback_setters()[self._specs](
                state=self._env._ep_state,
                runtime=self._env._ep_api.runtime
            )(f)

    def event(
        self,
        specs: typing.Mapping | Event.Specs | pd.DataFrame
    ) -> Event:
        return self._component(
            specs,
            lambda d: self.Event(d, environment=self)
        )

    @property
    def _TODO_datetime(self):
        # TODO
        return datetime.datetime(
            year=self._ep_api.exchange.year(self._ep_state),
            month=self._ep_api.exchange.month(self._ep_state),
            day=self._ep_api.exchange.day_of_month(self._ep_state),
            hour=self._ep_api.exchange.hour(self._ep_state),
            minute=self._ep_api.exchange.minutes(self._ep_state)
        )

class Environment(BaseEnvironment):
    def __init__(self, ep_api: 'pyenergyplus.api.EnergyPlusAPI' = None):
        if ep_api is None:
            ep = utils.energyplus.importer.import_package(
                submodules=['.api']
            )
            ep_api = ep.api.EnergyPlusAPI()

        return super().__init__(ep_api)

    def __call__(self, *args, console_output: bool = False):
        self._console_output(enabled=console_output)
        return super().__call__(*args)

__all__ = [
    BaseEnvironment,
    Environment
]
