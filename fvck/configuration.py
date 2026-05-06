"""
fvck.configuration

Configuration loading and validation for `fvck`.

The configuration format is explicitly versioned. Current version:

- `version: 1`

Version 1 schema (high level):

- `languages`: mapping of language name -> compiler config
  - `program_path`: compiler executable
  - `parameters`: list[str] default flags
  - `outputs`: mapping of input extension -> output extension (e.g. `.c: .o`)
  - `command`: argv template/structure used to build the compile command

- `targets`: list of named compile targets
  - `name`: unique identifier used by link targets
  - `sources`: list of globs/paths/directories expanded into translation units

- `link_targets`: list of named link targets
  - `name`: identifier
  - `from_targets`: list of target names whose objects will be linked
  - `output`: output path (relative to build dir unless absolute)
  - `program_path`, `parameters`, `command`: describe how to link

- `python_bindings` (optional): cached post-link steps intended as a convenience wrapper
  around setuptools/pip builds for python C extensions.

Location-aware errors:

This module uses a custom PyYAML loader that preserves line/column marks on
mappings/sequences. Validation errors are raised as `ConfigError` including
`path:line:column` to point to the failing block.
"""
# Copyright (C) 2026 Da'Jour J. Christophe. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import yaml

from .settings import Language, LinkTarget, PythonBinding, Settings, Target


@dataclass(frozen=True)
class ConfigLocation:
    """
    A concrete location within a configuration file.

    Attributes:
        path: Filesystem path to the configuration file.
        line: 1-based line number.
        column: 1-based column number.
    """
    path: str
    line: int
    column: int

    def format(self) -> str:
        return f'{self.path}:{self.line}:{self.column}'


class ConfigError(ValueError):
    """
    A configuration validation error.

    The string representation includes file location when available.
    """
    def __init__(self, message: str, *, loc: ConfigLocation | None = None) -> None:
        super().__init__(message)
        self.loc = loc

    def __str__(self) -> str:
        if self.loc is None:
            return super().__str__()
        return f'{self.loc.format()}: {super().__str__()}'


def _loc_from_node(config_path: str, node: yaml.Node | None) -> ConfigLocation | None:
    if node is None or not hasattr(node, 'start_mark') or node.start_mark is None:
        return None
    # PyYAML marks are 0-based.
    return ConfigLocation(config_path, int(node.start_mark.line) + 1, int(node.start_mark.column) + 1)


def _require_mapping(value: Any, *, what: str, loc: ConfigLocation | None) -> Mapping[str, Any]:
    """
    Validate that `value` is a mapping and return it.

    Args:
        value: Candidate object.
        what: Human-readable description of the value (used in error message).
        loc: Optional file location for diagnostics.
    """
    if not isinstance(value, dict):
        raise ConfigError(f'{what} must be a mapping', loc=loc)
    return value


def _require_str(value: Any, *, what: str, loc: ConfigLocation | None) -> str:
    """Validate that `value` is a non-empty string and return it."""
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f'{what} must be a string', loc=loc)
    return value


def _require_str_list(value: Any, *, what: str, loc: ConfigLocation | None) -> list[str]:
    """Validate that `value` is a `list[str]` and return a copy."""
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f'{what} must be list[str]', loc=loc)
    return list(value)


def _validate_command(command: Any, *, name: str, loc: ConfigLocation | None) -> Any:
    """
    Validate a command template/structure.

    `fvck` supports two representations:

    1) Legacy list[str] templates:
       - Strings can include placeholders like `{program}`, `{input}`.
       - The special literal `{parameters}` is spliced as argv items.

    2) Structured command blocks:
       - `command: { argv: [...] }`
       - argv items can be strings or token mappings:
         - `{ var: "parameters", splice: true }`
         - optional `prefix` / `separate` control how list items are emitted.

    This function validates structure only. Placeholder variable validity is
    checked later when building argv (and errors include the recorded `command_loc`).
    """
    if command is None:
        raise ConfigError(f'{name}: command is required', loc=loc)

    if isinstance(command, list) and all(isinstance(v, str) for v in command):
        return command

    if isinstance(command, dict):
        argv = command.get('argv')
        if not isinstance(argv, list):
            raise ConfigError(f'{name}: command.argv must be a list', loc=loc)

        for item in argv:
            if isinstance(item, str):
                continue
            if isinstance(item, dict):
                var = item.get('var')
                if not isinstance(var, str) or not var.strip():
                    raise ConfigError(f'{name}: command.argv var must be string', loc=loc)

                splice = item.get('splice', False)
                if not isinstance(splice, bool):
                    raise ConfigError(f'{name}: command.argv splice must be bool', loc=loc)

                prefix = item.get('prefix', None)
                if prefix is not None and not isinstance(prefix, str):
                    raise ConfigError(f'{name}: command.argv prefix must be string', loc=loc)

                separate = item.get('separate', False)
                if not isinstance(separate, bool):
                    raise ConfigError(f'{name}: command.argv separate must be bool', loc=loc)
                continue

            raise ConfigError(f'{name}: command.argv items must be string or mapping', loc=loc)

        return command

    raise ConfigError(f'{name}: command must be list[str] or mapping', loc=loc)


