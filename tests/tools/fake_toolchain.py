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

import argparse
import hashlib
import os
from pathlib import Path


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _append_log(log_path: str, line: str) -> None:
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    # Use newline-delimited atomic-ish appends.
    with open(log_path, "a", encoding="utf-8", newline="\n") as f:
        f.write(line.rstrip("\n") + "\n")
        f.flush()
        os.fsync(f.fileno())


def compile_cmd(args: argparse.Namespace) -> int:
    in_path = str(Path(args.input).resolve())
    out_path = Path(args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = f"input={in_path}\nsha256={_sha256_file(in_path)}\n"
    out_path.write_text(payload, encoding="utf-8")
    _append_log(args.log, f"compile {in_path} -> {out_path}")
    return 0


def link_cmd(args: argparse.Namespace) -> int:
    out_path = Path(args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    object_paths = [str(Path(p).resolve()) for p in args.objects]
    content = "\n".join([Path(p).read_text(encoding="utf-8") for p in object_paths]) + "\n"
    out_path.write_text(content, encoding="utf-8")
    _append_log(args.log, f"link {len(object_paths)} -> {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("compile")
    c.add_argument("--input", required=True)
    c.add_argument("--output", required=True)
    c.add_argument("--log", required=True)
    c.set_defaults(func=compile_cmd)

    l = sub.add_parser("link")
    l.add_argument("--output", required=True)
    l.add_argument("--log", required=True)
    l.add_argument("objects", nargs="*")
    l.set_defaults(func=link_cmd)

    ns = parser.parse_args()
    return int(ns.func(ns))


if __name__ == "__main__":
    raise SystemExit(main())
