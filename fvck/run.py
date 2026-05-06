"""
fvck.run

Command-line entrypoint for the `fvck` tool.

This module provides:

- `launch()`: parse arguments and run a build
- `main()`: console script entrypoint for setuptools

The console script is configured in `pyproject.toml`:

`fvck = "fvck.run:main"`
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

from argparse import ArgumentParser, Namespace
from sys      import exit

from .fvck import Fvck

def launch() -> int:
    """
    Parse CLI arguments and execute a build.

    Returns:
        0 on success, -1 on failure (mirrors `Fvck.run`).
    """

    parser: ArgumentParser = ArgumentParser(
        description='A simple CLI example that greets you and adds numbers.',
    )

    parser.add_argument('-b', '--build', type=str, help='A filesystem path to the build directory')
    parser.add_argument('-c', '--config', type=str, help='A filesystem path to the .fvckrc')

    args: Namespace = parser.parse_args()

    fvck: Fvck = Fvck()

    return fvck.run(args)

def main() -> int:
    """Console script entrypoint."""
    return launch()

if __name__ == '__main__':
    exit(main())
