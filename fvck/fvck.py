"""
fvck.fvck

This module provides the main build orchestration entrypoint (`Fvck`).

The high-level flow is:

1. Load and validate a versioned YAML configuration (`fvck.configuration.load_config`).
2. Materialize an explicit build graph:
   - `Target` nodes expand `sources` entries into concrete file paths.
   - Each source is compiled into an object file under the configured build directory.
   - `LinkTarget` nodes link only the object files from the configured `from_targets` list.
3. Cache translation units (TUs) based on:
   - the *exact* configured compile argv (salt), and
   - compiler-produced depfiles (`-MMD -MF`) to capture true include dependencies.
4. Optionally run cached "python binding" steps (e.g., setuptools/pip wrappers) in a
   loosely coupled way using `python_bindings`.

Concurrency:

- Compilation jobs are independent and are executed in parallel.
- Link jobs are executed after compilation; independent link targets run in parallel.
- Optional python binding jobs run after linking; independent bindings run in parallel.

All build artifacts are placed under the user-provided build directory.
"""
# Copyright (C) 2026 Da'Jour J. Christophe. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import os
import threading
import sys

from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor, as_completed
from glob import glob
from os import makedirs
from os.path import abspath
from pathlib import Path

from .cache import TranslationUnitCache
from .compiler import CompileOptions
from .configuration import ConfigError, load_config
from .settings import Language, LinkTarget, PythonBinding, Settings, Target
from .step_cache import StepCache
from .strategy import CompilerStrategy, LinkerStrategy, PythonBindingStrategy
from .utilities import Utilities


