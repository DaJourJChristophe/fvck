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

from typing import Any

import yaml

from .settings import Settings, Language

def load_config(path: str) -> None:

    with open(path, 'r', encoding='utf-8') as file:
        payload: Any = yaml.safe_load(file)

    if not isinstance(payload, dict):
        raise ValueError('config must be a mapping')

    raw_languages = payload.get('languages')

    if not isinstance(raw_languages, dict):
        raise ValueError('languages must be a mapping')

    languages: dict[str, Language] = {}

    for name, raw in raw_languages.items():

        if not isinstance(name, str):
            raise ValueError('language name must be string')

        if not isinstance(raw, dict):
            raise ValueError(f'language {name} must be a mapping')

        name = name.lower()

        program_path = raw.get('program_path')
        parameters   = raw.get('parameters', [])
        outputs      = raw.get('outputs', {})

        if not isinstance(program_path, str):
            raise ValueError(f'{name}: program_path must be string')

        if not isinstance(parameters, list) or not all(isinstance(p, str) for p in parameters):
            raise ValueError(f'{name}: parameters must be list[str]')

        if not isinstance(outputs, dict) or not all(
            isinstance(k, str) and isinstance(v, str)
            for k, v in outputs.items()
        ):
            raise ValueError(f'{name}: outputs must be dict[str, str]')

        languages[name] = Language(
            name=name,
            program_path=program_path,
            parameters=parameters,
            outputs=outputs
        )

    Settings.set_languages(languages)
