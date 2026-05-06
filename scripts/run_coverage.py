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
import sys
import sysconfig
import unittest
from pathlib import Path
from trace import Trace


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    cover_dir = repo_root / "coverage" / "trace"
    cover_dir.mkdir(parents=True, exist_ok=True)

    stdlib_dir = Path(sysconfig.get_path("stdlib") or "").resolve()
    platstdlib_dir = Path(sysconfig.get_path("platstdlib") or "").resolve()
    site_dir = Path(sysconfig.get_path("purelib") or "").resolve()

    ignoredirs = [
        str(stdlib_dir),
        str(platstdlib_dir),
        str(site_dir),
        str((repo_root / "tests").resolve()),
    ]

    tracer = Trace(
        count=True,
        trace=False,
        countfuncs=False,
        countcallers=False,
        ignoremods=(),
        ignoredirs=tuple(ignoredirs),
    )

    def _run_tests() -> int:
        loader = unittest.TestLoader()
        suite = loader.discover(start_dir=str(repo_root / "tests"), top_level_dir=str(repo_root))
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        return 0 if result.wasSuccessful() else 1

    rc = tracer.runfunc(_run_tests)
    results = tracer.results()
    results.write_results(show_missing=True, summary=True, coverdir=str(cover_dir))
    return int(rc)


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[1])
    raise SystemExit(main())
