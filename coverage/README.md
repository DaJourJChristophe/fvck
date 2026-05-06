# Coverage

Run the full test suite:

`env\\Scripts\\python.exe -m unittest discover -s tests -t . -v`

Generate a coverage report (uses Python stdlib `trace`, avoiding the `coverage` package name collision with this folder):

- Generates per-file coverage data under `coverage/trace/`:
  - `env\\Scripts\\python.exe scripts/run_coverage.py`
