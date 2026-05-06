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

from dataclasses import dataclass
from typing     import ClassVar

@dataclass(frozen=True)
class Language:
    name: str
    program_path: str
    parameters: list[str]
    outputs: dict[str, str]

class Settings:
    _languages: ClassVar[dict[str, Language]] = {}

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
