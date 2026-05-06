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

from fvck.utilities import Utilities


class TestUtilities(unittest.TestCase):
    def test_is_filepath(self) -> None:
        self.assertTrue(Utilities.is_filepath("a.c"))
        self.assertTrue(Utilities.is_filepath("src/a.c"))
        self.assertFalse(Utilities.is_filepath(""))

    def test_is_dirpath(self) -> None:
        self.assertTrue(Utilities.is_dirpath("build"))
        self.assertTrue(Utilities.is_dirpath("."))
        self.assertFalse(Utilities.is_dirpath(""))

    def test_directory_exists(self) -> None:
        self.assertTrue(Utilities.directory_exists("."))

