"""
fvck.settings

Data models and global settings registry for `fvck`.

`fvck` uses a simple "loaded configuration singleton" pattern:

- `fvck.configuration.load_config()` parses and validates YAML, then populates `Settings`.
- Build orchestration (`fvck.fvck.Fvck`) reads from `Settings` to materialize a build graph.

The dataclasses in this module are intentionally small and immutable (frozen=True)
to avoid accidental mutation during a build.
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
from typing     import ClassVar
from typing     import Any

@dataclass(frozen=True)
class Language:
    """
    Compiler configuration for a language.

    Attributes:
        name: Lowercased language identifier (e.g. "c", "cpp").
        program_path: Compiler executable.
        parameters: Default argv parameters for the compiler.
        outputs: Mapping from input extension (".c") to output extension (".o").
        command: Command template/structure used by `CommandBuilder`.
        command_loc: Optional `path:line:col` pointing at the YAML `command` block.
    """
    name: str
    program_path: str
    parameters: list[str]
    outputs: dict[str, str]
    # Required command description used by the build strategy.
    # Back-compat: a list[str] template is accepted by configuration parsing.
    command: Any
    command_loc: str | None = None

@dataclass(frozen=True)
class Linker:
    """
    Legacy linker configuration (retained for compatibility).

    New builds should prefer `LinkTarget` which is part of the explicit build graph.
    """
    program_path: str
    parameters: list[str]
    output: str
    command: Any

@dataclass(frozen=True)
class Target:
    """
    A named compile target in the build graph.

    Attributes:
        name: Unique identifier used by `LinkTarget.from_targets`.
        sources: List of entries expanded into translation units (globs/paths/directories).
    """
    name: str
    sources: list[str]

@dataclass(frozen=True)
class LinkTarget:
    """
    A named link target in the build graph.

    Attributes:
        name: Identifier for the link target.
        program_path: Linker executable.
        parameters: Default argv parameters for the linker.
        output: Output artifact path (relative to build dir unless absolute).
        from_targets: Names of compile targets whose objects are linked.
        command: Command template/structure used by `CommandBuilder`.
        command_loc: Optional `path:line:col` pointing at the YAML `command` block.
    """
    name: str
    program_path: str
    parameters: list[str]
    output: str
    from_targets: list[str]
    command: Any
    command_loc: str | None = None

@dataclass(frozen=True)
class PythonBinding:
    """
    Optional, cached "python bindings" step.

    This is intended as a convenience wrapper around external build tooling
    (setuptools/pip/build backends). It is loosely coupled:

    - Users can run setuptools on its own without `fvck`.
    - When configured, `fvck` can run a user-defined command and cache it based on
      declared inputs.

    Attributes:
        name: Binding identifier (used for cache keying and artifact directory naming).
        project_root: Working directory to run the command in.
        parameters: Optional list[str] available as `{parameters}` for templating.
        from_targets: Optional compile targets whose objects are exposed as `{objects}`.
        inputs: Globs (relative to `project_root`) used to compute cache validity.
        build_subdir: Subdirectory under build dir used for artifact isolation.
        command: Command template/structure used by `CommandBuilder`.
        command_loc: Optional `path:line:col` pointing at the YAML `command` block.
    """
    name: str
    project_root: str
    parameters: list[str]
    # Optional: depends on compiled objects from these targets (passed as `{objects}`).
    from_targets: list[str]
    # Declared inputs for caching (globs relative to project_root).
    inputs: list[str]
    # Where to place artifacts (absolute path resolved by fvck, passed as `{build_dir}`).
    build_subdir: str
    command: Any
    command_loc: str | None = None

class Settings:
    """
    Global registry populated by `fvck.configuration.load_config()`.

    This is a simple process-global store; it is not thread-safe for mutation.
    Callers should treat it as immutable during execution after `load_config()`.
    """
    _languages: ClassVar[dict[str, Language]] = {}
    _sources  : ClassVar[list[str]] = []
    _linkers  : ClassVar[list[Linker]] = []
    _targets  : ClassVar[list[Target]] = []
    _link_targets: ClassVar[list[LinkTarget]] = []
    _python_bindings: ClassVar[list[PythonBinding]] = []

    @classmethod
    def set_languages(cls, languages: dict[str, Language]) -> None:
        cls._languages = languages

    @classmethod
    def get_language(cls, name: str) -> Language:
        try:
            return cls._languages[name]
        except KeyError:
            raise KeyError(f'language not found: {name}')

    @classmethod
    def languages(cls) -> dict[str, Language]:
        return cls._languages.copy()

    @classmethod
    def set_sources(cls, sources: list[str]) -> None:
        cls._sources = sources

    @classmethod
    def sources(cls) -> list[str]:
        return cls._sources.copy()

    @classmethod
    def set_linkers(cls, linkers: list[Linker]) -> None:
        cls._linkers = linkers

    @classmethod
    def linkers(cls) -> list[Linker]:
        return cls._linkers.copy()

    @classmethod
    def set_targets(cls, targets: list[Target]) -> None:
        cls._targets = targets

    @classmethod
    def targets(cls) -> list[Target]:
        return cls._targets.copy()

    @classmethod
    def set_link_targets(cls, link_targets: list[LinkTarget]) -> None:
        cls._link_targets = link_targets

    @classmethod
    def link_targets(cls) -> list[LinkTarget]:
        return cls._link_targets.copy()

    @classmethod
    def set_python_bindings(cls, bindings: list[PythonBinding]) -> None:
        cls._python_bindings = bindings

    @classmethod
    def python_bindings(cls) -> list[PythonBinding]:
        return cls._python_bindings.copy()
