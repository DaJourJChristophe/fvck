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
import unittest
from argparse import Namespace
from pathlib import Path

from fvck.fvck import Fvck
from tests.helpers import make_writable_temp_dir, remove_dir


class TestFvckIntegration(unittest.TestCase):
    def test_parallel_compile_and_link_with_cache(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = str((repo_root / "tests" / "tools" / "fake_toolchain.py").resolve())

        workspace_tmp = str((repo_root / "build" / "test_tmp").resolve())
        td = make_writable_temp_dir(base_dir=workspace_tmp)
        try:
            td_path = Path(td)
            src_dir = td_path / "src"
            src_dir.mkdir(parents=True, exist_ok=True)

            (src_dir / "a.cpp").write_text('#include "h.h"\nint a(){return 1;}\n', encoding="utf-8")
            (src_dir / "b.cpp").write_text('#include "h.h"\nint b(){return 2;}\n', encoding="utf-8")
            (src_dir / "h.h").write_text("int a(); int b();\n", encoding="utf-8")

            build_dir = td_path / "build"
            log_dir = td_path / "logs"
            compile_log = str((log_dir / "compile.log").resolve())
            link_log = str((log_dir / "link.log").resolve())

            cfg_path = td_path / "settings.yaml"
            cfg_path.write_text(
                "\n".join(
                    [
                        "version: 1",
                        "languages:",
                        "  Cpp:",
                        f"    program_path: {sys.executable!s}",
                        "    parameters: []",
                        "    command:",
                        "      argv:",
                        "        - '{program}'",
                        f"        - '{tool}'",
                        "        - compile",
                        "        - --input",
                        "        - '{input}'",
                        "        - --output",
                        "        - '{output}'",
                        "        - --log",
                        f"        - '{compile_log}'",
                        "    outputs:",
                        "      .cpp: .o",
                        "targets:",
                        "  - name: core",
                        "    sources: ['src/*.cpp']",
                        "link_targets:",
                        "  - name: app1",
                        "    program_path: " + str(sys.executable),
                        "    parameters: []",
                        "    output: app1.txt",
                        "    from_targets: ['core']",
                        "    command:",
                        "      argv:",
                        "        - '{program}'",
                        f"        - '{tool}'",
                        "        - link",
                        "        - --output",
                        "        - '{output}'",
                        "        - --log",
                        f"        - '{link_log}'",
                        "        - { var: 'objects', splice: true }",
                        "  - name: app2",
                        "    program_path: " + str(sys.executable),
                        "    parameters: []",
                        "    output: app2.txt",
                        "    from_targets: ['core']",
                        "    command:",
                        "      argv:",
                        "        - '{program}'",
                        f"        - '{tool}'",
                        "        - link",
                        "        - --output",
                        "        - '{output}'",
                        "        - --log",
                        f"        - '{link_log}'",
                        "        - { var: 'objects', splice: true }",
                    ]
                ),
                encoding="utf-8",
            )

            old_cwd = os.getcwd()
            try:
                os.chdir(td)
                args = Namespace(config=str(cfg_path), build=str(build_dir))
                rc = Fvck().run(args)
                self.assertEqual(rc, 0)

                # Outputs exist
                self.assertTrue((build_dir / "src" / "a.o").is_file())
                self.assertTrue((build_dir / "src" / "b.o").is_file())
                self.assertTrue((build_dir / "app1.txt").is_file())
                self.assertTrue((build_dir / "app2.txt").is_file())

                # Second run should not recompile (cache hit), but will relink.
                rc2 = Fvck().run(args)
                self.assertEqual(rc2, 0)

                compile_lines = Path(compile_log).read_text(encoding="utf-8").strip().splitlines()
                self.assertEqual(len(compile_lines), 2)

                # Header change should invalidate both.
                (src_dir / "h.h").write_text("int a(); int b(); int c();\n", encoding="utf-8")
                rc3 = Fvck().run(args)
                self.assertEqual(rc3, 0)
                compile_lines2 = Path(compile_log).read_text(encoding="utf-8").strip().splitlines()
                self.assertEqual(len(compile_lines2), 4)

            finally:
                os.chdir(old_cwd)
        finally:
            remove_dir(td)

    def test_python_bindings_cached_step(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = str((repo_root / "tests" / "tools" / "fake_toolchain.py").resolve())

        workspace_tmp = str((repo_root / "build" / "test_tmp").resolve())
        td = make_writable_temp_dir(base_dir=workspace_tmp)
        try:
            td_path = Path(td)
            (td_path / "src").mkdir(parents=True, exist_ok=True)
            (td_path / "src" / "x.cpp").write_text("int x(){return 1;}\n", encoding="utf-8")
            (td_path / "pyproject.toml").write_text("[build-system]\nrequires=[]\n", encoding="utf-8")
            (td_path / "setup.py").write_text("print('setup placeholder')\n", encoding="utf-8")

            build_dir = td_path / "build"
            log_dir = td_path / "logs"
            binding_log = str((log_dir / "binding.log").resolve())

            cfg_path = td_path / "settings.yaml"
            cfg_path.write_text(
                "\n".join(
                    [
                        "version: 1",
                        "languages:",
                        "  Cpp:",
                        f"    program_path: {sys.executable!s}",
                        "    parameters: []",
                        "    command: { argv: ['{program}', '" + tool + "', 'compile', '--input', '{input}', '--output', '{output}', '--log', '" + str((log_dir / 'compile.log').resolve()) + "'] }",
                        "    outputs: { .cpp: .o }",
                        "targets:",
                        "  - name: core",
                        "    sources: ['src/*.cpp']",
                        "link_targets: []",
                        "python_bindings:",
                        "  - name: bind",
                        "    project_root: .",
                        "    build_subdir: .python_bindings",
                        "    from_targets: ['core']",
                        "    inputs: ['setup.py', 'pyproject.toml']",
                        "    parameters: []",
                        "    command:",
                        "      argv:",
                        "        - '{python}'",
                        f"        - '{tool}'",
                        "        - compile",
                        "        - --input",
                        "        - 'setup.py'",
                        "        - --output",
                        "        - '{build_dir}/stamp.txt'",
                        "        - --log",
                        f"        - '{binding_log}'",
                    ]
                ),
                encoding="utf-8",
            )

            old_cwd = os.getcwd()
            try:
                os.chdir(td)
                args = Namespace(config=str(cfg_path), build=str(build_dir))
                rc1 = Fvck().run(args)
                self.assertEqual(rc1, 0)
                rc2 = Fvck().run(args)
                self.assertEqual(rc2, 0)

                lines = Path(binding_log).read_text(encoding="utf-8").strip().splitlines()
                self.assertEqual(len(lines), 1)
            finally:
                os.chdir(old_cwd)
        finally:
            remove_dir(td)
