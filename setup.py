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

from pathlib import Path

from setuptools import find_packages, setup


def _read_version() -> str:
    ns: dict[str, object] = {}
    version_file = Path(__file__).parent / "fvck" / "__init__.py"
    exec(version_file.read_text(encoding="utf-8"), ns)
    version = ns.get("__version__")
    if not isinstance(version, str):
        raise RuntimeError("Could not read __version__")
    return version


setup(
    name="fvck",
    version=_read_version(),
    description="A configurable build wrapper with TU caching and optional setuptools convenience steps.",
    long_description=(Path(__file__).parent / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    python_requires=">=3.11",
    packages=find_packages(include=["fvck*"]),
    install_requires=["PyYAML>=6.0"],
    entry_points={"console_scripts": ["fvck=fvck.run:main"]},
)

