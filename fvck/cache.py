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

import hashlib
import json
import os

from typing import Any

def _parse_raw_cache(raw_cache: object, *, num_sets: int) -> list[list[tuple[str, Any]]] | None:
    if not isinstance(raw_cache, list):
        return None

    if len(raw_cache) != num_sets:
        return None

    parsed: list[list[tuple[str, Any]]] = []
    for raw_set in raw_cache:
        if not isinstance(raw_set, list):
            return None

        parsed_set: list[tuple[str, Any]] = []
        for item in raw_set:
            if not isinstance(item, list | tuple) or len(item) != 2:
                return None
            key, value = item[0], item[1]
            parsed_set.append((str(key), value))

        parsed.append(parsed_set)

    return parsed

class SetAssociativeCache:

    def __init__(
        self,
        num_sets: int,
        associativity: int,
        path: str = 'build/cache.json'
    ) -> None:

        if num_sets <= 0:
            raise ValueError('num_sets must be greater than zero')

        if associativity <= 0:
            raise ValueError('associativity must be greater than zero')

        self.num_sets      : int                         = num_sets
        self.associativity : int                         = associativity
        self.path          : str                         = path
        self.cache         : list[list[tuple[str, Any]]] = [[] for _ in range(num_sets)]

        self._load()
        self._deduplicate()

    def get(self, key: str) -> Any | None:
        set_index  : int                   = self._get_set_index(key)
        target_set : list[tuple[str, Any]] = self.cache[set_index]

        for i, (k, v) in enumerate(target_set):

            if k == key:
                item = target_set.pop(i)
                target_set.append(item)
                self.save()
                return v

        return None

    def put(self, key: str, value: Any) -> None:
        set_index  : int                   = self._get_set_index(key)
        target_set : list[tuple[str, Any]] = self.cache[set_index]

        target_set[:] = [(k, v) for k, v in target_set if k != key]

        if len(target_set) >= self.associativity:
            target_set.pop(0)

        target_set.append((key, value))
        self.save()

    def save(self) -> None:
        self._deduplicate()

        directory: str = os.path.dirname(self.path)

        if directory:
            os.makedirs(directory, exist_ok=True)

        payload: dict[str, Any] = {
            'num_sets': self.num_sets,
            'associativity': self.associativity,
            'cache': self.cache,
        }

        tmp_path: str = f'{self.path}.tmp'

        with open(tmp_path, 'w', encoding='utf-8') as file:
            json.dump(payload, file, indent=4)

        os.replace(tmp_path, self.path)

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return

        with open(self.path, 'r', encoding='utf-8') as file:
            payload: Any = json.load(file)

        if not isinstance(payload, dict):
            return

        if payload.get('num_sets') != self.num_sets:
            return

        if payload.get('associativity') != self.associativity:
            return

        parsed_cache = _parse_raw_cache(payload.get('cache', []), num_sets=self.num_sets)
        if parsed_cache is None:
            return

        self.cache = parsed_cache

    def _deduplicate(self) -> None:
        new_cache: list[list[tuple[str, Any]]] = [[] for _ in range(self.num_sets)]

        for target_set in self.cache:
            for key, value in target_set:
                set_index       : int                   = self._get_set_index(key)
                canonical_set   : list[tuple[str, Any]] = new_cache[set_index]

                canonical_set[:] = [
                    (k, v)
                    for k, v in canonical_set
                    if k != key
                ]

                if len(canonical_set) >= self.associativity:
                    canonical_set.pop(0)

                canonical_set.append((key, value))

        self.cache = new_cache

    def __contains__(self, key: str) -> bool:
        set_index  : int                   = self._get_set_index(key)
        target_set : list[tuple[str, Any]] = self.cache[set_index]

        for k, _ in target_set:
            if k == key:
                return True

        return False

    def _get_set_index(self, key: str) -> int:
        digest: str = hashlib.sha256(key.encode('utf-8')).hexdigest()
        value : int = int(digest, 16)

        return value % self.num_sets

    def __repr__(self) -> str:
        return '\n'.join([f'Set {i}: {s}' for i, s in enumerate(self.cache)])

def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()

    with open(path, 'rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(chunk)

    return digest.hexdigest()

def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))

class TranslationUnitCache:

    def __init__(self, path: str = 'build/cache.json') -> None:
        self.path  : str            = path
        self.cache : dict[str, str] = {}

        self._load()

    def is_valid(self, source_path: str) -> bool:
        source_path = _norm(source_path)

        if not os.path.isfile(source_path):
            return False

        current_hash: str = _sha256_file(source_path)
        cached_hash : str | None = self.cache.get(source_path)

        return cached_hash == current_hash

    def is_dirty(self, source_path: str) -> bool:
        return not self.is_valid(source_path)

    def mark_valid(self, source_path: str) -> None:
        source_path = _norm(source_path)

        if not os.path.isfile(source_path):
            raise FileNotFoundError(source_path)

        self.cache[source_path] = _sha256_file(source_path)
        self.save()

    def invalidate(self, source_path: str) -> None:
        source_path = _norm(source_path)

        if source_path in self.cache:
            del self.cache[source_path]
            self.save()

    def save(self) -> None:
        directory: str = os.path.dirname(self.path)

        if directory:
            os.makedirs(directory, exist_ok=True)

        tmp_path: str = f'{self.path}.tmp'

        with open(tmp_path, 'w', encoding='utf-8') as file:
            json.dump(self.cache, file, indent=4, sort_keys=True)

        os.replace(tmp_path, self.path)

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return

        with open(self.path, 'r', encoding='utf-8') as file:
            payload: Any = json.load(file)

        if not isinstance(payload, dict):
            return

        self.cache = {
            str(path): str(file_hash)
            for path, file_hash in payload.items()
            if isinstance(path, str) and isinstance(file_hash, str)
        }