class Fvck:
    """
    Build orchestrator for `fvck`.

    Instances are lightweight and are typically created per process invocation.

    Attributes:
        __workdir: The working directory used to resolve relative paths from config.
        __tu_cache: Cache used to validate/skip compilation of translation units.
    """
    def __init__(self) -> None:
        """Create a new orchestrator with an empty in-memory build state."""
        self.__workdir: str = '.'
        self.__tu_cache: TranslationUnitCache = TranslationUnitCache()

    def _is_glob(self, pattern: str) -> bool:
        """
        Return True if `pattern` looks like a glob expression.

        This is a heuristic used to decide how to expand `sources` entries.
        """
        return any(ch in pattern for ch in '*?[')

    def _expand_sources(self, entry: str) -> list[str]:
        """
        Expand a `Target.sources` entry into concrete file paths.

        The `entry` can be:

        - A glob pattern (relative to `__workdir`) like `src/**/*.c`.
        - An absolute glob pattern.
        - A directory path (recursively includes all files under it).
        - A single file path.

        Returns:
            A list of absolute file paths. The list may contain duplicates; callers
            are expected to deduplicate per-target.
        """
        if not isinstance(entry, str) or not entry.strip():
            return []

        entry_abs: str = Utilities.make_abspath(self.__workdir, entry)

        if self._is_glob(entry):
            if Path(entry_abs).is_absolute():
                return [str(Path(p).resolve()) for p in glob(entry_abs, recursive=True) if Path(p).is_file()]

            base_dir = Path(self.__workdir)
            return [str(p.resolve()) for p in base_dir.glob(entry) if p.is_file()]

        if Utilities.directory_exists(entry_abs):
            return [str(p) for p in Path(entry_abs).rglob('*') if p.is_file()]

        return [entry_abs]

    def run(self, args: Namespace) -> int:
        """
        Execute a configured build.

        Args:
            args: Parsed CLI args (must contain `config` and `build` attributes).

        Returns:
            0 on success, -1 on failure.

        Side effects:
            - Creates directories and writes build artifacts under `args.build`.
            - Writes TU cache state under `build/cache.json` (or configured cache path).
            - May invoke external tools (compiler, linker, python commands).
        """
        fvckrc_filepath: str = args.config
        build_dir: str = args.build

        if not fvckrc_filepath or not Utilities.file_exists(fvckrc_filepath):
            print(f'error: the configuration file {fvckrc_filepath} does not exist.')
            return -1

        if not build_dir or not Utilities.is_dirpath(build_dir):
            print(f'error: invalid build directory path: {build_dir}')
            return -1

        try:
            load_config(abspath(fvckrc_filepath))
        except ConfigError as e:
            print(f'error: {e}')
            return -1

        build_dir = abspath(build_dir)
        makedirs(build_dir, exist_ok=True)

        # Build graph:
        # - compile nodes: one per (target, source)
        # - link nodes: one per link_target, depends on target objects
        targets: list[Target] = Settings.targets()
        link_targets: list[LinkTarget] = Settings.link_targets()

        languages: dict[str, Language] = Settings.languages()
        input_ext_to_lang: dict[str, Language] = {}
        for lang in languages.values():
            for input_ext in lang.outputs.keys():
                input_ext_to_lang[input_ext.lower()] = lang

        compiler_strategy = CompilerStrategy()
        max_workers = max(1, (os.cpu_count() or 1))
        print_lock = threading.Lock()

        # Expand target sources -> unique file list per target.
        expanded_target_sources: dict[str, list[str]] = {}
        for target in targets:
            expanded: list[str] = []
            for entry in target.sources:
                expanded.extend(self._expand_sources(entry))

            seen: set[str] = set()
            unique: list[str] = []
            for p in expanded:
                norm = str(Path(p).resolve()).lower()
                if norm in seen:
                    continue
                seen.add(norm)
                unique.append(p)

            expanded_target_sources[target.name] = unique

        # Compile job: (target_name, source_abs, language, options, salt)
        # The salt is derived from the user-provided argv (after template expansion).
        compile_jobs: list[tuple[str, str, Language, CompileOptions, str]] = []
        target_objects: dict[str, list[str]] = {t.name: [] for t in targets}

        for target in targets:
            for src in expanded_target_sources.get(target.name, []):
                if not Utilities.file_exists(src):
                    self.__tu_cache.invalidate(src)
                    print(f'error: the file {src} does not exist.')
                    return -1

                ext = Path(src).suffix.lower()
                if ext not in input_ext_to_lang:
                    continue

                lang = input_ext_to_lang[ext]
                if ext not in lang.outputs:
                    continue

                out_ext = lang.outputs[ext]

                output_obj = Utilities.move_under_build(
                    abspath('.'),
                    Utilities.replace_extension(src, out_ext),
                    build_dir=build_dir,
                )

                depfile = f'{output_obj}.d'

                options = CompileOptions(
                    target_filepath=abspath(src),
                    target_fileext=ext,
                    output_filepath=output_obj,
                    depfile_filepath=depfile,
                )

                makedirs(str(Path(options.output_filepath).parent), exist_ok=True)

                # Signature/salt: exact argv produced by user config.
                argv = compiler_strategy.configure(lang, options)
                salt = '\0'.join(argv)

                if self.__tu_cache.is_valid(src, salt=salt) and Utilities.file_exists(output_obj):
                    target_objects[target.name].append(output_obj)
                    continue

                compile_jobs.append((target.name, src, lang, options, salt))

        def _compile_one(job: tuple[str, str, Language, CompileOptions, str]) -> tuple[str, str, int]:
            """
            Compile a single translation unit.

            This is executed inside a thread pool.

            Returns:
                (target_name, object_path, return_code)
            """
            tgt, src, lang, opts, salt = job
            self.__tu_cache.invalidate(src)
            try:
                code, out, err, argv = compiler_strategy.execute(lang, opts)
            except ValueError as e:
                with print_lock:
                    print(f'error: {e}')
                return tgt, opts.output_filepath, -1
            if code == 0:
                # Record the depfile-derived dependencies for future cache hits.
                self.__tu_cache.mark_valid(src, salt=salt, depfile_path=opts.depfile_filepath or None)
                with print_lock:
                    print(' '.join(argv))
                    if out:
                        print(out, end='')
                return tgt, opts.output_filepath, 0

            with print_lock:
                print(' '.join(argv))
                if err:
                    print(err, end='')
            return tgt, opts.output_filepath, -1

        if compile_jobs:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = [pool.submit(_compile_one, job) for job in compile_jobs]
                for fut in as_completed(futures):
                    tgt, obj, rc = fut.result()
                    if rc:
                        return -1
                    target_objects[tgt].append(obj)

        # Link jobs: each link target depends on objects from its `from_targets` list.
        linker_strategy = LinkerStrategy()

        def _objects_for_link(link: LinkTarget) -> list[str]:
            """
            Resolve the object list for a link target.

            The ordering is stable to improve determinism of the link step.
            """
            objs: list[str] = []
            for tgt in link.from_targets:
                objs.extend(target_objects.get(tgt, []))
            # Stable ordering helps reproducibility.
            return sorted(set(objs), key=lambda p: str(Path(p).resolve()).lower())

        link_jobs: list[tuple[LinkTarget, list[str], str]] = []
        for link in link_targets:
            objs = _objects_for_link(link)
            if not objs:
                print(f'error: link target {link.name} has no objects (from_targets={link.from_targets})')
                return -1

            out = link.output
            if not Path(out).is_absolute():
                out = str((Path(build_dir) / out).resolve())
            link_jobs.append((link, objs, out))

        def _link_one(job: tuple[LinkTarget, list[str], str]) -> int:
            """
            Link one configured output artifact.

            Returns:
                0 on success, -1 on failure.
            """
            link, objs, out = job
            try:
                code, out_text, err, argv = linker_strategy.execute(link, objects=objs, output_path=out)
            except ValueError as e:
                with print_lock:
                    print(f'error: {e}')
                return -1
            with print_lock:
                print(' '.join(argv))
                if code and err:
                    print(err, end='')
                if out_text:
                    print(out_text, end='')
            return 0 if code == 0 else -1

        if link_jobs:
            with ThreadPoolExecutor(max_workers=min(len(link_jobs), max_workers)) as pool:
                futures = [pool.submit(_link_one, job) for job in link_jobs]
                for fut in as_completed(futures):
                    if fut.result():
                        return -1

        # Optional: setuptools/python C-binding wrapper steps (cached).
        bindings: list[PythonBinding] = Settings.python_bindings()
        if bindings:
            step_cache = StepCache(path=str((Path(build_dir) / '.fvck' / 'step_cache.json').resolve()))
            binding_strategy = PythonBindingStrategy()
            python_exe = sys.executable

            def _objects_for_binding(binding: PythonBinding) -> list[str]:
                """
                Resolve the object list for a python binding step.

                Bindings can be configured to depend on compiled objects (e.g. for
                passing static libs or object lists into an extension build).
                """
                objs: list[str] = []
                for tgt in binding.from_targets:
                    objs.extend(target_objects.get(tgt, []))
                return sorted(set(objs), key=lambda p: str(Path(p).resolve()).lower())

            def _binding_job(binding: PythonBinding) -> int:
                """
                Execute a cached python binding step.

                The step is skipped if:
                - the declared `inputs` resolve to a stable file list, AND
                - all those inputs match the cached content hashes for the step argv.

                Returns:
                    0 on success, -1 on failure.
                """
                project_root = str((Path(binding.project_root).resolve()) if Path(binding.project_root).is_absolute() else (Path(self.__workdir) / binding.project_root).resolve())
                binding_build_dir = str((Path(build_dir) / binding.build_subdir / binding.name).resolve())
                makedirs(binding_build_dir, exist_ok=True)

                objects = _objects_for_binding(binding)
                argv = binding_strategy.configure(
                    binding,
                    python_exe=python_exe,
                    project_root=project_root,
                    build_dir=binding_build_dir,
                    objects=objects,
                )
                salt = '\0'.join(argv)

                deps = step_cache.resolve_inputs(project_root=project_root, patterns=binding.inputs)
                key = f'python_binding:{binding.name}'

                if deps and step_cache.is_valid(key=key, deps=deps, salt=salt):
                    return 0

                code, out_text, err, argv2 = binding_strategy.execute(
                    binding,
                    python_exe=python_exe,
                    project_root=project_root,
                    build_dir=binding_build_dir,
                    objects=objects,
                )
                with print_lock:
                    print(' '.join(argv2))
                    if code and err:
                        print(err, end='')
                    if out_text:
                        print(out_text, end='')

                if code == 0 and deps:
                    step_cache.mark_valid(key=key, deps=deps, salt=salt)
                    return 0
                return -1

            with ThreadPoolExecutor(max_workers=min(len(bindings), max_workers)) as pool:
                futures = [pool.submit(_binding_job, b) for b in bindings]
                for fut in as_completed(futures):
                    if fut.result():
                        return -1

        print('[.] All build targets successfully completed.')
        return 0
