"""
fvck.compiler

Lightweight data container describing a single compilation unit invocation.

`CompileOptions` is passed into `CompilerStrategy` to allow command templates to refer to:

- `{input}`: the translation unit path
- `{output}`: the output object file path
- `{depfile}`: an optional compiler-produced depfile path
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

class CompileOptions:
    """
    Options describing compilation of a single source file.

    Attributes:
        target_filepath: Absolute path to the source file to compile.
        target_fileext: Lowercased extension of the source file (e.g. ".c").
        output_filepath: Absolute path to the output object file.
        depfile_filepath: Absolute path where the compiler should emit a depfile (if supported).
    """

    target_filepath: str = ''
    target_fileext : str = ''
    output_filepath: str = ''
    depfile_filepath: str = ''

    def __init__(self, target_filepath: str = '',
                       target_fileext : str = '',
                       output_filepath: str = '',
                       depfile_filepath: str = '') -> None:

        self.target_filepath = target_filepath
        self.target_fileext  = target_fileext
        self.output_filepath = output_filepath
        self.depfile_filepath = depfile_filepath
