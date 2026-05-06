'''
Copyright (C) 2026 Da'Jour J. Christophe. All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''
from __future__ import annotations

from os.path import abspath
from pathlib import Path

from argparse import Namespace

from .cache         import TranslationUnitCache
from .compiler      import CompileOptions
from .configuration import load_config
from .settings      import Language, Settings
from .strategy      import CompilerStrategy
from .utilities     import Utilities

from os import makedirs

class Fvck:

    def __init__(self) -> None:
        self.__workdir  : str = '.'
        self.__tu_cache : TranslationUnitCache = TranslationUnitCache()

    def run(self, args: Namespace) -> int:

        fvckrc_filepath: str = args.config
        build_dir: str = args.build

        load_config(abspath(fvckrc_filepath))

        build_dir: str = abspath(build_dir)
        makedirs(build_dir, exist_ok=True)

        return 0

        for index in range(1, len(args)):

            arg: str = args[index]

            if Utilities.is_filepath(arg):

                absfilepath: str = Utilities.make_abspath(self.__workdir, arg)

                if not Utilities.file_exists(absfilepath):
                    self.__tu_cache.invalidate(absfilepath)
                    print(f'error: the file {absfilepath} does not exist.')
                    return (-1)

                ext: str = Path(absfilepath).suffix.lower()

                langname: str = ext.lstrip('.')
                if langname not in Settings.languages():
                    print(f'error: the file language {langname} is not supported.')
                    return (-1)

                langsettings: Language = Settings.get_language(langname)
                options: CompileOptions = CompileOptions(
                    target_filepath=absfilepath,
                    target_fileext=ext,
                )

                if options.target_fileext not in langsettings.outputs:
                    print(f'error: the file extension {options.target_fileext} is not mapped to an output file extension.')
                    return (-1)

                options.output_filepath = Utilities.replace_extension(
                    options.target_filepath, langsettings.outputs[options.target_fileext])

                options.output_filepath = Utilities.move_under_build(
                    abspath('.'), options.output_filepath)

                if self.__tu_cache.is_valid(absfilepath) and Utilities.file_exists(options.output_filepath):
                    continue

                self.__tu_cache.invalidate(absfilepath)

                strategy: CompilerStrategy = CompilerStrategy()

                rc: int = strategy.invoke(langsettings, options)
                if rc:
                    return (-1)

                self.__tu_cache.mark_valid(absfilepath)

        print('[.] All build targets successfully completed.')
        return 0
