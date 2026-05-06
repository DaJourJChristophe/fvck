"""
fvck.cache

Caching primitives used by `fvck`.

This module contains:

- `SetAssociativeCache`: A small JSON-persisted set-associative cache with LRU behavior
  within each set. This is a general utility used elsewhere in the project.

- `TranslationUnitCache`: The TU cache used by the build orchestrator.

The TU cache is depfile-aware:

- On successful compilation, callers should record a depfile path (e.g. GCC/Clang
  `-MMD -MF <path>`).
- The cache stores a normalized dependency list and a combined content hash keyed by
  `(source_path, salt)` where salt is the *exact* compile argv (joined).
- On subsequent runs, cache validity is determined by re-hashing those dependencies.

Thread-safety:

`TranslationUnitCache` uses an internal lock so it can be used from a thread pool
when compiling in parallel.
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

import hashlib
import json
import os
import threading
import re

from typing import Any

def _parse_raw_cache(raw_cache: object, *, num_sets: int) -> list[list[tuple[str, Any]]] | None:
    """Parse and validate the JSON payload for `SetAssociativeCache`."""
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
    """
    JSON-persisted set-associative cache.

    Values are stored as `(key, value)` tuples within each set, and the cache maintains
    LRU-like behavior by moving hits to the end of the set list.

    Notes:
        This cache is generic and does not perform any hashing of values; callers must
        ensure values are JSON-serializable.
    """

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
        """Return the cached value for `key` if present, else None (updates LRU order on hit)."""
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
        """Insert/update the cache entry for `key` (evicting LRU entry within the set if needed)."""
        set_index  : int                   = self._get_set_index(key)
        target_set : list[tuple[str, Any]] = self.cache[set_index]

        target_set[:] = [(k, v) for k, v in target_set if k != key]

        if len(target_set) >= self.associativity:
            target_set.pop(0)

        target_set.append((key, value))
        self.save()

    def save(self) -> None:
        """Persist the cache to disk atomically."""
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

_INCLUDE_RE = re.compile(r'^\s*#\s*include\s*([<"])([^>"]+)[>"]')

def _read_includes(path: str) -> list[tuple[str, str]]:
    includes: list[tuple[str, str]] = []
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as file:
            for line in file:
                match = _INCLUDE_RE.match(line)
                if not match:
                    continue
                includes.append((match.group(1), match.group(2).strip()))
    except OSError:
        return []
    return includes

def _resolve_header(including_file: str, include_kind: str, header: str) -> str | None:
    # Only handle local includes for now; system includes are intentionally ignored.
    if include_kind != '"':
        return None

    candidate = os.path.join(os.path.dirname(including_file), header)
    if os.path.isfile(candidate):
        return candidate

    return None

def _discover_dependencies(source_path: str, *, max_files: int = 4096) -> list[str]:
    visited: set[str] = set()
    stack: list[str] = [os.path.abspath(source_path)]
    deps: list[str] = []

    while stack and len(visited) < max_files:
        current = os.path.abspath(stack.pop())
        current_norm = _norm(current)
        if current_norm in visited:
            continue
        visited.add(current_norm)
        deps.append(current)

        for include_kind, header in _read_includes(current):
            resolved = _resolve_header(current, include_kind, header)
            if not resolved:
                continue
            stack.append(resolved)

    deps.sort(key=_norm)
    return deps

class TranslationUnitCache:
    """
    Translation unit cache keyed by (source path, compile signature).

    A TU is considered valid when:
    - the cached dependency list matches the same file list, and
    - the combined content hash of those dependencies (including the `salt`) matches.

    The `salt` should be a stable signature that changes whenever the produced object
    would change due to configuration (most commonly: the fully-expanded compile argv).
    """

    def __init__(self, path: str = 'build/cache.json') -> None:
        self.path  : str            = path
        self.cache : dict[str, dict[str, object]] = {}
        self._lock: threading.Lock = threading.Lock()

        self._load()

    def _make_key(self, source_path: str, *, salt: str) -> str:
        return f'{_norm(source_path)}\0{salt}'

    def _combined_hash(self, paths: list[str], *, salt: str) -> str:
        digest = hashlib.sha256()
        digest.update(salt.encode('utf-8'))
        digest.update(b'\0')

        for dep in sorted(paths, key=_norm):
            dep_norm = _norm(dep)
            if not os.path.isfile(dep_norm):
                continue
            digest.update(dep_norm.encode('utf-8'))
            digest.update(b'\0')
            digest.update(_sha256_file(dep_norm).encode('utf-8'))
            digest.update(b'\0')

        return digest.hexdigest()

    def _parse_depfile(self, depfile_path: str) -> list[str]:
        """
        Parses a Makefile-style depfile. Best-effort, supports line continuations.
        """
        try:
            text = open(depfile_path, 'r', encoding='utf-8', errors='ignore').read()
        except OSError:
            return []

        text = text.replace('\\\n', ' ')
        # Format: target: dep dep dep
        if ':' not in text:
            return []

        deps_part = text.split(':', 1)[1]
        parts = [p.strip() for p in deps_part.split() if p.strip()]
        # Depfiles often include the output as the first token; filter non-files later.
        return parts

    def _entry_for_source(
        self,
        source_path: str,
        *,
        salt: str,
        depfile_path: str | None,
    ) -> dict[str, object]:
        """
        Builds a cache entry from a depfile (preferred) or from best-effort source scanning.
        """
        source_norm = _norm(source_path)
        deps: list[str]
        if depfile_path:
            deps = self._parse_depfile(depfile_path)
        else:
            deps = []

        if not deps:
            deps = _discover_dependencies(source_norm)

        # Always include the source itself.
        if source_norm not in map(_norm, deps):
            deps.append(source_norm)

        return {
            'deps': [_norm(p) for p in deps],
            'hash': self._combined_hash(deps, salt=salt),
        }

    def is_valid(self, source_path: str, *, salt: str = '') -> bool:
        """
        Return True if the TU cache entry is valid for `source_path` with the given salt.

        Args:
            source_path: Translation unit source file path.
            salt: Compile signature. Must be non-empty.
        """
        if not salt:
            raise ValueError('salt is required')

        key = self._make_key(source_path, salt=salt)

        with self._lock:
            entry_any = self.cache.get(key)

        if not isinstance(entry_any, dict):
            return False

        deps = entry_any.get('deps')
        expected_hash = entry_any.get('hash')

        if not isinstance(deps, list) or not all(isinstance(p, str) for p in deps):
            return False
        if not isinstance(expected_hash, str):
            return False

        current_hash = self._combined_hash(list(deps), salt=salt)
        return current_hash == expected_hash

    def is_dirty(self, source_path: str, *, salt: str = '') -> bool:
        return not self.is_valid(source_path, salt=salt)

    def mark_valid(self, source_path: str, *, salt: str = '', depfile_path: str | None = None) -> None:
        """
        Record a TU as valid in the cache.

        Args:
            source_path: Translation unit source path.
            salt: Compile signature. Must be non-empty.
            depfile_path: Optional depfile path for dependency capture. If missing or unreadable,
                a best-effort `#include "..."` scan is used.
        """
        if not salt:
            raise ValueError('salt is required')
        if not os.path.isfile(_norm(source_path)):
            raise FileNotFoundError(source_path)

        key = self._make_key(source_path, salt=salt)
        entry = self._entry_for_source(source_path, salt=salt, depfile_path=depfile_path)

        with self._lock:
            self.cache[key] = entry
            self.save()

    def invalidate(self, source_path: str) -> None:
        """
        Remove all cached variants of `source_path` (for any salt).

        This is used before compilation to avoid retaining stale entries.
        """
        # Removes all cached variants (different salts) for this source path.
        source_norm = _norm(source_path)
        with self._lock:
            keys = [k for k in self.cache.keys() if isinstance(k, str) and k.split('\0', 1)[0] == source_norm]
            for k in keys:
                del self.cache[k]
            if keys:
                self.save()

    def save(self) -> None:
        # Caller must hold lock.
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

        new_cache: dict[str, dict[str, object]] = {}
        if isinstance(payload, dict):
            for k, v in payload.items():
                if not isinstance(k, str):
                    continue
                # Back-compat: old format was {source_path: "hash"} (no salt).
                if isinstance(v, str):
                    new_cache[f'{_norm(k)}\0legacy'] = {'deps': [_norm(k)], 'hash': v}
                    continue

                if isinstance(v, dict):
                    deps = v.get('deps')
                    h = v.get('hash')
                    if isinstance(deps, list) and all(isinstance(p, str) for p in deps) and isinstance(h, str):
                        new_cache[str(k)] = {'deps': list(deps), 'hash': h}

        with self._lock:
            self.cache = new_cache
