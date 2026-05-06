"""
fvck.step_cache

Generic cache for non-compile build steps.

`fvck` has two caching layers:

- `TranslationUnitCache` (in `fvck.cache`): keyed by translation unit + compile argv,
  dependency-tracked via compiler-produced depfiles.
- `StepCache` (this module): keyed by an arbitrary step key + step argv, dependency-tracked
  via a user-declared list of input file globs.

The step cache is intended for "wrapper" steps where `fvck` is not responsible for
the full semantics of the tooling (e.g., setuptools/pip/build backends). It provides
fast "did anything relevant change?" checks while keeping the wrapper loosely coupled.
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

from glob import glob
from pathlib import Path
from typing import Any


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


class StepCache:
    """
    Generic cache for non-compile build steps (e.g. setuptools builds).

    Cache keying is explicit: caller provides a stable `key` and a list of input files.
    """

    def __init__(self, *, path: str) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._cache: dict[str, dict[str, object]] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, 'r', encoding='utf-8') as file:
                payload: Any = json.load(file)
        except Exception:
            return
        if not isinstance(payload, dict):
            return
        parsed: dict[str, dict[str, object]] = {}
        for k, v in payload.items():
            if not isinstance(k, str) or not isinstance(v, dict):
                continue
            deps = v.get('deps')
            h = v.get('hash')
            if isinstance(deps, list) and all(isinstance(p, str) for p in deps) and isinstance(h, str):
                parsed[k] = {'deps': list(deps), 'hash': h}
        with self._lock:
            self._cache = parsed

    def _save(self) -> None:
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp_path = f'{self.path}.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as file:
            json.dump(self._cache, file, indent=2, sort_keys=True)
        os.replace(tmp_path, self.path)

    def _combined_hash(self, deps: list[str], *, salt: str) -> str:
        digest = hashlib.sha256()
        digest.update(salt.encode('utf-8'))
        digest.update(b'\0')
        for dep in sorted(deps, key=_norm):
            dep_norm = _norm(dep)
            if not os.path.isfile(dep_norm):
                continue
            digest.update(dep_norm.encode('utf-8'))
            digest.update(b'\0')
            digest.update(_sha256_file(dep_norm).encode('utf-8'))
            digest.update(b'\0')
        return digest.hexdigest()

    def resolve_inputs(self, *, project_root: str, patterns: list[str]) -> list[str]:
        """
        Expand input glob patterns into a stable list of concrete file paths.

        Args:
            project_root: Root directory to resolve patterns from.
            patterns: Glob patterns relative to `project_root`.

        Returns:
            Sorted, de-duplicated list of absolute file paths.
        """
        root = Path(project_root).resolve()
        out: list[str] = []
        for pattern in patterns:
            p = str((root / pattern).as_posix())
            matches = glob(p, recursive=True)
            out.extend([str(Path(m).resolve()) for m in matches if Path(m).is_file()])
        return sorted(set(out), key=lambda x: str(Path(x).resolve()).lower())

    def is_valid(self, *, key: str, deps: list[str], salt: str) -> bool:
        """
        Return True if the cached entry for `key` matches the current dependency hashes.

        The check is strict:
        - dependency list must match exactly
        - combined hash (dependency contents + salt) must match
        """
        with self._lock:
            entry = self._cache.get(key)
        if not isinstance(entry, dict):
            return False
        cached_deps = entry.get('deps')
        cached_hash = entry.get('hash')
        if not isinstance(cached_deps, list) or not all(isinstance(p, str) for p in cached_deps):
            return False
        if not isinstance(cached_hash, str):
            return False
        # If deps changed (different set), invalidate.
        if sorted(map(_norm, cached_deps)) != sorted(map(_norm, deps)):
            return False
        return self._combined_hash(deps, salt=salt) == cached_hash

    def mark_valid(self, *, key: str, deps: list[str], salt: str) -> None:
        """Store/overwrite a cache entry for `key`."""
        with self._lock:
            self._cache[key] = {'deps': list(deps), 'hash': self._combined_hash(deps, salt=salt)}
            self._save()
