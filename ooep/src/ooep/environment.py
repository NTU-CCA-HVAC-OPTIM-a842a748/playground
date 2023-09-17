import abc
import typing
import collections
import io
import csv

import packaging
import pandas as pd

from . import utils


class Environment:
    def __init__(self, ep_api: 'pyenergyplus.api.EnergyPlusAPI' = None):
        # TODO
        self._ep_api = ep_api
        if self._ep_api is None:
            ep = utils.energyplus.importer.import_package(
                submodules=['api']
            )
            self._ep_api = ep.api.EnergyPlusAPI()

        assert (
            packaging.version.Version(self._ep_api.api_version())
                >= packaging.version.Version('0.2')
        )

        pass

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

    @property
    def _ready(self):
        return self._ep_api.exchange.api_data_fully_ready(self._ep_state)

    @property
    def _available_data(self):
        # TODO NOTE headsup! upcoming version will include `get_api_data`
        def _ep_csv_reader(f, default_title=None):
            title = default_title
            for row in csv.reader(f):
                if len(row) == 1:
                    title = row.pop()
                yield title, row

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

    class Specs(typing.NamedTuple):
        actuators: pd.DataFrame
        # TODO ...
        variables: pd.DataFrame
        # TODO ...
        events: pd.DataFrame

    @property
    def specs(self) -> Specs:
        return self.Specs(
            actuators=self._available_data['**ACTUATORS**'][[*self.Actuator.Specs._fields]],
            #internal_variables=...,
            #plugin_global_variables=...,
            #trends=...,
            variables=self._available_data['**VARIABLES**'][[*self.Variable.Specs._fields]],
            # TODO ... !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            events=pd.DataFrame(self.Event._get_ep_available_specs())
        )

    class Component(abc.ABC):
        class Specs(typing.NamedTuple):
            ...

        def __init__(self, specs: Specs | typing.Mapping, environment: 'Environment'):
            self._specs = self.Specs(**specs)
            self._env = environment

        @property
        def specs(self):
            return self._specs

    def _component(
        self,
        specs: typing.Mapping | Component.Specs | pd.DataFrame,
        constructor: typing.Callable[[], Component]
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
            # TODO
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

    def actuator(self, specs: typing.Mapping | Actuator.Specs | pd.DataFrame) -> Actuator:
        return self._component(
            specs,
            lambda d: self.Actuator(d, environment=self)
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
            return self._env._ep_api.exchange.get_variable_handle(
                self._env._ep_state,
                variable_name=self._specs.variable_name,
                variable_key=self._specs.variable_key
            )

        @property
        def specs(self):
            return self._specs

        @property
        def value(self):
            return self._env._ep_api.exchange.get_variable_value(
                self._env._ep_state,
                variable_handle=self._ep_handle
            )

    def variable(self, specs: typing.Mapping | Variable.Specs | pd.DataFrame) -> Variable:
        return self._component(
            specs,
            lambda d: self.Variable(d, environment=self)
        )

    class Event(Component):
        class Specs(typing.NamedTuple):
            event_name: str

        @classmethod
        def _get_ep_callback_setters(cls):
            # TODO NOTE state:
            # TODO NOTE each state only has a single callback; states dont share callbacks!
            def _state_callback_setter(state, base_setter):
                return lambda callback: base_setter(
                    state,
                    lambda _: callback()
                )

            def _data_callback_setter(state, base_setter):
                return lambda callback: base_setter(
                    state, callback
                )

            runtime: eplus.api.runtime
            return {
                # state callbacks
                cls.Specs('after_component_input'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.callback_after_component_get_input
                    ),
                cls.Specs('after_new_environment_warmup_complete'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.after_new_environment_warmup_complete
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
                        state, runtime.begin_system_timestep_before_predictor
                    ),
                cls.Specs('begin_zone_timestep_after_init_heat_balance'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.begin_zone_timestep_after_init_heat_balance
                    ),
                cls.Specs('begin_zone_timestep_before_init_heat_balance'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.begin_zone_timestep_before_init_heat_balance
                    ),
                cls.Specs('begin_zone_timestep_before_set_current_weather'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.begin_zone_timestep_before_set_current_weather
                    ),
                cls.Specs('end_system_sizing'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.callback_end_system_sizing
                    ),
                cls.Specs('end_system_timestep_after_hvac_reporting'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.end_system_timestep_after_hvac_reporting
                    ),
                cls.Specs('end_system_timestep_before_hvac_reporting'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.end_system_timestep_before_hvac_reporting
                    ),
                cls.Specs('end_zone_sizing'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.callback_end_zone_sizing
                    ),
                cls.Specs('end_zone_timestep_after_zone_reporting'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.end_zone_timestep_after_zone_reporting
                    ),
                cls.Specs('end_zone_timestep_before_zone_reporting'):
                    lambda state, runtime: _state_callback_setter(
                        state, runtime.end_zone_timestep_before_zone_reporting
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
            raise NotImplementedError('function not available')

        @callback.setter
        def callback(self, f):
            self._get_ep_callback_setters()[self._specs](
                state=self._env._ep_state,
                runtime=self._env._ep_api.runtime
            )(f)

    def event(self, specs: typing.Mapping | Event.Specs | pd.DataFrame) -> Event:
        return self._component(
            specs,
            lambda d: self.Event(d, environment=self)
        )

__all__ = [
    Environment
]
