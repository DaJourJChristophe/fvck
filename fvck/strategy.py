"""
fvck.strategy

Strategy objects that turn validated configuration into executable commands.

This module intentionally separates:

- *Command construction* (template expansion and argv assembly), and
- *Command execution* (invoking subprocesses).

Command templates:

Commands are configured as either a legacy list[str] template, or a structured
`{argv: [...]}` representation. The builder expands placeholders (e.g. `{input}`)
and can splice list-valued variables into argv.

Error reporting:

When `Language.command_loc` / `LinkTarget.command_loc` / `PythonBinding.command_loc`
is populated by the config loader, errors raised during template expansion are
prefixed with `path:line:col` to point directly at the failing command block.
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

from os      import makedirs
from pathlib import Path
from typing  import cast

from .compiler  import CompileOptions
from .settings  import Language, LinkTarget, PythonBinding
from .utilities import Utilities

class CommandBuilder:
    """
    Build an argv list from a configured command representation.

    Args:
        variables: Mapping from placeholder name -> value. Values may be strings or list[str].
        context: Optional string included in error messages (typically `path:line:col`).

    Supported placeholders:
        - String placeholders: any `{name}` where `variables[name]` is a string.
        - Token mappings: `{var: "...", splice: bool, prefix: str?, separate: bool?}`.

    Notes:
        This is a pure builder; it does not execute the command.
    """

    def __init__(self, *, variables: dict[str, object], context: str | None = None) -> None:
        self._variables = variables
        self._context = context

    def _expand_string_template(self, text: str) -> str:
        out = text
        for key, value in self._variables.items():
            if isinstance(value, str):
                out = out.replace(f'{{{key}}}', value)
        return out

    def _emit_var_token(
        self,
        *,
        var_name: str,
        splice: bool,
        prefix: str | None,
        separate: bool,
    ) -> list[str]:
        if var_name not in self._variables:
            msg = f'unknown template variable: {var_name}'
            if self._context:
                msg = f'{self._context}: {msg}'
            raise ValueError(msg)

        value = self._variables[var_name]

        def _apply_prefix(item: str) -> list[str]:
            if prefix is None:
                return [item]
            if separate:
                return [prefix, item]
            return [f'{prefix}{item}']

        if splice:
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                msg = f'variable {var_name} is not list[str] for splice'
                if self._context:
                    msg = f'{self._context}: {msg}'
                raise ValueError(msg)

            out: list[str] = []
            for v in value:
                out.extend(_apply_prefix(v))
            return out

        if not isinstance(value, str):
            msg = f'variable {var_name} is not string'
            if self._context:
                msg = f'{self._context}: {msg}'
            raise ValueError(msg)

        return _apply_prefix(value)

    def build_argv(self, command: object) -> list[str]:
        # Back-compat: list[str] templates, with `{parameters}` splicing.
        if isinstance(command, list) and all(isinstance(v, str) for v in command):
            expanded: list[str] = []
            for item in command:
                if item == '{parameters}':
                    expanded.extend(cast(list[str], self._variables['parameters']))
                    continue
                expanded.append(self._expand_string_template(item))
            return expanded

        if not isinstance(command, dict):
            msg = 'command must be list[str] or mapping'
            if self._context:
                msg = f'{self._context}: {msg}'
            raise ValueError(msg)

        argv = command.get('argv')
        if not isinstance(argv, list):
            msg = 'command.argv must be a list'
            if self._context:
                msg = f'{self._context}: {msg}'
            raise ValueError(msg)

        expanded: list[str] = []
        for item in argv:
            if isinstance(item, str):
                expanded.append(self._expand_string_template(item))
                continue

            if not isinstance(item, dict):
                msg = 'command.argv items must be string or mapping'
                if self._context:
                    msg = f'{self._context}: {msg}'
                raise ValueError(msg)

            var = item.get('var')
            if not isinstance(var, str) or not var.strip():
                msg = 'command.argv var must be string'
                if self._context:
                    msg = f'{self._context}: {msg}'
                raise ValueError(msg)

            splice = item.get('splice', False)
            prefix = item.get('prefix', None)
            separate = item.get('separate', False)

            if not isinstance(splice, bool):
                msg = 'command.argv splice must be bool'
                if self._context:
                    msg = f'{self._context}: {msg}'
                raise ValueError(msg)
            if prefix is not None and not isinstance(prefix, str):
                msg = 'command.argv prefix must be string'
                if self._context:
                    msg = f'{self._context}: {msg}'
                raise ValueError(msg)
            if not isinstance(separate, bool):
                msg = 'command.argv separate must be bool'
                if self._context:
                    msg = f'{self._context}: {msg}'
                raise ValueError(msg)

            expanded.extend(
                self._emit_var_token(
                    var_name=var,
                    splice=splice,
                    prefix=prefix,
                    separate=separate,
                )
            )

        return expanded


class CompilerStrategy:
    """
    Compile translation units into object files using a configured `Language`.

    The caller supplies `CompileOptions` which includes:
    - `input` translation unit path
    - `output` object file path
    - optional `depfile` output path (for compilers that support it)
    """

    def _template_vars(self, settings: Language, options: CompileOptions) -> dict[str, object]:
        return {
            'program': settings.program_path,
            'parameters': list(settings.parameters),
            'input': options.target_filepath,
            'output': options.output_filepath,
            'depfile': options.depfile_filepath,
        }

    def configure(self, settings: Language, options: CompileOptions) -> list[str]:
        builder = CommandBuilder(variables=self._template_vars(settings, options), context=settings.command_loc)
        return builder.build_argv(settings.command)

    def execute(self, settings: Language, options: CompileOptions) -> tuple[int, str, str, list[str]]:
        args: list[str] = self.configure(settings, options)
        code, out, err = Utilities.run_command(args)
        return code, out, err, args

    def invoke(self, settings: Language, options: CompileOptions) -> int:

        if not settings.program_path.strip():
            print('error: compiler program path is empty.')
            return (-1)

        dirpath: Path = Path(options.output_filepath).parent
        makedirs(dirpath, exist_ok=True)

        code, out, err, args = self.execute(settings, options)

        print(' '.join(args))

        if code and err:
            print(err, end='')
            return (-1)

        print(out, end='')
        return 0


class LinkerStrategy:
    """
    Link object files into an output artifact using a configured `LinkTarget`.

    A link target is a graph node: it depends on objects produced by one or more
    compile targets (resolved in `fvck.fvck.Fvck`).
    """
    def configure(self, linker: LinkTarget, *, objects: list[str], output_path: str) -> list[str]:
        builder = CommandBuilder(
            variables={
                'program': linker.program_path,
                'parameters': list(linker.parameters),
                'objects': list(objects),
                'output': output_path,
            }
            ,context=linker.command_loc
        )
        return builder.build_argv(linker.command)

    def execute(self, linker: LinkTarget, *, objects: list[str], output_path: str) -> tuple[int, str, str, list[str]]:
        args = self.configure(linker, objects=objects, output_path=output_path)
        code, out, err = Utilities.run_command(args)
        return code, out, err, args

    def invoke(self, linker: LinkTarget, *, objects: list[str], output_path: str) -> int:
        if not linker.program_path.strip():
            print('error: linker program path is empty.')
            return (-1)

        if not objects:
            print('error: no objects to link.')
            return (-1)

        dirpath: Path = Path(output_path).parent
        makedirs(dirpath, exist_ok=True)

        code, out, err, args = self.execute(linker, objects=objects, output_path=output_path)
        print(' '.join(args))
        if code and err:
            print(err, end='')
            return (-1)

        print(out, end='')
        return 0


class PythonBindingStrategy:
    """
    Execute a cached python binding step (e.g., setuptools/pip convenience wrapper).

    This strategy is intentionally generic: it only builds argv from the configured
    `PythonBinding.command` and runs it with `cwd=project_root`.

    Artifact isolation is achieved by encouraging users to route setuptools build
    output directories under `{build_dir}`.
    """
    def configure(
        self,
        binding: PythonBinding,
        *,
        python_exe: str,
        project_root: str,
        build_dir: str,
        objects: list[str],
    ) -> list[str]:
        builder = CommandBuilder(
            variables={
                'python': python_exe,
                'program': python_exe,
                'parameters': list(binding.parameters),
                'project_root': project_root,
                'build_dir': build_dir,
                'objects': list(objects),
            },
            context=binding.command_loc,
        )
        return builder.build_argv(binding.command)

    def execute(
        self,
        binding: PythonBinding,
        *,
        python_exe: str,
        project_root: str,
        build_dir: str,
        objects: list[str],
    ) -> tuple[int, str, str, list[str]]:
        argv = self.configure(
            binding,
            python_exe=python_exe,
            project_root=project_root,
            build_dir=build_dir,
            objects=objects,
        )
        code, out, err = Utilities.run_command(argv, cwd=project_root)
        return code, out, err, argv
