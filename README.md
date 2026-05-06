`bin/start`

This is an early prototype of a translation-unit (TU) cache for a tiny build pipeline.

- Example build: `bin\\start.bat`
- Inputs: `examples\\*.cpp` (and included headers)
- Outputs: `build\\*.o`
- Cache storage: `tmp\\tu_cache\\` (index + cached object files)

`python -m unittest discover -s tests -t . -v`
`python scripts/run_coverage.py`

## Install (virtualenv)

From an activated venv:

- Editable: `python -m pip install -e .`
- Regular: `python -m pip install .`

This installs the `fvck` CLI entrypoint (runs `fvck.run:main`):

- `fvck -c config/settings.yaml -b build`

## UAT (zlib)

If you initialize submodules, you can run a real-world-ish UAT build against zlib:

- `git submodule update --init --recursive`
- `fvck -c tests/uat/uat_zlib.yaml -b build/uat_zlib`

`pip freeze | Out-File -Encoding utf8 requirements.txt`

`python -m fvck.run -c tests/uat/uat_zlib.yaml -b build/uat_zlib`
