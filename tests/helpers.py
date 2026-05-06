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

import os
import shutil
import time
import uuid
from pathlib import Path


def make_writable_temp_dir(*, base_dir: str) -> str:
    """
    `tempfile` directories are not writable in this sandboxed Windows environment,
    so we create our own per-test directories under the workspace.
    """
    Path(base_dir).mkdir(parents=True, exist_ok=True)
    name = f"t_{int(time.time() * 1000)}_{os.getpid()}_{uuid.uuid4().hex[:8]}"
    path = str((Path(base_dir) / name).resolve())
    Path(path).mkdir(parents=True, exist_ok=False)
    return path


def remove_dir(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)

