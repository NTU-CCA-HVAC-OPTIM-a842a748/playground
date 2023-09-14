# TODO ...

import contextlib
import builtins

@contextlib.contextmanager
def temporary_attr(o, name: str):
    a = builtins.getattr(o, name)
    try: yield
    finally: builtins.setattr(o, name, a)

import sys

@contextlib.contextmanager
def temporary_search_path(*paths):
    with temporary_attr(sys, 'path'):
        setattr(sys, 'path', [str(p) for p in paths])
        try: yield
        finally: pass

import os
import shutil

def find_energyplus():
    return os.path.dirname(
        os.path.realpath(shutil.which('energyplus'))
    )
# TODO
import os
os.environ['PATH'] += f''':{os.path.expanduser('~/.local/bin')}'''

energyplus_path = find_energyplus()
#energyplus_path = os.path.expanduser('~/.local/EnergyPlus-23-1-0')
with temporary_search_path(energyplus_path):
    import pyenergyplus as eplus
    import pyenergyplus.api
##### TODO !!!!!!!!!!!!!!!!!!!!!




import typing


    
import packaging
import io
import csv
import collections

import pandas as pd

import typing
import types



class Environment:
    _ep_api = eplus.api.EnergyPlusAPI()
    assert (
        packaging.version.Version(_ep_api.api_version()) 
            >= packaging.version.Version('0.2')
    )

    def __init__(self):
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
 
            return {title: pd.DataFrame(d[title], columns=colnames[title]) for title in d}
    
    class Specs(typing.NamedTuple):
        actuators: pd.DataFrame
        # TODO ...
        variables: pd.DataFrame

    @property
    def specs(self) -> Specs:
        return self.Specs(
            actuators=self._available_data['**ACTUATORS**'][[
                'component_type', 
                'control_type', 
                'actuator_key'
            ]],
            #internal_variables=...,
            #plugin_global_variables=...,
            #trends=...,
            variables=self._available_data['**VARIABLES**'][[
                'variable_name', 
                'variable_key'
            ]]
        )
    
    class Component:
        class Specs:
            pass

        def __init__(self, environment: 'Environment'):
            self._env = environment

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
            
        def __init__(
            self, 
            specs: Specs,
            environment: 'Environment'
        ):
            super().__init__(environment)
            self._specs = self.Specs(specs)
            
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
        def specs(self):
            return self._specs

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
            super().__init__(environment)
            self._specs = self.Specs(**specs)

            # TODO
            # NOTE alloc
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

    # TODO
    @property
    def _TODO_callbacks(self):    
        class _TODO_dataclass:
            after_component_get_input: typing.Callable

            def __delitem__(self, name):
                # TODO raise not supported
                raise Exception()

            def __setitem__(self, name, value):
                pass

            def __getitem__(self, name):
                pass


        def _ep_set_callback(event: str, callback):
            _ep_runtime = self._ep_api.runtime
            _ep_callback_setters = {
                'after_component_input': _ep_runtime.callback_after_component_get_input
            }

            _ep_callback_setters[event](self._ep_state, callback)


        # self._ep_api.runtime.callback_<...>(self._ep_state, callable)
        pass
