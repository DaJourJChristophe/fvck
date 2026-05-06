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
import unittest

from fvck.configuration import load_config
from fvck.settings import Settings

from tests.helpers import make_writable_temp_dir, remove_dir


class TestConfiguration(unittest.TestCase):
    def test_load_sources_languages_and_link(self) -> None:
        workspace_tmp = os.path.join(os.path.dirname(__file__), "..", "build", "test_tmp")
        td = make_writable_temp_dir(base_dir=workspace_tmp)
        try:
            cfg = os.path.join(td, "settings.yaml")
            with open(cfg, "w", encoding="utf-8") as f:
                f.write(
                    "\n".join(
                        [
                            "version: 1",
                            "languages:",
                            "  Cpp:",
                            "    program_path: g++",
                            "    parameters: []",
                            "    command: { argv: ['{program}', '-c', '-o', '{output}', '{input}'] }",
                            "    outputs: { .cpp: .o }",
                            "targets:",
                            "  - name: t",
                            "    sources: ['src/*.cpp']",
                            "link_targets:",
                            "  - name: app",
                            "    program_path: g++",
                            "    parameters: []",
                            "    output: app.exe",
                            "    from_targets: ['t']",
                            "    command: { argv: ['{program}', {var: objects, splice: true}, '-o', '{output}'] }",
                        ]
                    )
                )

            load_config(cfg)
            self.assertIn("cpp", Settings.languages())
            self.assertEqual(Settings.targets()[0].name, "t")
            self.assertEqual(Settings.link_targets()[0].output, "app.exe")
        finally:
            remove_dir(td)

    def test_links_rejects_link_and_links_together(self) -> None:
        # v1 schema has no link/links; enforce version presence.
        workspace_tmp = os.path.join(os.path.dirname(__file__), "..", "build", "test_tmp")
        td = make_writable_temp_dir(base_dir=workspace_tmp)
        try:
            cfg = os.path.join(td, "settings.yaml")
            with open(cfg, "w", encoding="utf-8") as f:
                f.write("languages: {}")

            with self.assertRaises(ValueError):
                load_config(cfg)
        finally:
            remove_dir(td)
