"""
fvck.utilities

Small, dependency-free filesystem and process helpers.

This module is intentionally conservative about path validation because `fvck`
accepts user-supplied paths from a YAML configuration and a CLI. The helpers are
used to:

- identify file vs directory paths
- normalize/resolve relative paths
- move outputs under a build directory while preserving relative structure
- execute subprocess commands with captured output
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

import os
import subprocess

from pathlib import Path
from typing  import Tuple

class Utilities:
    """
    Namespace class for stateless helper functions.

    The class is used as a simple namespacing mechanism (no instances required).
    """

    @staticmethod
    def _has_invalid_path_chars(path: str) -> bool:
        """
        Check for characters that are invalid in Windows paths.

        Notes:
            - `:` is only allowed as a drive-letter separator (e.g. `C:\\...`).
            - This does not attempt to validate every platform nuance; it is a
              guardrail against obviously invalid user input.
        """
        invalid = set('<>"|?*')

        for i, ch in enumerate(path):
            if ch in invalid:
                return True

            # Allow drive letter colon (e.g. "C:\...").
            if ch == ':' and i == 1 and path[0].isalpha():
                continue

            if ch == ':':
                return True

        return False

    @staticmethod
    def file_exists(path: str) -> bool:
        """Return True if `path` exists and is a file."""
        return Path(path).is_file()

    @staticmethod
    def directory_exists(path: str) -> bool:
        """Return True if `path` exists and is a directory."""
        return Path(path).is_dir()

    @staticmethod
    def is_dirpath(path: str) -> bool:
        """
        Heuristically validate that a string looks like a directory path.

        This is used to validate CLI/config input *without* requiring the path
        to exist yet (e.g., `build/` can be created later).
        """
        if not isinstance(path, str) or not path.strip():
            return False

        if Utilities._has_invalid_path_chars(path):
            return False

        stripped = path.strip()

        if stripped in ('.', '..'):
            return True

        if len(stripped) >= 2 and stripped[1] == ':':
            return True

        if (
            os.path.sep in stripped
            or '/' in stripped
            or '\\' in stripped
        ):
            return True

        # Allow simple relative directory names like "build" or "out".
        # This intentionally does not require the directory to exist.
        return True

    @staticmethod
    def is_filepath(path: str) -> bool:
        """
        Heuristically validate that a string looks like a file path.

        Returns True for strings that:
        - contain a path separator OR
        - contain a filename extension
        """
        return (
            isinstance(path, str)
            and bool(path.strip())
            and not Utilities._has_invalid_path_chars(path)
            and (
                os.path.sep in path
                or '/' in path
                or '\\' in path
                or os.path.splitext(path)[1] != ''
            )
        )

    @staticmethod
    def make_abspath(working_dir: str, path: str) -> str:
        """Resolve `path` relative to `working_dir` and return an absolute path."""
        return str((Path(working_dir) / path).resolve())

    @staticmethod
    def move_under_build(project_root: str, source_path: str, build_dir: str = 'build') -> str:
        """
        Map `source_path` under `project_root/build_dir/` preserving relative layout.

        Example:
            project_root = /repo
            source_path  = /repo/src/a.c
            build_dir    = build

            => /repo/build/src/a.c
        """
        root = Path(project_root).resolve()
        src = Path(source_path).resolve()

        relative = src.relative_to(root)
        return str(root / build_dir / relative)

    @staticmethod
    def replace_extension(path: str, new_ext: str) -> str:
        """Return `path` with its suffix replaced by `new_ext`."""
        return str(Path(path).with_suffix(new_ext))

    @staticmethod
    def run_command(cmd: list[str], cwd: str | None = None, env: dict[str, str] | None = None) -> Tuple[int, str, str]:
        """
        Run a subprocess and capture stdout/stderr.

        Args:
            cmd: argv list (no shell interpolation).
            cwd: Optional working directory for the subprocess.
            env: Optional environment mapping for the subprocess.

        Returns:
            (returncode, stdout, stderr)
        """
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=cwd,
                env=env,
            )
            return result.returncode, result.stdout, result.stderr

        except FileNotFoundError:
            return 127, '', f'error: command not found: {cmd[0]}\n'
