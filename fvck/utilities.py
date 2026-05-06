'''
Copyright (C) 2026 Da'Jour J. Christophe. All rights reserved.

Licensed under the Apache License, Version 2.0 (the 'License');
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an 'AS IS' BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''
from __future__ import annotations

import os
import subprocess

from pathlib import Path
from typing  import Tuple

class Utilities:

    @staticmethod
    def file_exists(path: str) -> bool:
        return Path(path).is_file()

    @staticmethod
    def is_filepath(path: str) -> bool:
        return (
            isinstance(path, str)
            and bool(path.strip())
            and not any(ch in path for ch in '<>:"|?*')
            and (
                os.path.sep in path
                or '/' in path
                or '\\' in path
                or os.path.splitext(path)[1] != ''
            )
        )

    @staticmethod
    def make_abspath(working_dir: str, path: str) -> str:
        return str((Path(working_dir) / path).resolve())

    @staticmethod
    def move_under_build(project_root: str, source_path: str, build_dir: str = 'build') -> str:
        root = Path(project_root).resolve()
        src = Path(source_path).resolve()

        relative = src.relative_to(root)
        return str(root / build_dir / relative)

    @staticmethod
    def replace_extension(path: str, new_ext: str) -> str:
        return str(Path(path).with_suffix(new_ext))

    @staticmethod
    def run_command(cmd: list[str]) -> Tuple[int, str, str]:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
            return result.returncode, result.stdout, result.stderr

        except FileNotFoundError:
            return 127, '', f'error: command not found: {cmd[0]}\n'
