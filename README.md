`bin/start`

This is an early prototype of a translation-unit (TU) cache for a tiny build pipeline.

- Example build: `bin\\start.bat`
- Inputs: `examples\\*.cpp` (and included headers)
- Outputs: `build\\*.o`
- Cache storage: `tmp\\tu_cache\\` (index + cached object files)
