"""Keep optional renderer cache files in a process-owned temporary directory."""
import os
import tempfile

_cache = None

def configure_cache():
    global _cache
    if "MPLCONFIGDIR" not in os.environ:
        _cache = tempfile.TemporaryDirectory(prefix="chart-recover-render-")
        os.environ["MPLCONFIGDIR"] = _cache.name
