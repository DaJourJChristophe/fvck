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

import unittest

from fvck.strategy import CommandBuilder


class TestCommandBuilder(unittest.TestCase):
    def test_structured_argv_with_splice(self) -> None:
        builder = CommandBuilder(
            variables={
                "program": "gcc",
                "parameters": ["-c", "-O0"],
                "input": "a.c",
                "output": "a.o",
            }
        )

        argv = builder.build_argv(
            {
                "argv": [
                    "{program}",
                    {"var": "parameters", "splice": True},
                    "-o",
                    {"var": "output"},
                    {"var": "input"},
                ]
            }
        )

        self.assertEqual(argv, ["gcc", "-c", "-O0", "-o", "a.o", "a.c"])

    def test_structured_argv_prefix_separate(self) -> None:
        builder = CommandBuilder(variables={"incs": ["inc1", "inc2"], "parameters": []})
        argv = builder.build_argv({"argv": [{"var": "incs", "splice": True, "prefix": "-I", "separate": True}]})
        self.assertEqual(argv, ["-I", "inc1", "-I", "inc2"])

    def test_unknown_variable_raises(self) -> None:
        builder = CommandBuilder(variables={"parameters": []})
        with self.assertRaises(ValueError):
            builder.build_argv({"argv": [{"var": "nope"}]})