def load_config(path: str) -> None:
    """
    Load a versioned config file and populate `fvck.settings.Settings`.

    Args:
        path: Filesystem path to a YAML configuration file.

    Raises:
        ConfigError: If the configuration is missing required keys or contains invalid values.

    Side effects:
        Overwrites global state in `Settings` (languages, targets, link targets, python bindings).
    """
    class _Marked:
        __mark__: Any

    class MarkedDict(dict):
        __mark__: Any

    class MarkedList(list):
        __mark__: Any

    class MarkedLoader(yaml.SafeLoader):
        pass

    def _construct_mapping(loader: MarkedLoader, node: yaml.MappingNode) -> MarkedDict:
        mapping = MarkedDict()
        mapping.__mark__ = node.start_mark
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node)
            value = loader.construct_object(value_node)
            mapping[key] = value
        return mapping

    def _construct_sequence(loader: MarkedLoader, node: yaml.SequenceNode) -> MarkedList:
        seq = MarkedList()
        seq.__mark__ = node.start_mark
        for child in node.value:
            seq.append(loader.construct_object(child))
        return seq

    MarkedLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)
    MarkedLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_SEQUENCE_TAG, _construct_sequence)

    def _loc_from_obj(obj: Any) -> ConfigLocation | None:
        mark = getattr(obj, '__mark__', None)
        if mark is None:
            return None
        return ConfigLocation(path, int(mark.line) + 1, int(mark.column) + 1)

    with open(path, 'r', encoding='utf-8') as file:
        payload: Any = yaml.load(file, Loader=MarkedLoader)

    root_loc = _loc_from_obj(payload) or ConfigLocation(path, 1, 1)
    root = _require_mapping(payload, what='config', loc=root_loc)

    version = root.get('version')
    if version != 1:
        raise ConfigError('version must be 1', loc=root_loc)

    raw_languages = root.get('languages')
    raw_targets = root.get('targets')
    raw_links = root.get('link_targets')
    raw_python = root.get('python_bindings')

    if raw_languages is None:
        raise ConfigError('languages is required', loc=root_loc)
    if raw_targets is None:
        raise ConfigError('targets is required', loc=root_loc)
    if raw_links is None:
        raw_links = []
    if raw_python is None:
        raw_python = []

    if not isinstance(raw_languages, dict):
        raise ConfigError('languages must be a mapping', loc=_loc_from_obj(raw_languages) or root_loc)
    if not isinstance(raw_targets, list):
        raise ConfigError('targets must be a list', loc=_loc_from_obj(raw_targets) or root_loc)
    if not isinstance(raw_links, list):
        raise ConfigError('link_targets must be a list', loc=_loc_from_obj(raw_links) or root_loc)
    if not isinstance(raw_python, list):
        raise ConfigError('python_bindings must be a list', loc=_loc_from_obj(raw_python) or root_loc)

    languages: dict[str, Language] = {}
    for lang_name, raw in raw_languages.items():
        if not isinstance(lang_name, str):
            raise ConfigError('language name must be string', loc=root_loc)

        lang_key = lang_name.lower()
        raw_map_loc = _loc_from_obj(raw) or root_loc
        raw_map = _require_mapping(raw, what=f'languages.{lang_name}', loc=raw_map_loc)

        program_path = _require_str(raw_map.get('program_path'), what=f'{lang_key}: program_path', loc=raw_map_loc)
        parameters = raw_map.get('parameters', [])
        outputs = raw_map.get('outputs', {})
        command_obj = raw_map.get('command')
        command_loc = _loc_from_obj(command_obj) or raw_map_loc
        command = _validate_command(command_obj, name=lang_key, loc=command_loc)

        if not isinstance(parameters, list) or not all(isinstance(p, str) for p in parameters):
            raise ConfigError(f'{lang_key}: parameters must be list[str]', loc=root_loc)
        if not isinstance(outputs, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in outputs.items()):
            raise ConfigError(f'{lang_key}: outputs must be dict[str, str]', loc=root_loc)

        languages[lang_key] = Language(
            name=lang_key,
            program_path=program_path,
            parameters=list(parameters),
            outputs={str(k): str(v) for k, v in outputs.items()},
            command=command,
            command_loc=command_loc.format() if command_loc else None,
        )

    targets: list[Target] = []
    for i, item in enumerate(raw_targets):
        item_loc = _loc_from_obj(item) or root_loc
        if not isinstance(item, dict):
            raise ConfigError(f'targets[{i}] must be a mapping', loc=item_loc)
        name = _require_str(item.get('name'), what=f'targets[{i}].name', loc=item_loc)
        sources = _require_str_list(item.get('sources', []), what=f'targets[{i}].sources', loc=item_loc)
        targets.append(Target(name=name, sources=sources))

    link_targets: list[LinkTarget] = []
    for i, item in enumerate(raw_links):
        item_loc = _loc_from_obj(item) or root_loc
        if not isinstance(item, dict):
            raise ConfigError(f'link_targets[{i}] must be a mapping', loc=item_loc)
        name = _require_str(item.get('name'), what=f'link_targets[{i}].name', loc=item_loc)
        output = _require_str(item.get('output'), what=f'link_targets[{i}].output', loc=item_loc)
        from_targets = _require_str_list(item.get('from_targets', []), what=f'link_targets[{i}].from_targets', loc=item_loc)
        parameters = item.get('parameters', [])
        if not isinstance(parameters, list) or not all(isinstance(p, str) for p in parameters):
            raise ConfigError(f'link_targets[{i}].parameters must be list[str]', loc=item_loc)
        program_path = _require_str(item.get('program_path'), what=f'link_targets[{i}].program_path', loc=item_loc)
        command_obj = item.get('command')
        command_loc = _loc_from_obj(command_obj) or item_loc
        command = _validate_command(command_obj, name=f'link_targets[{i}]', loc=command_loc)

        link_targets.append(
            LinkTarget(
                name=name,
                program_path=program_path,
                parameters=list(parameters),
                output=output,
                from_targets=from_targets,
                command=command,
                command_loc=command_loc.format() if command_loc else None,
            )
        )

    python_bindings: list[PythonBinding] = []
    for i, item in enumerate(raw_python):
        item_loc = _loc_from_obj(item) or root_loc
        if not isinstance(item, dict):
            raise ConfigError(f'python_bindings[{i}] must be a mapping', loc=item_loc)

        name = _require_str(item.get('name'), what=f'python_bindings[{i}].name', loc=item_loc)
        project_root = _require_str(item.get('project_root', '.'), what=f'python_bindings[{i}].project_root', loc=item_loc)
        build_subdir = _require_str(item.get('build_subdir', '.python_bindings'), what=f'python_bindings[{i}].build_subdir', loc=item_loc)
        from_targets = _require_str_list(item.get('from_targets', []), what=f'python_bindings[{i}].from_targets', loc=item_loc)
        parameters = item.get('parameters', [])
        if not isinstance(parameters, list) or not all(isinstance(p, str) for p in parameters):
            raise ConfigError(f'python_bindings[{i}].parameters must be list[str]', loc=item_loc)
        inputs = _require_str_list(item.get('inputs', []), what=f'python_bindings[{i}].inputs', loc=item_loc)

        command_obj = item.get('command')
        command_loc = _loc_from_obj(command_obj) or item_loc
        command = _validate_command(command_obj, name=f'python_bindings[{i}]', loc=command_loc)

        python_bindings.append(
            PythonBinding(
                name=name,
                project_root=project_root,
                parameters=list(parameters),
                from_targets=from_targets,
                inputs=inputs,
                build_subdir=build_subdir,
                command=command,
                command_loc=command_loc.format() if command_loc else None,
            )
        )

    Settings.set_languages(languages)
    Settings.set_targets(targets)
    Settings.set_link_targets(link_targets)
    Settings.set_python_bindings(python_bindings)
