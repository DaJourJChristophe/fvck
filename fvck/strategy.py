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

from os.path import abspath

from .compiler  import CompileOptions
from .settings  import Language
from .utilities import Utilities

class CompilerStrategy:

    def configure(self, settings: Language, options: CompileOptions) -> list[str]:
        return [
            settings.program_path,
            *settings.parameters,

            '-o', options.output_filepath,

            options.target_filepath
        ]

    def invoke(self, settings: Language, options: CompileOptions) -> int:

        if not settings.program_path.strip():
            print('error: compiler program path is empty.')
            return (-1)

        args: list[str] = self.configure(settings, options)

        print(' '.join(args))

        code, out, err = Utilities.run_command(args)

        if code and err:
            print(err, end='')
            return (-1)

        print(out, end='')
        return 0
