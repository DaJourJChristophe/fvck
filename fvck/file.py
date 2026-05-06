"""
fvck.file

Minimal file metadata wrapper used for comparing file timestamps and properties.

This class is not currently used by the main build graph, but remains a useful helper
for future enhancements (e.g., incremental rebuild heuristics or diagnostics).
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

from os   import stat, stat_result
from time import ctime

import stat as stat_module

class File:
    """
    File metadata snapshot.

    Instances store raw timestamps (float seconds) and expose human-readable properties
    via `ctime` for debugging/logging.

    Ordering:
        `File` implements `<` and `>` based on `modified_ts`.
    """

    def __init__(
        self,
        *,
        size_bytes: int,
        created: float,
        modified: float,
        accessed: float,
        mode: str,
        inode: int,
        device: int,
    ) -> None:

        self.__accessed_ts   : float = accessed
        self.__created_ts    : float = created
        self.__device        : int   = device
        self.__inode         : int   = inode
        self.__mode          : str   = mode
        self.__modified_ts   : float = modified
        self.__size_bytes    : int   = size_bytes

    @staticmethod
    def read_file_metadata(path: str) -> 'File':
        """Read `os.stat` metadata for `path` and return a `File` snapshot."""
        st: stat_result = stat(path)

        if hasattr(st, 'st_birthtime'):
            created_time = st.st_birthtime
        else:
            created_time = st.st_ctime # type: ignore

        return File(
            size_bytes=st.st_size,
            created=float(created_time),
            modified=float(st.st_mtime),
            accessed=float(st.st_atime),
            mode=stat_module.filemode(st.st_mode),
            inode=st.st_ino,
            device=st.st_dev,
        )

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, File):
            return NotImplemented
        return self.modified_ts > other.modified_ts

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, File):
            return NotImplemented
        return self.modified_ts < other.modified_ts

    def __repr__(self) -> str:
        return (
            '{'
            f' accessed: {self.accessed},'
            f' created: {self.created},'
            f' device: {self.device},'
            f' inode: {self.inode},'
            f' mode: {self.mode},'
            f' modified: {self.modified},'
            f' size_bytes: {self.size_bytes}'
            ' }\n'
        )

    @property
    def accessed(self) -> str:
        return ctime(self.__accessed_ts)

    @property
    def created(self) -> str:
        return ctime(self.__created_ts)

    @property
    def device(self) -> int:
        return self.__device

    @property
    def inode(self) -> int:
        return self.__inode

    @property
    def mode(self) -> str:
        return self.__mode

    @property
    def modified(self) -> str:
        return ctime(self.__modified_ts)

    @property
    def modified_ts(self) -> float:
        return self.__modified_ts

    @property
    def size_bytes(self) -> int:
        return self.__size_bytes
