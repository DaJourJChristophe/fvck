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

from os import makedirs
from os.path import abspath

from argparse import ArgumentParser, Namespace

from .fvck import Fvck

def launch() -> int:

    parser: ArgumentParser = ArgumentParser(
        description='A simple CLI example that greets you and adds numbers.',
    )

    # parser.add_argument('name', help='The name of the person to greet')
    parser.add_argument('-b', '--build', type=str, help='A filesystem path to the build directory')
    parser.add_argument('-c', '--config', type=str, help='A filesystem path to the .fvckrc')
    # parser.add_argument('-v', '--verbose', action='store_true', help='Increase output verbosity')
    # parser.add_argument('numbers', nargs=2, type=float, help='Two numbers to add together')

    args: Namespace = parser.parse_args()

    fvck: Fvck = Fvck()

    return fvck.run(args)

def main() -> int:
    return launch()
